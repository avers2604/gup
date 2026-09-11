from pathlib import Path

import getpass_qt.app as qt_app
from getpass_qt.app import main


class _SelfTestStack:
    @staticmethod
    def count():
        return 8


class _SelfTestPreview:
    def __init__(self, events):
        self._events = events
        self.has_image = True

    def set_pil_image(self, image):
        self._events.append(("preview", image))
        self.has_image = image is not None


class _SelfTestPlate:
    def __init__(self, events):
        self._events = events

    def setText(self, value):
        self._events.append(("plate", value))


class _SelfTestVehiclePage:
    def __init__(self, events):
        self.preview = _SelfTestPreview(events)
        self.pass_fields = {
            "first": {"plate": _SelfTestPlate(events)},
        }


class _SelfTestSidebar:
    def __init__(self, window, events):
        self._window = window
        self._events = events

    def request_route(self, route):
        self._events.append(("route", route))
        self._window.active_route = route


class _SelfTestWindow:
    events = []

    def __init__(self, theme_manager, vehicle_viewmodel):
        self.active_route = "dashboard"
        self.stack = _SelfTestStack()
        self.sidebar = _SelfTestSidebar(self, self.events)
        self.vehicle_page = _SelfTestVehiclePage(self.events)

    @staticmethod
    def show():
        pass

    @staticmethod
    def close():
        pass


def test_qt_self_test_returns_zero(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assert main(["--self-test"]) == 0


def test_qt_self_test_exercises_debounced_vehicle_binding(monkeypatch):
    events = []
    _SelfTestWindow.events = events

    def fake_wait_for_preview_refresh(window, app):
        events.append(("wait", 250))
        window.vehicle_page.preview.has_image = True

    monkeypatch.setattr(qt_app, "MainWindow", _SelfTestWindow)
    monkeypatch.setattr(
        qt_app,
        "_wait_for_preview_refresh",
        fake_wait_for_preview_refresh,
    )
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    assert main(["--self-test"]) == 0
    assert events == [
        ("route", "vehicle"),
        ("preview", None),
        ("plate", "А111АА78"),
        ("wait", 250),
    ]


def test_phase1_keeps_tkinter_as_default_production_entrypoint():
    source = (
        Path(__file__).resolve().parents[1] / "pass_generator.py"
    ).read_text(encoding="utf-8")
    assert "from getpass_ui.app import App" in source
    assert "from getpass_qt" not in source
