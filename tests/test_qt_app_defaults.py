from getpass_app.models.preferences import OperatorDefaults, UiPreferences
import getpass_qt.app as qt_app


class FakeSettingsService:
    def __init__(self, *, defaults):
        self.defaults = defaults
        self.operator_loads = 0

    @staticmethod
    def load_ui_preferences():
        return UiPreferences(theme="light")

    @staticmethod
    def save_theme(_theme):
        return True

    def load_operator_defaults(self):
        self.operator_loads += 1
        return self.defaults


class FakeWindow:
    def __init__(self, **_kwargs):
        pass

    @staticmethod
    def show():
        pass

    @staticmethod
    def close():
        pass


def test_self_test_loads_operator_defaults_once_and_shares_snapshot(monkeypatch):
    defaults = OperatorDefaults(
        last_pass_num="555-26",
        territory="Тестовая площадка",
        badge_tab_num="00999",
    )
    settings = FakeSettingsService(defaults=defaults)
    captured = {}

    monkeypatch.setattr(
        qt_app,
        "SettingsService",
        lambda **_kwargs: settings,
    )
    monkeypatch.setattr(
        qt_app,
        "_vehicle_viewmodel",
        lambda *, self_test, defaults: captured.setdefault("vehicle", defaults),
    )
    monkeypatch.setattr(
        qt_app,
        "_employee_badge_viewmodel",
        lambda *, self_test, defaults: captured.setdefault("employee", defaults),
    )
    monkeypatch.setattr(
        qt_app,
        "_batch_viewmodel",
        lambda *, self_test, defaults: captured.setdefault("batch", defaults),
    )
    monkeypatch.setattr(qt_app, "MainWindow", FakeWindow)
    monkeypatch.setattr(qt_app, "_exercise_self_test", lambda *_args: None)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    assert qt_app.main(["--self-test"]) == 0
    assert settings.operator_loads == 1
    assert captured == {
        "vehicle": defaults,
        "employee": defaults,
        "batch": defaults,
    }
