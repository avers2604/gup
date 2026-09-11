import pytest
from PySide6.QtCore import Qt

from getpass_app.services.settings_service import SettingsService
from getpass_qt.main_window import MainWindow
from getpass_qt.theme.manager import ThemeManager
from getpass_qt.viewmodels.main_viewmodel import MainViewModel


def test_main_viewmodel_defaults_to_dashboard(qtbot):
    vm = MainViewModel()
    assert vm.active_route == "dashboard"


def test_main_viewmodel_emits_valid_route(qtbot):
    vm = MainViewModel()
    with qtbot.waitSignal(vm.route_changed, timeout=1000) as signal:
        vm.set_route("vehicle")
    assert signal.args == ["vehicle"]
    assert vm.active_route == "vehicle"


def test_main_viewmodel_rejects_unknown_route():
    vm = MainViewModel()
    with pytest.raises(ValueError, match="Unknown route"):
        vm.set_route("unknown")


def _window(qapp):
    service = SettingsService(
        load=lambda: {"theme": "light"},
        save=lambda values: True,
    )
    manager = ThemeManager(qapp, service)
    manager.load()
    return MainWindow(theme_manager=manager)


def test_main_window_has_variant_a_sidebar_and_stack(qapp, qtbot):
    window = _window(qapp)
    qtbot.addWidget(window)
    assert window.sidebar.objectName() == "Sidebar"
    assert window.stack.count() == 8
    assert window.active_route == "dashboard"


def test_sidebar_switches_to_vehicle_page(qapp, qtbot):
    window = _window(qapp)
    qtbot.addWidget(window)
    window.sidebar.request_route("vehicle")
    assert window.active_route == "vehicle"


def test_dashboard_primary_action_navigates_to_vehicle(qapp, qtbot):
    window = _window(qapp)
    qtbot.addWidget(window)
    qtbot.mouseClick(window.dashboard.vehicle_button, Qt.MouseButton.LeftButton)
    assert window.active_route == "vehicle"
