from getpass_app.services.settings_service import SettingsService
from getpass_design.tokens import DARK, LIGHT
from getpass_qt.theme.manager import ThemeManager
from getpass_qt.theme.stylesheet import build_stylesheet


def test_light_stylesheet_uses_get_brand_tokens():
    css = build_stylesheet("light")
    for value in (LIGHT.primary, LIGHT.accent_fill, LIGHT.ground, LIGHT.surface):
        assert value in css


def test_dark_stylesheet_uses_dark_palette():
    css = build_stylesheet("dark")
    for value in (DARK.primary, DARK.accent_fill, DARK.ground, DARK.surface):
        assert value in css


def test_vehicle_workspace_styles_use_semantic_tokens_and_states():
    css = build_stylesheet("light")

    assert 'QLineEdit[invalid="true"]' in css
    assert LIGHT.danger in css
    assert LIGHT.focus in css
    assert "QTabWidget#PassSlotTabs" in css
    assert "QFrame#PrintSettings" in css
    assert "QWidget#VehiclePreview" in css
    assert "QPushButton#PrintButton" in css
    assert "QPushButton#SavePdfButton" in css


def test_employee_badge_styles_use_semantic_tokens_and_states():
    css = build_stylesheet("light")

    assert 'QComboBox[invalid="true"]' in css
    assert 'QPushButton#BadgePhotoButton[invalid="true"]' in css
    assert "QFrame#BadgePhotoCard" in css
    assert "QFrame#BadgePrintSettings" in css
    assert "QWidget#BadgePreview" in css
    assert "QWidget#PhotoCropCanvas" in css
    assert "QPushButton#BadgePrintButton" in css
    assert "QPushButton#BadgeSavePdfButton" in css
    assert LIGHT.danger in css
    assert LIGHT.focus in css


def test_phase4_table_styles_use_semantic_tokens():
    css = build_stylesheet("light")

    assert "QTableView" in css
    assert "QHeaderView::section" in css
    assert "QTableView::item:selected" in css
    assert LIGHT.surface in css
    assert LIGHT.surface_alt in css
    assert LIGHT.line in css
    assert LIGHT.primary in css
    assert LIGHT.on_primary in css


def test_theme_manager_persists_toggle(qapp):
    saved = []
    service = SettingsService(
        load=lambda: {"theme": "light"},
        save=lambda values: saved.append(values) or True,
    )
    manager = ThemeManager(qapp, service)
    manager.apply("light", persist=False)
    assert manager.current_theme == "light"
    manager.toggle()
    assert manager.current_theme == "dark"
    assert saved == [{"theme": "dark"}]
