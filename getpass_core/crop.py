"""Геометрия кадрирования фотографии для бейджа."""
from __future__ import annotations

PHOTO_ASPECT = 3 / 4  # ширина / высота


def compute_crop_box(orig_w, orig_h, state, frame_box, canvas_size):
    """Прямоугольник кадра в координатах исходного файла.

    Гарантирует соотношение сторон 3:4. Раньше при отдалении (scale < 1)
    рамка становилась больше фотографии, обрезалась по её границе, и
    сохранялся кадр произвольной геометрии — не тот, что оператор видел
    в красной рамке.
    """
    canvas_w, canvas_h = canvas_size
    frame_x, frame_y, frame_w, frame_h = frame_box
    cur_scale = state["base_scale"] * state["scale"]
    scaled_w = orig_w * cur_scale
    scaled_h = orig_h * cur_scale
    img_left = (canvas_w / 2 + state["offset_x"]) - scaled_w / 2
    img_top = (canvas_h / 2 + state["offset_y"]) - scaled_h / 2

    rw = frame_w / cur_scale
    rh = frame_h / cur_scale
    rx = (frame_x - img_left) / cur_scale
    ry = (frame_y - img_top) / cur_scale

    # 1) вписать рамку в фотографию, СОХРАНИВ соотношение сторон
    if rw > orig_w:
        rh *= orig_w / rw
        rw = orig_w
    if rh > orig_h:
        rw *= orig_h / rh
        rh = orig_h

    # 2) сдвинуть внутрь границ
    rx = max(0.0, min(rx, orig_w - rw))
    ry = max(0.0, min(ry, orig_h - rh))

    rx, ry = int(round(rx)), int(round(ry))
    rw, rh = int(round(rw)), int(round(rh))
    rw = max(1, min(rw, orig_w - rx))
    rh = max(1, min(rh, orig_h - ry))
    return rx, ry, rw, rh


def compute_crop_from_state(im, orig_w, orig_h, state, frame_box, canvas_size):
    box = compute_crop_box(orig_w, orig_h, state, frame_box, canvas_size)
    rx, ry, rw, rh = box
    return im.crop((rx, ry, rx + rw, ry + rh)), box


def min_scale_for_cover(*_args, **_kwargs) -> float:
    """Минимальный зум: фотография всегда должна закрывать рамку целиком."""
    return 1.0
