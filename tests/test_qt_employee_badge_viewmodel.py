from datetime import datetime

from PIL import Image
from PySide6.QtTest import QSignalSpy

from getpass_app.services.employee_badge_service import (
    EmployeeBadgeOutputError,
    EmployeeBadgeOutputResult,
    EmployeeBadgeWarnings,
)
from getpass_qt.viewmodels.employee_badge_viewmodel import EmployeeBadgeViewModel


class FakeBadgeService:
    def __init__(self):
        self.preview_calls = 0
        self.photo_calls = []
        self.saved = []
        self.printed = []
        self.warning_calls = 0
        self.fail_output = False

    @staticmethod
    def roles():
        return ("Водитель", "Слесарь")

    @staticmethod
    def printers():
        return ("Printer A",)

    def warnings(self, _state):
        self.warning_calls += 1
        return EmployeeBadgeWarnings(
            duplicates=({"tab_num": "01035"},),
            blacklist=({"incident": "test"},),
        )

    def render_preview(self, _data):
        self.preview_calls += 1
        return Image.new("RGB", (850, 540), "white")

    def store_photo(self, image, tab_num):
        self.photo_calls.append((image, tab_num))
        return "/tmp/cropped.jpg"

    def save_pdf(self, state, path):
        self.saved.append((state, path))
        if self.fail_output:
            raise EmployeeBadgeOutputError("disk")
        return EmployeeBadgeOutputResult(next_tab_num="01036")

    def print_badge(self, state, printer):
        self.printed.append((state, printer))
        if self.fail_output:
            raise EmployeeBadgeOutputError("printer")
        return EmployeeBadgeOutputResult(next_tab_num="01036")


def make_viewmodel():
    service = FakeBadgeService()
    viewmodel = EmployeeBadgeViewModel(
        service,
        now=lambda: datetime(2026, 9, 12),
    )
    return viewmodel, service


def fill_valid(viewmodel):
    values = {
        "tab_num": "01035",
        "park": 'ОСП «Трамвайный парк № 5»',
        "role": "Водитель",
        "surname": "Иванов",
        "name": "Иван",
        "patronymic": "Иванович",
        "phone": "+79990000000",
        "photo_path": "/tmp/photo.jpg",
    }
    for field, value in values.items():
        viewmodel.set_field(field, value)


def test_initial_dates_match_legacy_five_year_default(qtbot):
    viewmodel, _service = make_viewmodel()

    assert viewmodel.state.data.issue_date == "12.09.2026"
    assert viewmodel.state.data.valid_until == "12.09.2031"


def test_name_fields_are_normalized_to_uppercase(qtbot):
    viewmodel, _service = make_viewmodel()

    viewmodel.set_field("surname", "Иванов")
    viewmodel.set_field("name", "Иван")
    viewmodel.set_field("patronymic", "Иванович")

    assert viewmodel.state.data.surname == "ИВАНОВ"
    assert viewmodel.state.data.name == "ИВАН"
    assert viewmodel.state.data.patronymic == "ИВАНОВИЧ"


def test_plus_five_years_uses_issue_date(qtbot):
    viewmodel, _service = make_viewmodel()
    viewmodel.set_field("issue_date", "29.02.2028")

    assert viewmodel.set_years(5) is True
    assert viewmodel.state.data.valid_until == "28.02.2033"


def test_roles_printers_and_warnings_are_delegated(qtbot):
    viewmodel, service = make_viewmodel()

    assert viewmodel.roles() == ("Водитель", "Слесарь")
    assert viewmodel.printers() == ("Printer A",)
    warnings = viewmodel.warnings()
    assert warnings.duplicates
    assert warnings.blacklist
    assert service.warning_calls == 1


def test_store_photo_updates_state_and_emits_state_change(qtbot):
    viewmodel, service = make_viewmodel()
    viewmodel.set_field("tab_num", "01035")
    spy = QSignalSpy(viewmodel.state_changed)
    image = Image.new("RGB", (300, 400), "white")

    path = viewmodel.store_photo(image)

    assert path == "/tmp/cropped.jpg"
    assert service.photo_calls == [(image, "01035")]
    assert viewmodel.state.data.photo_path == path
    assert spy.count() == 1


def test_preview_is_delegated_to_service(qtbot):
    viewmodel, service = make_viewmodel()
    spy = QSignalSpy(viewmodel.preview_changed)

    image = viewmodel.refresh_preview()

    assert service.preview_calls == 1
    assert image.size == (850, 540)
    assert spy.count() == 1


def test_successful_save_clears_employee_but_keeps_next_tab_and_park(qtbot):
    viewmodel, service = make_viewmodel()
    fill_valid(viewmodel)

    assert viewmodel.save_pdf("badge.pdf") is True

    assert len(service.saved) == 1
    assert viewmodel.state.data.tab_num == "01036"
    assert viewmodel.state.data.park == 'ОСП «Трамвайный парк № 5»'
    assert viewmodel.state.data.role == ""
    assert viewmodel.state.data.surname == ""
    assert viewmodel.state.data.photo_path == ""
    assert viewmodel.state.data.issue_date == "12.09.2026"
    assert viewmodel.state.data.valid_until == "12.09.2031"


def test_output_error_emits_failure_without_clearing_state(qtbot):
    viewmodel, service = make_viewmodel()
    fill_valid(viewmodel)
    service.fail_output = True
    failure = QSignalSpy(viewmodel.operation_failed)

    assert viewmodel.print_badge("Printer A") is False

    assert failure.count() == 1
    assert viewmodel.state.data.surname == "ИВАНОВ"
    assert viewmodel.state.data.photo_path == "/tmp/photo.jpg"


def test_invalid_state_blocks_output_before_service(qtbot):
    viewmodel, service = make_viewmodel()

    assert viewmodel.save_pdf("badge.pdf") is False

    assert service.saved == []
