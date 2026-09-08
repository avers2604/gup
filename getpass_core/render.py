"""Отрисовка бланков: пропуск на ТС, бейдж работника, листы А4.

Геометрия и координаты перенесены из первоначальной версии без изменений —
макет откалиброван по типографскому бланку, трогать его нельзя.
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

from . import config
from .domain import format_plate_visual
from .fonts import (get_dot_icons_font, get_echoes_font, get_styled_font,
                    raqm_ok)

CARD_W, CARD_H = 638, 1004
A4_W, A4_H = 2480, 3508
PASS_W, PASS_H = 2480, 1560


class TemplateMissing(Exception):
    """Нет template.png — бланк будет отрисован на белом фоне."""


def _ellipsize(draw, text, font, max_w):
    """Обрезать текст многоточием, если он не влезает даже минимальным кеглем."""
    if draw.textbbox((0, 0), text, font=font)[2] <= max_w:
        return text
    ell = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if draw.textbbox((0, 0), text[:mid] + ell, font=font)[2] <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return (text[:lo] + ell) if lo else ell


def draw_auto_fit_text(draw, text, x, y, max_w, max_size, min_size=16, font_style="body", fill="#1b2126", anchor="mm", **kwargs):
    if not text:
        return
    size = max_size
    while size > min_size:
        f = get_styled_font(font_style, size)
        bbox = draw.textbbox((0, 0), text, font=f)
        if (bbox[2] - bbox[0]) <= max_w:
            break
        size -= 2
    font = get_styled_font(font_style, size)
    font = get_styled_font(font_style, size)
    text = _ellipsize(draw, text, font, max_w)
    draw.text((x, y), text, fill=fill, font=font, anchor=anchor)


def _fit_text(draw, text, x, y, max_w, max_size, font_echoes=None, anchor="mm",
              fill="#000000", bold=False):
    """Вписать текст в колонку реестра.

    Раньше при неподходящем тексте функция оставляла ИСХОДНЫЙ (максимальный)
    кегль и текст наезжал на соседние колонки. Теперь кегль честно опускается
    до минимального, а остаток обрезается многоточием.
    """
    if not text:
        return
    min_size = 16
    size = max_size
    font = None
    while size >= min_size:
        f = get_echoes_font(size, bold=bold)
        if (draw.textbbox((0, 0), text, font=f)[2] - draw.textbbox((0, 0), text, font=f)[0]) <= max_w:
            font = f
            break
        size -= 2
    if font is None:
        font = get_echoes_font(min_size, bold=bold)
        text = _ellipsize(draw, text, font, max_w)
    draw.text((x, y), text, fill=fill, font=font, anchor=anchor)


def draw_dot_icon(draw, code, x, y, color, size=48, anchor="mm", bg_code=None, bg_color="#FFFFFF"):
    """Пиктограмма DoT Icons. bg_code — подложка (o/O/d/D) другим цветом."""
    f = get_dot_icons_font(size)
    if f is None:
        return False
    if bg_code:
        draw.text((x, y), bg_code, fill=bg_color, font=f, anchor=anchor)
    draw.text((x, y), code, fill=color, font=f, anchor=anchor)
    return True

def draw_sheet_brand_icons(draw, x, y, size=48, color_tram="#C62828", color_trol="#009FA0"):
    """Пара tram+trol — фирменный знак ГЭТ в строке заголовка листа."""
    ok1 = draw_dot_icon(draw, "tram", x, y, color_tram, size=size, anchor="lm")
    ok2 = draw_dot_icon(draw, "trol", x + int(size * 1.5), y, color_trol, size=size, anchor="lm")
    return ok1 or ok2


_CACHED_BASE_TEMPLATE = None
_CACHED_BADGE_LOGO = None


def template_exists() -> bool:
    return os.path.exists(config.TEMPLATE_FILE)


def get_base_template(silent=True):
    """Подложка бланка. При отсутствии файла возвращает белый лист.

    silent=True по умолчанию: функция вызывается из авто-предпросмотра, и
    модальное окно об ошибке там всплывало само собой при каждом запуске.
    Сообщать об отсутствии шаблона должен интерфейс, один раз.
    """
    global _CACHED_BASE_TEMPLATE
    target_w, target_h = PASS_W, PASS_H
    if os.path.exists(config.TEMPLATE_FILE):
        try:
            if _CACHED_BASE_TEMPLATE is None:
                im = Image.open(config.TEMPLATE_FILE).convert("RGB")
                _CACHED_BASE_TEMPLATE = im.resize((target_w, target_h), Image.Resampling.LANCZOS)
            return _CACHED_BASE_TEMPLATE.copy()
        except Exception as exc:
            if not silent:
                raise TemplateMissing(str(exc)) from exc
    elif not silent:
        raise TemplateMissing(config.TEMPLATE_FILE)
    return Image.new("RGB", (target_w, target_h), "#ffffff")


def get_badge_logo_img(target_width=340):
    global _CACHED_BADGE_LOGO
    if _CACHED_BADGE_LOGO is None:
        base_tpl = get_base_template(silent=True)
        _CACHED_BADGE_LOGO = base_tpl.crop((60, 65, 890, 260))
    aspect = _CACHED_BADGE_LOGO.height / _CACHED_BADGE_LOGO.width
    target_h = int(target_width * aspect)
    return _CACHED_BADGE_LOGO.resize((target_width, target_h), Image.Resampling.LANCZOS)


def reset_template_cache():
    global _CACHED_BASE_TEMPLATE, _CACHED_BADGE_LOGO
    _CACHED_BASE_TEMPLATE = None
    _CACHED_BADGE_LOGO = None


def fit_photo_to_box(photo_path, target_w, target_h):
    im = Image.open(photo_path).convert("RGB")
    orig_w, orig_h = im.size
    scale = max(target_w / orig_w, target_h / orig_h)
    new_w, new_h = int(orig_w * scale), int(orig_h * scale)
    resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))

def render_single_badge_image(badge_data):
    badge = Image.new("RGB", (CARD_W, CARD_H), "#FFFFFF")
    draw = ImageDraw.Draw(badge)
    C_NAVY = "#0A2540"; C_TEXT = "#1B2126"
    badge.paste(get_badge_logo_img(target_width=340), (25, 20))
    draw_auto_fit_text(draw, badge_data.get("park", ""), CARD_W // 2, 142, 590, 32, min_size=18, font_style="body", fill=C_NAVY, anchor="mm")
    draw_auto_fit_text(draw, badge_data.get("role", ""), CARD_W // 2, 182, 590, 32, min_size=18, font_style="body", fill=C_TEXT, anchor="mm")
    pw, ph = 582, 560
    photo_path = badge_data.get("photo_path")
    if photo_path and os.path.exists(photo_path):
        try:
            badge.paste(fit_photo_to_box(photo_path, pw, ph), (28, 215))
        except Exception:
            draw.rectangle([28, 215, 28 + pw, 215 + ph], fill="#F0F4F8")
    else:
        draw.rectangle([28, 215, 28 + pw, 215 + ph], fill="#F0F4F8")
        draw.text((CARD_W // 2, 215 + ph // 2), "ФОТОГРАФИЯ СОТРУДНИКА", fill="#9AA5B1",
                  font=get_styled_font("body", 28), anchor="mm", align="center")
    draw.rectangle([28, 215, 28 + pw, 215 + ph], outline="#CBD2D9", width=1)
    draw_auto_fit_text(draw, (badge_data.get("surname") or "").upper(), CARD_W // 2, 825, 580, 38, min_size=18, font_style="body", fill="#000000", anchor="mm")
    draw_auto_fit_text(draw, (badge_data.get("name") or "").upper(), CARD_W // 2, 870, 580, 38, min_size=18, font_style="body", fill="#000000", anchor="mm")
    draw_auto_fit_text(draw, (badge_data.get("patronymic") or "").upper(), CARD_W // 2, 915, 580, 38, min_size=18, font_style="body", fill="#000000", anchor="mm")
    date_str = f"с {badge_data.get('issue_date', '')} по {badge_data.get('valid_until', '')}"
    draw.text((28, 970), date_str, fill="#1B2126", font=get_styled_font("light", 24), anchor="ls")
    draw.text((CARD_W - 28, 970), badge_data.get("tab_num", ""), fill=C_NAVY, font=get_styled_font("title", 42), anchor="rs")
    return badge

def build_a4_sheet_of_badges(badge_img, count=9):
    """Лист А4 из `count` копий одного бейджа (проверено: пиксель-в-пиксель как раньше)."""
    return build_badge_a4_grid([badge_img] * count)

def render_pass(pass_data, common_data, silent=True):
    base_img = get_base_template(silent=silent)
    target_w, target_h = base_img.size
    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    C_NAVY = "#0A2540"; C_TEXT = "#1B2126"; C_RED = "#C62828"; C_SIGNAL_RED = "#D32F2F"
    if common_data.get("is_temporary"):
        draw.rectangle([500, 345, 1950, 425], fill="#ffffff")
        font_title = get_styled_font("title", 74)
        title_str = "ВРЕМЕННЫЙ  ПРОПУСК  №"
        num_str = pass_data["num"]
        full_str = f"{title_str}  {num_str}"
        total_w = draw.textlength(full_str, font=font_title)
        start_x = (target_w - total_w) // 2
        w_title = draw.textlength(title_str + "  ", font=font_title)
        draw.text((start_x, 410), title_str, fill="#181a30", font=font_title, anchor="ls")
        draw.text((start_x + w_title, 410), num_str, fill=C_NAVY, font=font_title, anchor="ls")
    else:
        draw.text((1400, 410), pass_data["num"], fill=C_NAVY, font=get_styled_font("title", 76), anchor="ls")
    if pass_data.get("territory"):
        draw_auto_fit_text(draw, pass_data["territory"].upper(), x=1240, y=452, max_w=1400, max_size=36,
                           min_size=20, font_style="geo", fill=C_NAVY, anchor="mm")
    else:
        draw.rectangle([70, 438, target_w - 70, 464], fill=C_SIGNAL_RED)
    draw_auto_fit_text(draw, format_plate_visual(pass_data.get("plate", "")), x=1240, y=558, max_w=1700,
                       max_size=145, min_size=55, font_style="plate", fill="#000000", anchor="mm")
    draw_auto_fit_text(draw, pass_data.get("brand", ""), 680, 775, max_w=800, max_size=64, min_size=24, font_style="body", fill=C_TEXT, anchor="mm")
    draw_auto_fit_text(draw, pass_data.get("model", ""), 680, 965, max_w=800, max_size=64, min_size=24, font_style="body", fill=C_TEXT, anchor="mm")
    draw_auto_fit_text(draw, pass_data.get("type", ""), 1860, 775, max_w=800, max_size=64, min_size=24, font_style="body", fill=C_TEXT, anchor="mm")
    draw_auto_fit_text(draw, pass_data.get("color", ""), 1860, 965, max_w=800, max_size=64, min_size=24, font_style="body", fill=C_TEXT, anchor="mm")
    draw_auto_fit_text(draw, pass_data.get("driver_full", ""), x=1240, y=1195, max_w=1850, max_size=58,
                       min_size=26, font_style="body", fill=C_TEXT, anchor="ms")
    draw_auto_fit_text(draw, common_data.get("otb_post", ""), x=440, y=1420, max_w=650, max_size=48, min_size=22, font_style="body", fill=C_TEXT, anchor="ms")
    draw_auto_fit_text(draw, common_data.get("otb_name", ""), x=1917, y=1420, max_w=650, max_size=54, min_size=24, font_style="body", fill=C_TEXT, anchor="ms")
    f_d_lbl = get_styled_font("geo_reg", 36); f_d_val = get_styled_font("title", 46); f_d_exp = get_styled_font("title", 54)
    draw.text((1940, 150), "ВЫДАН:", fill="#626577", font=f_d_lbl, anchor="lm")
    draw.text((2120, 150), common_data.get('issue_date', ''), fill=C_NAVY, font=f_d_val, anchor="lm")
    draw.line([(1920, 202), (2335, 202)], fill="#CBD2D9", width=2)
    draw.text((1940, 260), "ДО:", fill=C_RED, font=f_d_lbl, anchor="lm")
    draw.text((2050, 260), common_data.get('valid_until', ''), fill=C_RED, font=f_d_exp, anchor="lm")
    return img


def render_dot_icons_test_sheet():
    """Тестовый лист кодов пиктограмм. Возвращает (изображение, есть_raqm)."""
    codes = ["tram", "trol", "p", "no", "b", "left", "right", "up", "down", "back",
             "pl", "pr", "1", "7", "11a", "o8", "o8a", "o1", "o11a", "O2", "d1", "Dd1",
             "o2", "o20", "x1", "x20", "tram21", "trol7"]
    img = Image.new("RGB", (PASS_W, PASS_H), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    draw.text((1240, 90), "DoT Icons — тестовый лист кодов (ГЭТ)", fill="#0A2540",
              font=get_echoes_font(56, bold=True), anchor="mm")
    if not raqm_ok():
        draw.text((1240, 170), "ВНИМАНИЕ: Pillow собран без RAQM — составные лигатуры могут не собраться",
                  fill="#C62828", font=get_echoes_font(34, bold=True), anchor="mm")
    x, y = 160, 300
    for code in codes:
        drawn = draw_dot_icon(draw, code, x + 70, y + 60, "#D32F2F", size=90)
        draw.text((x + 160, y + 60), code if drawn else f"{code}  (нет шрифта)",
                  fill="#1B2126", font=get_echoes_font(34), anchor="lm")
        x += 760
        if x > 2200:
            x = 160
            y += 210
    return img, raqm_ok()


def build_pass_a4_sheet(img1, img2=None):
    """Лист А4 с одним или двумя пропусками и линией разреза."""
    sheet = Image.new("RGB", (A4_W, A4_H), "white")
    draw = ImageDraw.Draw(sheet)
    y_slot = A4_H // 2
    sheet.paste(img1, (0, (y_slot - img1.height) // 2))
    if img2 is not None:
        sheet.paste(img2, (0, y_slot + (y_slot - img2.height) // 2))
    for x in range(120, 2360, 45):
        draw.line([(x, y_slot), (x + 25, y_slot)], fill="#9E9E9E", width=3)
    draw.text((1240, y_slot), "   ✂   ЛИНИЯ РАЗРЕЗА   ✂   ", fill="#757575",
              font=get_styled_font("geo", 36), anchor="mm")
    return sheet


def build_badge_a4_single(badge_img):
    sheet = Image.new("RGB", (A4_W, A4_H), "#FFFFFF")
    x_c = (A4_W - CARD_W) // 2
    y_c = (A4_H - CARD_H) // 2
    sheet.paste(badge_img, (x_c, y_c))
    ImageDraw.Draw(sheet).rectangle([x_c, y_c, x_c + CARD_W, y_c + CARD_H],
                                    outline="#CBD2D9", width=2)
    return sheet


def build_badge_a4_grid(badge_images):
    """Лист А4 с сеткой 3x3 из уже отрисованных бейджей."""
    cols, rows = 3, 3
    sheet = Image.new("RGB", (A4_W, A4_H), "#FFFFFF")
    draw = ImageDraw.Draw(sheet)
    total_w, total_h = cols * CARD_W, rows * CARD_H
    start_x = (A4_W - total_w) // 2
    start_y = (A4_H - total_h) // 2
    for i, b_img in enumerate(badge_images[:cols * rows]):
        r, c = divmod(i, cols)
        x, y = start_x + c * CARD_W, start_y + r * CARD_H
        sheet.paste(b_img, (x, y))
        draw.rectangle([x, y, x + CARD_W, y + CARD_H], outline="#A0AEC0", width=2)
    draw.text((1240, start_y - 60),
              "СПБ ГУП «ГОРЭЛЕКТРОТРАНС» — ЛИСТ ПЕЧАТИ ПРОПУСКОВ РАБОТНИКОВ (85 × 54 мм)",
              fill="#718096", font=get_styled_font("light", 32), anchor="mm")
    draw_sheet_brand_icons(draw, 150, start_y - 60, size=44)
    return sheet
