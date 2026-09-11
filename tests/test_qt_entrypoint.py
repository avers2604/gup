from pathlib import Path

import getpass_qt.app as qt_app
from getpass_qt.app import main


def test_qt_self_test_returns_zero(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assert main(["--self-test"]) == 0


def test_qt_self_test_exercises_vehicle_route_and_binding(monkeypatch):
    events = []

    class FakeStack:
        @staticmethod
        def count():
            return 8

    class FakePreview:
        has_image = False

    class FakePlate:
        def __init__(self, window):
            self._window = window

        def setText(self, value):
            events.append(("plate", value))
            self._window.vehicle_page.preview.has_image = True

    class FakeVehiclePage:
        def __init__(self, window):
            self.preview = FakePreview()
            self.pass_fields = {
                "first": {"plate": FakePlate(window)},
            }

    class FakeSidebar:
        def __init__(self, window):
            self._window = window

        def request_route(self, route):
            events.append(("route", route))
            self._window.active_route = route

    class FakeWindow:
        def __init__(self, theme_manager, vehicle_viewmodel):
            self.active_route = "dashboard"
            self.stack = FakeStack()
            self.sidebar = FakeSidebar(self)
            self.vehicle_page = FakeVehiclePage(self)

        @staticmethod
        def show():
            pass

        @staticmethod
        def close():
            pass

    monkeypatch.setattr(qt_app, "MainWindow", FakeWindow)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    assert main(["--self-test"]) == 0
    assert events == [
        ("route", "vehicle"),
        ("plate", "А111АА78"),
    ]


def test_phase1_keeps_tkinter_as_default_production_entrypoint():
    source = (
        Path(__file__).resolve().parents[1] / "pass_generator.py"
    ).read_text(encoding="utf-8")
    assert "from getpass_ui.app import App" in source
    assert "from getpass_qt" not in source
