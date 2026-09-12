import pytest
from PIL import Image
from PySide6.QtCore import Qt

from getpass_app.models.journal import JournalField, JournalSnapshot
from getpass_app.services.settings_service import SettingsService
from getpass_qt.main_window import MainWindow
from getpass_qt.theme.manager import ThemeManager
from getpass_qt.viewmodels.employee_badge_viewmodel import EmployeeBadgeViewModel
from getpass_qt.viewmodels.journal_viewmodel import JournalViewModel
from getpass_qt.viewmodels.main_viewmodel import MainViewModel
from getpass_qt.viewmodels.operations_viewmodel import OperationsViewModel
from getpass_qt.viewmodels.vehicle_pass_viewmodel import VehiclePassViewModel
from getpass_qt.views.employee_badge import EmployeeBadgePage
from getpass_qt.views.journals import JournalsPage
from getpass_qt.views.operations import OperationsPage
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


class FakeNavigationEmployeeService:
    def roles(self):
        return ("ВОДИТЕЛЬ",)

    def printers(self):
        return ("По умолчанию",)

    def render_preview(self, data):
        return Image.new("RGB", (340, 216), "white")

    def warnings(self, state):
        raise AssertionError("navigation test must not query output warnings")

    def store_photo(self, image, tab_num):
        raise AssertionError("navigation test must not store photos")

    def save_pdf(self, state, path):
        raise AssertionError("navigation test must not save")

    def print_badge(self, state, printer):
        raise AssertionError("navigation test must not print")


class FakeNavigationJournalService:
    def journal_keys(self):
        return ("pass", "badge")

    def snapshot(self, journal_key, filters, **kwargs):
        return JournalSnapshot(
            journal_key=journal_key,
            journal_name="Тестовый журнал",
            fields=(JournalField("status", "Статус", 100),),
            rows=(),
            total_records=0,
            filtered_records=0,
            page=0,
            page_size=kwargs.get("page_size", 100),
            page_count=1,
        )

    def distinct(self, journal_key, key):
        return ()

    def update_record(self, *args):
        raise AssertionError("navigation test must not update journal")

    def revoke(self, *args):
        raise AssertionError("navigation test must not revoke journal")

    def history(self, *args):
        return ()

    def export(self, *args):
        raise AssertionError("navigation test must not export journal")

    def add_revoked_to_blacklist(self, *args):
        raise AssertionError("navigation test must not edit blacklist")


class FakeNavigationOperationsService:
    def pending(self):
        return ()

    def confirm(self, ids):
        raise AssertionError("navigation test must not confirm operations")

    def cancel(self, ids):
        raise AssertionError("navigation test must not cancel operations")


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
    employee_vm = EmployeeBadgeViewModel(FakeNavigationEmployeeService())
    journal_vm = JournalViewModel(FakeNavigationJournalService())
    operations_vm = OperationsViewModel(FakeNavigationOperationsService())
    return MainWindow(
        theme_manager=manager,
        vehicle_viewmodel=vehicle_vm,
        employee_badge_viewmodel=employee_vm,
        journal_viewmodel=journal_vm,
        operations_viewmodel=operations_vm,
    )


def test_main_window_has_variant_a_sidebar_and_stack(qapp, qtbot):
    window = _window(qapp)
    qtbot.addWidget(window)
    assert window.sidebar.objectName() == "Sidebar"
    assert window.stack.count() == 8
    assert window.active_route == "dashboard"
    assert isinstance(window.vehicle_page, VehiclePassPage)
    assert isinstance(window.employee_page, EmployeeBadgePage)
    assert isinstance(window.journals_page, JournalsPage)
    assert isinstance(window.operations_page, OperationsPage)


def test_sidebar_switches_to_vehicle_page(qapp, qtbot):
    window = _window(qapp)
    qtbot.addWidget(window)
    window.sidebar.request_route("vehicle")
    assert window.active_route == "vehicle"
    assert window.stack.currentWidget() is window.vehicle_page


def test_employee_route_uses_real_employee_badge_page(qapp, qtbot):
    window = _window(qapp)
    qtbot.addWidget(window)
    window.sidebar.request_route("employee")
    assert window.active_route == "employee"
    assert window.stack.currentWidget() is window.employee_page


def test_phase4_routes_use_real_journal_and_operations_pages(qapp, qtbot):
    window = _window(qapp)
    qtbot.addWidget(window)

    window.sidebar.request_route("journals")
    assert window.stack.currentWidget() is window.journals_page

    window.sidebar.request_route("operations")
    assert window.stack.currentWidget() is window.operations_page


def test_dashboard_primary_action_navigates_to_vehicle(qapp, qtbot):
    window = _window(qapp)
    qtbot.addWidget(window)
    qtbot.mouseClick(window.dashboard.vehicle_button, Qt.MouseButton.LeftButton)
    assert window.active_route == "vehicle"
    assert window.stack.currentWidget() is window.vehicle_page
