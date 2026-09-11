"""Токены фирменного стиля СПб ГУП «Горэлектротранс».

Значения взяты из брендбука предприятия, а не подобраны на глаз.
Модуль намеренно не импортирует ничего, кроме стандартной библиотеки.
"""
from __future__ import annotations

from dataclasses import dataclass, field

BRAND = {
    "navy": "#24305E",
    "teal": "#009CBC",
    "red": "#E4032E",
    "yellow": "#FBBA00",
    "lime": "#AFCB37",
    "mint": "#8ACBC1",
    "grey": "#DADADA",
}

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


@dataclass(frozen=True)
class Palette:
    name: str
    ground: str
    surface: str
    surface_alt: str
    ink: str
    ink_muted: str
    ink_faint: str
    line: str
    line_strong: str
    primary: str
    primary_hover: str
    accent: str
    accent_hover: str
    accent_fill: str
    accent_fill_hover: str
    on_primary: str
    on_accent: str
    danger: str
    warning: str
    success: str
    info: str
    focus: str
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

SPACE = (0, 4, 8, 12, 16, 20, 24, 32, 40, 48)
RADIUS = {"field": 14, "button": 18, "card": 20, "chip": 999}
TYPE = {
    "display": (20, "bold"),
    "title": (15, "bold"),
    "heading": (12, "bold"),
    "body": (11, "normal"),
    "label": (8, "bold"),
    "caption": (9, "normal"),
    "data": (13, "bold"),
}
FONT_STACK = ("Moscow Sans", "Echoes Sans", "Segoe UI", "DejaVu Sans", "sans-serif")
