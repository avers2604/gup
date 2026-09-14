import os
import tempfile

from PIL import Image, ImageDraw

from getpass_design.tokens import PALETTES

_ICON_CACHE_DIR = os.path.join(tempfile.gettempdir(), "get_passes_qt_icons")


def _chevron_icon_path(color: str) -> str:
    """Путь к PNG-шеврону нужного цвета — рисуется один раз и кешируется.

    Встроенный Qt::down-arrow через border-color рисует сплошной
    прямоугольник вместо треугольника (проверено на реальном рендере),
    поэтому стрелка комбобокса — обычная картинка, как и логотип в
    сайдбаре.
    """
    safe_name = color.lstrip("#").upper()
    path = os.path.join(_ICON_CACHE_DIR, f"chevron_{safe_name}.png")
    if os.path.exists(path):
        return path
    os.makedirs(_ICON_CACHE_DIR, exist_ok=True)
    size = 24
    scale = 4
    canvas = size * scale
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    width = max(2, int(canvas * 0.10))
    pad = canvas * 0.26
    top = canvas * 0.38
    bottom = canvas * 0.62
    mid = canvas / 2
    points = [(pad, top), (mid, bottom), (canvas - pad, top)]
    draw.line(points, fill=color, width=width, joint="curve")
    radius = width / 2
    for x, y in points:
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color)
    img.resize((size, size), Image.LANCZOS).save(path)
    return path


