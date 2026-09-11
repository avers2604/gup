import pytest
from PIL import Image
from PySide6.QtCore import Qt

from getpass_app.services.settings_service import SettingsService
from getpass_qt.main_window import MainWindow
from getpass_qt.theme.manager import ThemeManager
from getpass_qt.viewmodels.main_viewmodel import MainViewModel
from getpass_qt.viewmodels.vehicle_pass_viewmodel import VehiclePassViewModel
from getpass_qt.views.vehicle_pass import VehiclePassPage


class FakeNavigationVehicleService:
    def lookup_vehicle(self, plate):
        return None

    def render_preview(self, data, common):
        return Image.new("RGB", (400, 200), "white")

    def save_pdf(self, state, path):
        raise AssertionError("navigation test must not save")

    def print_passes(self, state, printer, *, confirm_flip=None):
        raise AssertionError("navigation test must not print")

    def zones(self):
        return ("Парковка",)

    def brands(self):
        return ("Лада",)

    def printers(self):
        return ("По умолчанию",)


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
    vehicle_vm = VehiclePassViewModel(FakeNavigationVehicleService())
    return MainWindow(
        theme_manager=manager,
        vehicle_viewmodel=vehicle_vm,
    )


def test_main_window_has_variant_a_sidebar_and_stack(qapp, qtbot):
    window = _window(qapp)
    qtbot.addWidget(window)
    assert window.sidebar.objectName() == "Sidebar"
    assert window.stack.count() == 8
    assert window.active_route == "dashboard"
    assert isinstance(window.vehicle_page, VehiclePassPage)


def test_sidebar_switches_to_vehicle_page(qapp, qtbot):
    window = _window(qapp)
    qtbot.addWidget(window)
    window.sidebar.request_route("vehicle")
    assert window.active_route == "vehicle"
    assert window.stack.currentWidget() is window.vehicle_page


def test_dashboard_primary_action_navigates_to_vehicle(qapp, qtbot):
    window = _window(qapp)
    qtbot.addWidget(window)
    qtbot.mouseClick(window.dashboard.vehicle_button, Qt.MouseButton.LeftButton)
    assert window.active_route == "vehicle"
    assert window.stack.currentWidget() is window.vehicle_page
