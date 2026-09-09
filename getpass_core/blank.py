"""Бланк пропуска на ТС, построенный кодом."""
from __future__ import annotations

import os
from PIL import Image, ImageDraw

from . import config
from .fonts import get_echoes_font

PASS_W, PASS_H = 2480, 1560

C_BORDER = "#1B2A4F"
C_HAIRLINE = "#6F768C"
C_SIGN_LINE = "#A8ABB6"
C_LABEL = "#181A30"
C_CAPTION = "#6F768C"
C_PAPER = "#FFFFFF"

BORDER_W = 3
RADIUS = 22

BOX_DATE = (1835, 85, 2418, 329)
BOX_PLATE = (62, 485, 2418, 665)
BOX_BRAND = (62, 694, 1220, 854)
BOX_TYPE = (1260, 694, 2418, 854)
BOX_MODEL = (62, 885, 1220, 1045)
BOX_COLOR = (1260, 885, 2418, 1045)
BOX_POST = (62, 1074, 2418, 1259)
BOX_OTB = (62, 1290, 2418, 1474)

LOGO_POS = (81, 99)
LOGO_WIDTH = 796

TITLE_BASELINE = 409
TITLE_X = 840

LABEL_DX, LABEL_DY = 36, 25
HAIRLINE_INSET = 33

_ASSETS_DIR = os.path.join(config.BUNDLE_DIR, "assets")
if not os.path.exists(_ASSETS_DIR):
    _ASSETS_DIR = os.path.join(config.SCRIPT_DIR, "assets")

LOGO_FILE = os.path.join(_ASSETS_DIR, "logo_get.png")

_logo_cache: dict[int, Image.Image] = {}
_knockout_cache: dict[int, Image.Image] = {}
_blank_cache: dict[str, Image.Image] = {}


def logo_available() -> bool:
    return os.path.exists(LOGO_FILE)


def load_logo(width: int):
    cached = _logo_cache.get(width)
    if cached is not None:
        return cached.copy()
    if not os.path.exists(LOGO_FILE):
        return None
    try:
        logo = Image.open(LOGO_FILE).convert("RGBA")
    except Exception:
        return None
    height = max(1, int(logo.height * width / logo.width))
    logo = logo.resize((width, height), Image.Resampling.LANCZOS)
    _logo_cache[width] = logo
    return logo.copy()


def load_logo_knockout(width: int):
    cached = _knockout_cache.get(width)
    if cached is not None:
        return cached.copy()
    base = load_logo(width)
    if base is None:
        return None
    white = Image.new("RGBA", base.size, (255, 255, 255, 0))
    alpha = base.getchannel("A")
    white.putalpha(alpha)
    _knockout_cache[width] = white
    return white.copy()


def _rounded(draw, box, radius=RADIUS, width=BORDER_W, outline=C_BORDER, fill=None):
    draw.rounded_rectangle(box, radius=radius, outline=outline, width=width, fill=fill)


def _label(draw, box, text, size=44):
    draw.text((box[0] + LABEL_DX, box[1] + LABEL_DY), text, fill=C_LABEL,
              font=get_echoes_font(size, bold=True), anchor="la")


def _hairline(draw, box, y, color=C_HAIRLINE, width=2):
    draw.line([(box[0] + HAIRLINE_INSET, y), (box[2] - HAIRLINE_INSET, y)],
              fill=color, width=width)


def _caption(draw, x, y, text, size=32):
    draw.text((x, y), text, fill=C_CAPTION, font=get_echoes_font(size), anchor="ma")


def build_pass_blank() -> Image.Image:
    cached = _blank_cache.get("pass")
    if cached is not None:
        return cached.copy()

    img = Image.new("RGB", (PASS_W, PASS_H), C_PAPER)
    draw = ImageDraw.Draw(img)

    logo = load_logo(LOGO_WIDTH)
    if logo is not None:
        img.paste(logo, LOGO_POS, logo)

    _rounded(draw, BOX_DATE)

    _rounded(draw, BOX_PLATE)
    _hairline(draw, BOX_PLATE, 628)
    _caption(draw, 1240, 636, "Государственный номерной знак")

    _rounded(draw, BOX_BRAND)
    _label(draw, BOX_BRAND, "Марка")
    _rounded(draw, BOX_TYPE)
    _label(draw, BOX_TYPE, "Вид")
    _rounded(draw, BOX_MODEL)
    _label(draw, BOX_MODEL, "Модель")
    _rounded(draw, BOX_COLOR)
    _label(draw, BOX_COLOR, "Цвет")

    _rounded(draw, BOX_POST)
    _label(draw, BOX_POST, "Должность")
    _hairline(draw, BOX_POST, 1218)
    _caption(draw, 1240, 1226, "Наименование должности лица, управляющего ТС", size=30)

    _rounded(draw, BOX_OTB)
    _label(draw, BOX_OTB, "Ответственный за ОТБ")
    for x0, x1, caption in ((95, 784, "Должность"), (829, 1525, "Подпись"),
                            (1570, 2265, "Расшифровка")):
        draw.line([(x0, 1432), (x1, 1432)], fill=C_SIGN_LINE, width=2)
        _caption(draw, (x0 + x1) // 2, 1440, caption, size=30)

    draw.text((2387, 1432), "М.П.", fill=C_LABEL,
              font=get_echoes_font(38, bold=True), anchor="rs")

    _blank_cache["pass"] = img
    return img.copy()


def reset_cache() -> None:
    _logo_cache.clear()
    _knockout_cache.clear()
    _blank_cache.clear()