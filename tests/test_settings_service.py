from pathlib import Path

import pytest

from getpass_app.models.preferences import OperatorDefaults, UiPreferences
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


def test_load_operator_defaults_projects_supported_values():
    service = SettingsService(
        load=lambda: {
            "last_pass_num": "007-26",
            "territory": "Площадка 1",
            "otb_post": "Начальник ОТБ",
            "otb_name": "Иванов И.И.",
            "valid_until": "31.12.2027",
            "is_temporary_car": True,
            "print_mode": "a5",
            "badge_park": "Парк № 1",
            "badge_tab_num": "01234",
            "badge_print_mode": "a4_grid",
            "auto_preview_target": "2",
            "warn_duplicates": False,
            "print_pass_back": True,
            "window_geometry": "1200x800",
        },
        save=lambda values: True,
    )

    assert service.load_operator_defaults() == OperatorDefaults(
        last_pass_num="007-26",
        territory="Площадка 1",
        otb_post="Начальник ОТБ",
        otb_name="Иванов И.И.",
        valid_until="31.12.2027",
        is_temporary_car=True,
        print_mode="a5",
        badge_park="Парк № 1",
        badge_tab_num="01234",
        badge_print_mode="a4_grid",
        auto_preview_target="2",
        warn_duplicates=False,
        print_pass_back=True,
    )


def test_load_operator_defaults_normalizes_invalid_enums_and_missing_values():
    service = SettingsService(
        load=lambda: {
            "print_mode": "poster",
            "badge_print_mode": "booklet",
            "auto_preview_target": "3",
        },
        save=lambda values: True,
    )

    defaults = service.load_operator_defaults()

    assert defaults.print_mode == "a4"
    assert defaults.badge_print_mode == "card"
    assert defaults.auto_preview_target == "1"
    assert defaults.warn_duplicates is True


def test_save_operator_defaults_writes_only_operator_keys():
    saved = []
    service = SettingsService(
        load=lambda: {"theme": "dark", "window_geometry": "1200x800"},
        save=lambda values: saved.append(values) or True,
    )
    defaults = OperatorDefaults(
        last_pass_num="010-26",
        territory="Площадка 2",
        otb_post="ОТБ",
        otb_name="Петров П.П.",
        valid_until="31.12.2028",
        is_temporary_car=True,
        print_mode="a5",
        badge_park="Парк № 2",
        badge_tab_num="02000",
        badge_print_mode="a4_single",
        auto_preview_target="2",
        warn_duplicates=False,
        print_pass_back=True,
    )

    assert service.save_operator_defaults(defaults) is True
    assert saved == [{
        "last_pass_num": "010-26",
        "territory": "Площадка 2",
        "otb_post": "ОТБ",
        "otb_name": "Петров П.П.",
        "valid_until": "31.12.2028",
        "is_temporary_car": True,
        "print_mode": "a5",
        "badge_park": "Парк № 2",
        "badge_tab_num": "02000",
        "badge_print_mode": "a4_single",
        "auto_preview_target": "2",
        "warn_duplicates": False,
        "print_pass_back": True,
    }]


def test_save_operator_defaults_rejects_invalid_enum():
    service = SettingsService(load=lambda: {}, save=lambda values: True)
    defaults = OperatorDefaults(print_mode="poster")

    with pytest.raises(ValueError, match="print_mode"):
        service.save_operator_defaults(defaults)


def test_application_layer_has_no_pyside6_imports():
    root = Path(__file__).resolve().parents[1] / "getpass_app"
    for path in root.rglob("*.py"):
        assert "PySide6" not in path.read_text(encoding="utf-8"), path
