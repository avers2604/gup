"""Шрифты бланков, брендбук Echoes Sans и пиктограммы DoT Icons."""
from __future__ import annotations

import ctypes
import os
from PIL import ImageFont

from . import config

_FONT_CACHE: dict = {}

_CANDIDATES = {
    "title": ["GOTHICB.TTF", "gothicb.ttf", "segoeuib.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf"],
    "plate": ["bahnschrift.ttf", "trebucbd.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf"],
    "geo": ["GOTHICB.TTF", "gothicb.ttf", "segoeuib.ttf", "LiberationSans-Bold.ttf"],
    "geo_reg": ["GOTHIC.TTF", "gothic.ttf", "segoeui.ttf", "LiberationSans-Regular.ttf", "arial.ttf"],
    "body": ["segoeuib.ttf", "calibrib.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf"],
    "light": ["segoeui.ttf", "calibri.ttf", "LiberationSans-Regular.ttf", "arial.ttf"],
}

FONTS_MISSING = False


def get_styled_font(style_type: str, size: int):
    global FONTS_MISSING
    key = (style_type, size)
    cached = _FONT_CACHE.get(key)
    if cached is not None:
        return cached
    font = None
    for name in _CANDIDATES.get(style_type, ["arialbd.ttf"]):
        try:
            font = ImageFont.truetype(name, size)
            break
        except IOError:
            continue
    if font is None:
        FONTS_MISSING = True
        try:
            font = ImageFont.load_default(size)
        except TypeError:
            font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


def fonts_are_missing() -> bool:
    return FONTS_MISSING


_ECHOES_REGULAR = None
_ECHOES_BOLD = None
_ECHOES_FOUND = False
UI_FAMILY = "Segoe UI"

ECHOES_NAMES_REG = [
    "echoes sans.ttf", "echoessans.ttf", "echoes_sans.ttf", "echoessans-regular.ttf",
    "echoes sans regular.ttf", "echoessansregular.ttf", "echoessans-regular.otf",
    "echoes sans.otf", "moscowsans-regular.otf", "moscowsans-regular.ttf", "moscowsans.otf",
    "moscow sans regular.otf", "moscow sans.otf"
]
ECHOES_NAMES_BOLD = [
    "echoes sans bold.ttf", "echoessans-bold.ttf", "echoessansbold.ttf",
    "echoes_sans_bold.ttf", "echoessans-semibold.ttf", "echoes sans semibold.ttf",
    "moscowsansextrabold.otf", "moscowsans-bold.otf", "moscowsansbold.otf",
    "moscow sans bold.otf"
]

BRAND_TOKENS = ("echoes", "moscowsans", "moscow sans")


def find_echoes_font() -> None:
    global _ECHOES_REGULAR, _ECHOES_BOLD, _ECHOES_FOUND
    if _ECHOES_FOUND:
        return
    _ECHOES_FOUND = True

    search_dirs = [config.SCRIPT_DIR, config.FONTS_DIR]
    if os.name == "nt":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        search_dirs.append(os.path.join(windir, "Fonts"))
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            search_dirs.append(os.path.join(local, "Microsoft", "Windows", "Fonts"))

    for d in search_dirs:
        if not d or not os.path.isdir(d):
            continue
        try:
            files = os.listdir(d)
        except Exception:
            continue
        low_map = {f.lower(): f for f in files}

        for name in ECHOES_NAMES_REG:
            if name in low_map and _ECHOES_REGULAR is None:
                _ECHOES_REGULAR = os.path.join(d, low_map[name])
        for name in ECHOES_NAMES_BOLD:
            if name in low_map and _ECHOES_BOLD is None:
                _ECHOES_BOLD = os.path.join(d, low_map[name])

        for f in files:
            fl = f.lower()
            if any(tok in fl for tok in BRAND_TOKENS) and fl.endswith((".ttf", ".otf")):
                full = os.path.join(d, f)
                is_bold = any(k in fl for k in ("bold", "semibold", "-sb", "_sb"))
                if is_bold and _ECHOES_BOLD is None:
                    _ECHOES_BOLD = full
                elif not is_bold and _ECHOES_REGULAR is None:
                    _ECHOES_REGULAR = full

        if _ECHOES_REGULAR and _ECHOES_BOLD:
            break


