from PIL import Image

from getpass_app.models.employee_badge import EmployeeBadgeState
from getpass_app.models.preferences import OperatorDefaults
from getpass_app.services.employee_badge_service import EmployeeBadgeWarnings
from getpass_qt.viewmodels.employee_badge_viewmodel import EmployeeBadgeViewModel
from getpass_qt.viewmodels.vehicle_pass_viewmodel import VehiclePassViewModel
from getpass_qt.views.vehicle_pass import VehiclePassPage


class VehicleService:
    @staticmethod
    def zones():
        return ()

    @staticmethod
    def brands():
        return ()

    @staticmethod
    def printers():
        return ("По умолчанию",)

    @staticmethod
    def render_preview(_data, _common):
        return Image.new("RGB", (100, 50), "white")


class BadgeService:
    @staticmethod
    def roles():
        return ()

    @staticmethod
    def printers():
        return ()

    @staticmethod
    def warnings(_state: EmployeeBadgeState):
        return EmployeeBadgeWarnings(
            duplicates=({"id": "duplicate"},),
            blacklist=({"id": "incident"},),
        )


def test_vehicle_page_uses_saved_preview_target(qtbot):
    defaults = OperatorDefaults(auto_preview_target="2")
    vm = VehiclePassViewModel(VehicleService(), defaults=defaults)
    page = VehiclePassPage(vm)
    qtbot.addWidget(page)

    assert vm.preview_target == "second"
    assert page.preview_target.currentData() == "second"


def test_employee_duplicate_preference_does_not_hide_blacklist_warning():
    defaults = OperatorDefaults(warn_duplicates=False)
    vm = EmployeeBadgeViewModel(BadgeService(), defaults=defaults)

    warnings = vm.warnings()

    assert warnings.duplicates == ()
    assert warnings.blacklist == ({"id": "incident"},)