def build_stylesheet(theme: str) -> str:
    if theme not in PALETTES:
        raise ValueError(f"Unknown theme: {theme}")
    p = PALETTES[theme]
    chevron = _chevron_icon_path(p.accent).replace("\\", "/")
    return f"""
QWidget {{
    background: {p.ground};
    color: {p.ink};
    font-family: \"Segoe UI\";
    font-size: 11pt;
}}
QMainWindow, QWidget#AppShell {{ background: {p.ground}; }}
QScrollArea {{ background: transparent; border: 0; }}
QLabel {{ background: transparent; }}
QFrame#Sidebar {{ background: {p.primary}; }}
QFrame#SidebarLogoCard {{ background: #FFFFFF; border-radius: 14px; }}
QLabel#SidebarBrand {{ color: {p.on_primary}; font-size: 18pt; font-weight: 700; }}
QPushButton {{
    background: {p.surface};
    color: {p.ink};
    border: 1px solid {p.line_strong};
    border-radius: 12px;
    padding: 8px 14px;
}}
QPushButton:hover {{ background: {p.surface_alt}; border-color: {p.focus}; }}
QPushButton:pressed {{ background: {p.line}; }}
QPushButton:disabled {{
    color: {p.ink_faint};
    background: {p.surface_alt};
    border-color: {p.line};
}}
QPushButton[role=\"nav\"] {{
    background: transparent;
    color: {p.on_primary};
    border: 0;
    border-radius: 10px;
    padding: 10px 12px;
    text-align: left;
}}
QPushButton[role=\"nav\"]:checked {{ background: {p.accent_fill}; }}
QPushButton[role=\"primary\"] {{
    background: {p.primary};
    color: {p.on_primary};
    border: 0;
    border-radius: 14px;
    padding: 10px 18px;
    font-weight: 700;
}}
QPushButton[role=\"primary\"]:hover {{ background: {p.primary_hover}; }}
QPushButton[role=\"accent\"] {{
    background: {p.accent_fill};
    color: {p.on_accent};
    border: 0;
    border-radius: 14px;
    padding: 10px 18px;
    font-weight: 700;
}}
QPushButton[role=\"accent\"]:hover {{ background: {p.accent_fill_hover}; }}
QFrame[role=\"card\"] {{
    background: {p.surface};
    border: 1px solid {p.line};
    border-radius: 18px;
}}
QLabel[role=\"muted\"] {{ color: {p.ink_muted}; }}
QLineEdit, QComboBox {{
    background: {p.surface};
    color: {p.ink};
    border: 1px solid {p.line_strong};
    border-radius: 10px;
    padding: 8px 10px;
    selection-background-color: {p.primary};
    selection-color: {p.on_primary};
}}
QComboBox {{ padding-right: 32px; }}
QLineEdit:focus, QComboBox:focus {{
    border: 2px solid {p.focus};
}}
QLineEdit[invalid=\"true\"], QComboBox[invalid=\"true\"] {{
    border: 2px solid {p.danger};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    border: none;
    background: transparent;
}}
QComboBox::down-arrow {{
    image: url(\"{chevron}\");
    width: 13px;
    height: 13px;
}}
QComboBox QAbstractItemView {{
    background: {p.surface};
    color: {p.ink};
    border: 1px solid {p.line};
    border-radius: 10px;
    padding: 4px;
    outline: none;
    selection-background-color: {p.primary};
    selection-color: {p.on_primary};
}}
QCheckBox {{ spacing: 8px; }}
QTabWidget#PassSlotTabs::pane {{
    border: 0;
    background: transparent;
}}
QTabWidget#PassSlotTabs QTabBar::tab {{
    background: {p.surface_alt};
    color: {p.ink_muted};
    border: 1px solid {p.line};
    border-bottom: 0;
    padding: 8px 14px;
    margin-right: 4px;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
}}
QTabWidget#PassSlotTabs QTabBar::tab:selected {{
    background: {p.primary};
    color: {p.on_primary};
}}
QTabWidget#PassSlotTabs QTabBar::tab:disabled {{
    color: {p.ink_faint};
    background: {p.ground};
}}
QFrame#PrintSettings, QFrame#BadgePrintSettings {{
    background: {p.surface_alt};
    border: 1px solid {p.line};
    border-radius: 14px;
}}
QFrame#BadgePhotoCard {{
    background: {p.surface};
    border: 1px solid {p.line};
    border-radius: 18px;
}}
QPushButton#BadgePhotoButton {{
    background: {p.surface_alt};
    color: {p.ink};
    border: 1px solid {p.line_strong};
    border-radius: 10px;
    padding: 8px 10px;
}}
QPushButton#BadgePhotoButton:hover {{ border-color: {p.focus}; }}
QPushButton#BadgePhotoButton[invalid=\"true\"] {{
    border: 2px solid {p.danger};
}}
QWidget#VehiclePreview, QWidget#BadgePreview {{
    background: {p.surface_alt};
    border: 1px solid {p.line};
    border-radius: 14px;
}}
QWidget#PhotoCropCanvas {{
    background: {p.surface_alt};
    border: 1px solid {p.line_strong};
    border-radius: 12px;
}}
QTableView {{
    background: {p.surface};
    alternate-background-color: {p.surface_alt};
    color: {p.ink};
    border: 1px solid {p.line};
    border-radius: 12px;
    gridline-color: {p.line};
    selection-background-color: {p.primary};
    selection-color: {p.on_primary};
}}
QTableView::item {{
    padding: 6px 8px;
    border-bottom: 1px solid {p.line};
}}
QTableView::item:selected {{
    background: {p.primary};
    color: {p.on_primary};
}}
QHeaderView::section {{
    background: {p.surface_alt};
    color: {p.ink};
    border: 0;
    border-right: 1px solid {p.line};
    border-bottom: 1px solid {p.line_strong};
    padding: 8px 10px;
    font-weight: 700;
}}
QTableCornerButton::section {{
    background: {p.surface_alt};
    border: 0;
    border-bottom: 1px solid {p.line_strong};
}}
QPushButton#PrintButton, QPushButton#BadgePrintButton {{
    min-height: 22px;
    background: {p.accent_fill};
    color: {p.on_accent};
}}
QPushButton#PrintButton:hover, QPushButton#BadgePrintButton:hover {{
    background: {p.accent_fill_hover};
}}
QPushButton#SavePdfButton, QPushButton#BadgeSavePdfButton {{
    min-height: 22px;
    background: {p.primary};
    color: {p.on_primary};
}}
QPushButton#SavePdfButton:hover, QPushButton#BadgeSavePdfButton:hover {{
    background: {p.primary_hover};
}}
"""
