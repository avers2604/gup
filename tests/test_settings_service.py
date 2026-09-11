from pathlib import Path

import pytest

from getpass_app.models.preferences import UiPreferences
from getpass_app.services.settings_service import SettingsService


def test_load_ui_preferences_accepts_dark():
    service = SettingsService(
        load=lambda: {"theme": "dark"},
        save=lambda values: True,
    )
    assert service.load_ui_preferences() == UiPreferences(theme="dark")


def test_load_ui_preferences_normalizes_unknown_theme_to_light():
    service = SettingsService(
        load=lambda: {"theme": "neon"},
        save=lambda values: True,
    )
    assert service.load_ui_preferences() == UiPreferences(theme="light")


def test_save_theme_writes_only_supported_value():
    saved = []
    service = SettingsService(
        load=lambda: {},
        save=lambda values: saved.append(values) or True,
    )
    assert service.save_theme("dark") is True
    assert saved == [{"theme": "dark"}]


def test_save_theme_rejects_invalid_value():
    service = SettingsService(load=lambda: {}, save=lambda values: True)
    with pytest.raises(ValueError, match="Unsupported theme"):
        service.save_theme("neon")


def test_application_layer_has_no_pyside6_imports():
    root = Path(__file__).resolve().parents[1] / "getpass_app"
    for path in root.rglob("*.py"):
        assert "PySide6" not in path.read_text(encoding="utf-8"), path
