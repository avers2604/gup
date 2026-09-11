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
