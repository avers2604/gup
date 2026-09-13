from datetime import datetime

from getpass_app.models.batch import BatchReview
from getpass_app.models.preferences import OperatorDefaults
from getpass_app.services.employee_badge_service import EmployeeBadgeOutputResult
from getpass_qt.viewmodels.batch_viewmodel import BatchViewModel
from getpass_qt.viewmodels.employee_badge_viewmodel import EmployeeBadgeViewModel
from getpass_qt.viewmodels.vehicle_pass_viewmodel import VehiclePassViewModel


class VehicleService:
    @staticmethod
    def zones():
        return ()

    @staticmethod
    def brands():
        return ()

    @staticmethod
    def printers():
        return ()


class BadgeService:
    @staticmethod
    def roles():
        return ()

    @staticmethod
    def printers():
        return ()

    @staticmethod
    def warnings(_state):
        return None

    @staticmethod
    def save_pdf(_state, _path):
        return EmployeeBadgeOutputResult(next_tab_num="01036")


class BatchService:
    def __init__(self):
        self.pass_defaults = None
        self.badge_defaults = None

    @staticmethod
    def read_csv(_path):
        return (("row",),)

    def parse_pass_rows(self, _rows, defaults):
        self.pass_defaults = dict(defaults)
        return ()

    def parse_badge_rows(self, _rows, _folder, defaults):
        self.badge_defaults = dict(defaults)
        return ()

    @staticmethod
    def review(kind, _items):
        return BatchReview(kind=kind, rows=())


def custom_defaults():
    return OperatorDefaults(
        last_pass_num="777-26",
        territory="Площадка № 7",
        otb_post="Начальник ОТБ",
        otb_name="ПЕТРОВ П.П.",
        valid_until="31.12.2027",
        is_temporary_car=True,
        print_mode="a5",
        badge_park="ОСП «Трамвайный парк № 5»",
        badge_tab_num="01035",
        badge_print_mode="a4_single",
        print_pass_back=True,
    )


def test_vehicle_viewmodel_applies_persisted_operator_defaults():
    vm = VehiclePassViewModel(VehicleService(), defaults=custom_defaults())

    assert vm.state.first.num == "777-26"
    assert vm.state.first.territory == "Площадка № 7"
    assert vm.state.second.territory == "Площадка № 7"
    assert vm.state.common.valid_until == "31.12.2027"
    assert vm.state.common.is_temporary is True
    assert vm.state.common.otb_post == "Начальник ОТБ"
    assert vm.state.common.otb_name == "ПЕТРОВ П.П."
    assert vm.state.page_format == "a5"
    assert vm.state.print_back is True


def test_employee_viewmodel_applies_badge_defaults_and_preserves_them_after_issue():
    defaults = custom_defaults()
    vm = EmployeeBadgeViewModel(
        BadgeService(),
        defaults=defaults,
        now=lambda: datetime(2026, 9, 13),
    )

    assert vm.state.data.tab_num == "01035"
    assert vm.state.data.park == "ОСП «Трамвайный парк № 5»"
    assert vm.state.print_mode == "a4_single"

    vm.set_field("role", "Водитель")
    vm.set_field("surname", "Иванов")
    vm.set_field("name", "Иван")
    vm.set_field("photo_path", "/tmp/photo.jpg")
    assert vm.save_pdf("badge.pdf") is True

    assert vm.state.data.tab_num == "01036"
    assert vm.state.data.park == "ОСП «Трамвайный парк № 5»"
    assert vm.state.print_mode == "a4_single"


def test_batch_viewmodel_uses_operator_defaults_for_both_import_kinds(tmp_path):
    service = BatchService()
    vm = BatchViewModel(service, defaults=custom_defaults())

    assert vm.load_csv(str(tmp_path / "passes.csv")) is True
    assert service.pass_defaults["valid_until"] == "31.12.2027"
    assert service.pass_defaults["otb_post"] == "Начальник ОТБ"
    assert service.pass_defaults["otb_name"] == "ПЕТРОВ П.П."
    assert service.pass_defaults["is_temporary"] is True

    vm.set_kind("badge")
    assert vm.load_csv(str(tmp_path / "badges.csv")) is True
    assert service.badge_defaults["park"] == "ОСП «Трамвайный парк № 5»"
