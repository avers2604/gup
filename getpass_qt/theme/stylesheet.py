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
QPushButton[role=\"accent\"] {{
    background: {p.accent_fill};
    color: {p.on_accent};
    border: 0;
    border-radius: 14px;
    padding: 10px 18px;
    font-weight: 700;
}}
QFrame[role=\"card\"] {{
    background: {p.surface};
    border: 1px solid {p.line};
    border-radius: 18px;
}}
QLabel[role=\"muted\"] {{ color: {p.ink_muted}; }}
"""
