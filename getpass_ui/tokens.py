"""Токены фирменного стиля СПб ГУП «Горэлектротранс».

Значения взяты из брендбука предприятия, а не подобраны на глаз.
Модуль намеренно не импортирует ничего, кроме стандартной библиотеки —
его можно скопировать в любую другую программу ГЭТ как есть.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ─────────────────────────── фирменные цвета ───────────────────────────
#: Основные и дополнительные цвета брендбука. В скобках — CMYK из гайдлайна.
BRAND = {
    "navy":   "#24305E",   # C100 M90 Y35 K20 — основной
    "teal":   "#009CBC",   # C100 M0  Y25 K0  — городской троллейбус
    "red":    "#E4032E",   # C0   M100 Y80 K0 — городской трамвай
    "yellow": "#FBBA00",   # C0   M30 Y100 K0
    "lime":   "#AFCB37",   # C40  M0  Y90 K0
    "mint":   "#8ACBC1",   # C50  M0  Y30 K0
    "grey":   "#DADADA",   # K20
}

#: Закреплённое в брендбуке соответствие вида транспорта и цвета.
TRANSPORT = {"tram": BRAND["red"], "trolleybus": BRAND["teal"]}


def mix(color_a: str, color_b: str, t: float) -> str:
    """Линейное смешение двух цветов, t=0 → a, t=1 → b."""
    a = tuple(int(color_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(color_b[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def lighten(color: str, t: float) -> str:
    return mix(color, "#FFFFFF", t)


def darken(color: str, t: float) -> str:
    return mix(color, "#000000", t)


def relative_luminance(color: str) -> float:
    def channel(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """Контраст по WCAG: 4.5 — минимум для основного текста."""
    l1, l2 = sorted((relative_luminance(fg), relative_luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def readable_on(bg: str, dark: str = "#151A2B", light: str = "#FFFFFF") -> str:
    """Выбрать текст, который читается на данном фоне."""
    return dark if contrast_ratio(dark, bg) >= contrast_ratio(light, bg) else light


# ───────────────────────────── палитры тем ─────────────────────────────

@dataclass(frozen=True)
class Palette:
    name: str
    # поверхности
    ground: str          # полотно окна
    surface: str         # карточка
    surface_alt: str     # чередование строк, вложенные блоки
    # текст
    ink: str             # основной
    ink_muted: str       # подписи полей
    ink_faint: str       # подсказки
    # линии
    line: str
    line_strong: str
    # действия
    primary: str         # тёмно-синий брендбука
    primary_hover: str
    accent: str          # чистый фирменный бирюзовый — индикаторы, акценты
    accent_hover: str
    accent_fill: str     # затемнённый: заливка кнопок с белой подписью
    accent_fill_hover: str
    on_primary: str
    on_accent: str
    # состояния
    danger: str
    warning: str
    success: str
    info: str
    focus: str
    #: выворотка знака: True — использовать белую версию логотипа
    logo_knockout: bool = False
    extra: dict = field(default_factory=dict)


LIGHT = Palette(
    name="light",
    ground="#F4F5F9",
    surface="#FFFFFF",
    surface_alt="#F7F8FB",
    ink="#151A2B",
    ink_muted="#5C6480",
    ink_faint="#8A91A8",
    line="#E3E5EE",
    line_strong="#CBCFDD",
    primary=BRAND["navy"],
    primary_hover=lighten(BRAND["navy"], 0.14),
    accent=BRAND["teal"],
    accent_hover=lighten(BRAND["teal"], 0.12),
    # Белый на чистой бирюзе даёт контраст 3.24 — ниже нормы WCAG 4.5.
    # Для заливок с подписью берём затемнённый оттенок (4.61), чистый
    # фирменный цвет остаётся на индикаторах, где текста нет.
    accent_fill=darken(BRAND["teal"], 0.18),
    accent_fill_hover=darken(BRAND["teal"], 0.08),
    on_primary="#FFFFFF",
    on_accent="#FFFFFF",
    danger=BRAND["red"],
    warning=BRAND["yellow"],
    success=BRAND["lime"],
    info=BRAND["mint"],
    focus=BRAND["teal"],
)

#: Тёмная тема опирается на разрешённую брендбуком выворотку знака
#: на тёмно-синем и чёрном фоне.
DARK = Palette(
    name="dark",
    ground="#12172A",
    surface="#1A2039",
    surface_alt="#212949",
    ink="#EEF0F8",
    ink_muted="#A7AEC8",
    ink_faint="#7B839F",
    line="#2C3454",
    line_strong="#3D4870",
    primary=lighten(BRAND["navy"], 0.30),
    primary_hover=lighten(BRAND["navy"], 0.42),
    accent=lighten(BRAND["teal"], 0.10),
    accent_hover=lighten(BRAND["teal"], 0.24),
    accent_fill=lighten(BRAND["teal"], 0.10),
    accent_fill_hover=lighten(BRAND["teal"], 0.24),
    on_primary="#FFFFFF",
    on_accent="#08202A",
    danger=lighten(BRAND["red"], 0.24),
    warning=BRAND["yellow"],
    success=BRAND["lime"],
    info=BRAND["mint"],
    focus=lighten(BRAND["teal"], 0.18),
    logo_knockout=True,
)

PALETTES = {"light": LIGHT, "dark": DARK}

# ───────────────────────── размеры и типографика ─────────────────────────

#: Шаг сетки — 4 px. Все отступы кратны ему.
SPACE = (0, 4, 8, 12, 16, 20, 24, 32, 40, 48)

RADIUS = {"field": 8, "button": 10, "card": 14, "chip": 999}

#: Кегли в пунктах: Tk масштабирует их сам по tk scaling.
TYPE = {
    "display": (20, "bold"),
    "title":   (15, "bold"),
    "heading": (12, "bold"),
    "body":    (11, "normal"),
    "label":   (8,  "bold"),     # капительные подписи полей
    "caption": (9,  "normal"),
    "data":    (13, "bold"),     # госномер, табельный номер
}

#: Порядок предпочтения шрифтов интерфейса.
FONT_STACK = ("Moscow Sans", "Echoes Sans", "Segoe UI", "DejaVu Sans", "sans-serif")
