from getpass_design.tokens import PALETTES


def build_stylesheet(theme: str) -> str:
    if theme not in PALETTES:
        raise ValueError(f"Unknown theme: {theme}")
    p = PALETTES[theme]
    return f"""
QWidget {{
    background: {p.ground};
    color: {p.ink};
    font-family: \"Segoe UI\";
    font-size: 11pt;
}}
QMainWindow, QWidget#AppShell {{ background: {p.ground}; }}
QScrollArea {{ background: transparent; border: 0; }}
QFrame#Sidebar {{ background: {p.primary}; }}
QLabel#SidebarBrand {{ color: {p.on_primary}; font-size: 18pt; font-weight: 700; }}
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
QLineEdit:focus, QComboBox:focus {{
    border: 2px solid {p.focus};
}}
QLineEdit[invalid=\"true\"] {{
    border: 2px solid {p.danger};
}}
QComboBox QAbstractItemView {{
    background: {p.surface};
    color: {p.ink};
    border: 1px solid {p.line};
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
QFrame#PrintSettings {{
    background: {p.surface_alt};
    border: 1px solid {p.line};
    border-radius: 14px;
}}
QWidget#VehiclePreview {{
    background: {p.surface_alt};
    border: 1px solid {p.line};
    border-radius: 14px;
}}
QPushButton#PrintButton {{
    min-height: 22px;
    background: {p.accent_fill};
    color: {p.on_accent};
}}
QPushButton#PrintButton:hover {{ background: {p.accent_fill_hover}; }}
QPushButton#SavePdfButton {{
    min-height: 22px;
    background: {p.primary};
    color: {p.on_primary};
}}
QPushButton#SavePdfButton:hover {{ background: {p.primary_hover}; }}
"""