def get_echoes_font(size: int, bold: bool = False):
    find_echoes_font()
    path = _ECHOES_BOLD if bold else _ECHOES_REGULAR
    if path is None and bold:
        path = _ECHOES_REGULAR
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return get_styled_font("geo" if bold else "geo_reg", size)


def setup_ui_font() -> str:
    global UI_FAMILY
    find_echoes_font()
    if _ECHOES_REGULAR and os.name == "nt":
        try:
            family = ImageFont.truetype(_ECHOES_REGULAR, 20).getname()[0]
            ok = bool(ctypes.windll.gdi32.AddFontResourceW(_ECHOES_REGULAR))
            if _ECHOES_BOLD:
                ctypes.windll.gdi32.AddFontResourceW(_ECHOES_BOLD)
            if ok:
                UI_FAMILY = family
        except Exception:
            UI_FAMILY = "Segoe UI"
    return UI_FAMILY


def ui_family() -> str:
    return UI_FAMILY


def verify_ui_family(root) -> str:
    global UI_FAMILY
    if UI_FAMILY == "Segoe UI":
        return UI_FAMILY
    try:
        from tkinter import font as tkfont
        available = {f.lower() for f in tkfont.families(root)}
        if UI_FAMILY.lower() not in available:
            UI_FAMILY = "Segoe UI"
    except Exception:
        UI_FAMILY = "Segoe UI"
    return UI_FAMILY


DOT_ICON_CANDIDATES = [
    "dot icons.ttf", "dot icons.otf", "doticons.ttf", "doticons.otf",
    "dot_icons.ttf", "dot_icons.otf", "doticons-regular.ttf", "doticons-regular.otf",
    "dot icons regular.ttf", "dot icons regular.otf"
]
_DOT_ICON_PATH = None
_DOT_ICON_PATH_SEARCHED = False
_DOT_FONT_CACHE: dict = {}
_RAQM_OK = None


def find_dot_icons_font():
    global _DOT_ICON_PATH, _DOT_ICON_PATH_SEARCHED
    if _DOT_ICON_PATH_SEARCHED:
        return _DOT_ICON_PATH
    _DOT_ICON_PATH_SEARCHED = True

    for d in (config.FONTS_DIR, config.SCRIPT_DIR):
        if not d or not os.path.isdir(d):
            continue
        try:
            files = os.listdir(d)
        except Exception:
            continue
        low = {f.lower(): f for f in files}
        for name in DOT_ICON_CANDIDATES:
            if name in low:
                _DOT_ICON_PATH = os.path.join(d, low[name])
                return _DOT_ICON_PATH
        for f in sorted(files):
            fl = f.lower()
            if "dot" in fl and "icon" in fl and fl.endswith((".ttf", ".otf")):
                _DOT_ICON_PATH = os.path.join(d, f)
                return _DOT_ICON_PATH
    return _DOT_ICON_PATH


def raqm_ok() -> bool:
    global _RAQM_OK
    if _RAQM_OK is None:
        try:
            from PIL import features
            _RAQM_OK = bool(features.check("raqm"))
        except Exception:
            _RAQM_OK = False
    return _RAQM_OK


def _raqm_layout():
    layout = getattr(ImageFont, "Layout", None)
    if layout is not None and hasattr(layout, "RAQM"):
        return layout.RAQM
    return getattr(ImageFont, "LAYOUT_RAQM", None)


def get_dot_icons_font(size: int):
    if size in _DOT_FONT_CACHE:
        return _DOT_FONT_CACHE[size]
    path = find_dot_icons_font()
    if not path:
        return None
    engine = _raqm_layout() if raqm_ok() else None
    kw = {"layout_engine": engine} if engine is not None else {}
    try:
        f = ImageFont.truetype(path, size, **kw)
    except TypeError:
        try:
            f = ImageFont.truetype(path, size)
        except Exception:
            f = None
    except Exception:
        f = None
    _DOT_FONT_CACHE[size] = f
    return f
