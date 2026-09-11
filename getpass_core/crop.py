"""Геометрия кадрирования фотографии для бейджа."""
from __future__ import annotations

PHOTO_ASPECT = 3 / 4  # ширина / высота


def compute_crop_box(orig_w, orig_h, state, frame_box, canvas_size):
    canvas_w, canvas_h = canvas_size
    frame_x, frame_y, frame_w, frame_h = frame_box
    cur_scale = max(1e-4, float(state.get("base_scale", 1.0)) * float(state.get("scale", 1.0)))

    scaled_w = orig_w * cur_scale
    scaled_h = orig_h * cur_scale
    img_left = (canvas_w / 2 + state.get("offset_x", 0.0)) - scaled_w / 2
    img_top = (canvas_h / 2 + state.get("offset_y", 0.0)) - scaled_h / 2

    rw = frame_w / cur_scale
    rh = frame_h / cur_scale
    rx = (frame_x - img_left) / cur_scale
    ry = (frame_y - img_top) / cur_scale

    # Вписать рамку в границы, сохраняя пропорции
    if rw > orig_w:
        rh *= orig_w / rw
        rw = orig_w
    if rh > orig_h:
        rw *= orig_h / rh
        rh = orig_h

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
    return 1.0
