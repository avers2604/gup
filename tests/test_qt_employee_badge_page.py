from datetime import datetime

from PIL import Image
from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton

from getpass_app.services.employee_badge_service import (
    EmployeeBadgeOutputResult,
    EmployeeBadgeWarnings,
)
from getpass_qt.viewmodels.employee_badge_viewmodel import EmployeeBadgeViewModel
from getpass_qt.views.employee_badge import EmployeeBadgePage
from getpass_qt.widgets.image_preview import ImagePreview


class FakePageService:
    def __init__(self):
        self.preview_calls = 0
        self.saved = []
        self.printed = []
        self.warning_value = EmployeeBadgeWarnings()
        self.stored_photos = []

    @staticmethod
    def roles():
        return ("Водитель", "Слесарь")

    @staticmethod
    def printers():
        return ("Printer A", "Printer B")

    def warnings(self, _state):
        return self.warning_value

    def render_preview(self, _data):
        self.preview_calls += 1
        return Image.new("RGB", (850, 540), "white")

    def store_photo(self, image, tab_num):
        self.stored_photos.append((image, tab_num))
        return "/tmp/cropped.jpg"

    def save_pdf(self, state, path):
        self.saved.append((state, path))
        return EmployeeBadgeOutputResult(next_tab_num="01036")

    def print_badge(self, state, printer):
        self.printed.append((state, printer))
        return EmployeeBadgeOutputResult(next_tab_num="01036")


def make_page(qtbot, **overrides):
    service = FakePageService()
    viewmodel = EmployeeBadgeViewModel(
        service,
        now=lambda: datetime(2026, 9, 12),
    )
    confirmations = []

    def confirm_warning(kind, items):
        confirmations.append((kind, tuple(items)))
        return overrides.get("confirm_result", True)

    page = EmployeeBadgePage(
        viewmodel,
        open_image=overrides.get("open_image", lambda: None),
        crop_image=overrides.get("crop_image", lambda image, _parent: image),
        save_dialog=overrides.get("save_dialog", lambda _prefix: "badge.pdf"),
        confirm_warning=confirm_warning,
    )
    qtbot.addWidget(page)
    return page, viewmodel, service, confirmations


def fill_required(page):
    page.tab_num_edit.setText("01035")
    page.role_combo.setCurrentText("Водитель")
    page.surname_edit.setText("Иванов")
    page.name_edit.setText("Иван")
    page.photo_path = "/tmp/photo.jpg"
    page._viewmodel.set_field("photo_path", page.photo_path)


def test_employee_page_contains_operator_workflow(qtbot):
    page, _viewmodel, _service, _confirmations = make_page(qtbot)

    assert page.findChild(QLineEdit, "badge_surname") is page.surname_edit
    assert page.findChild(QLineEdit, "badge_name") is page.name_edit
    assert page.findChild(QComboBox, "BadgeRole") is page.role_combo
    assert page.findChild(QPushButton, "BadgePhotoButton") is page.photo_button
    assert page.findChild(ImagePreview, "BadgePreview") is page.preview
    assert page.findChild(QPushButton, "BadgePrintButton").text() == "Напечатать"
    assert page.findChild(QPushButton, "BadgeSavePdfButton").text() == "Сохранить PDF"


def test_employee_page_exposes_three_legacy_print_modes(qtbot):
    page, _viewmodel, _service, _confirmations = make_page(qtbot)

    assert [page.mode_combo.itemData(i) for i in range(page.mode_combo.count())] == [
        "card",
        "a4_grid",
        "a4_single",
    ]


def test_badge_preview_is_debounced_during_typing(qtbot):
    page, _viewmodel, service, _confirmations = make_page(qtbot)
    initial = service.preview_calls

    page.surname_edit.setText("И")
    page.surname_edit.setText("ИВ")
    page.surname_edit.setText("ИВА")

    assert service.preview_calls == initial
    qtbot.wait(180)
    assert service.preview_calls == initial + 1


def test_photo_selection_crops_and_persists_photo(qtbot):
    source = Image.new("RGB", (1200, 1600), "white")
    cropped = Image.new("RGB", (300, 400), "white")
    page, viewmodel, service, _confirmations = make_page(
        qtbot,
        open_image=lambda: source,
        crop_image=lambda image, _parent: cropped if image is source else None,
    )
    page.tab_num_edit.setText("01035")

    page.photo_button.click()

    assert service.stored_photos == [(cropped, "01035")]
    assert viewmodel.state.data.photo_path == "/tmp/cropped.jpg"
    assert "выбрано" in page.photo_status.text().lower()


def test_plus_five_year_button_updates_valid_until(qtbot):
    page, _viewmodel, _service, _confirmations = make_page(qtbot)
    page.issue_edit.setText("29.02.2028")

    page.five_year_button.click()

    assert page.valid_until_edit.text() == "28.02.2033"


def test_duplicate_warning_can_cancel_save_before_output(qtbot):
    page, _viewmodel, service, confirmations = make_page(
        qtbot,
        confirm_result=False,
    )
    fill_required(page)
    service.warning_value = EmployeeBadgeWarnings(
        duplicates=({"tab_num": "01035", "fio": "ИВАНОВ ИВАН"},),
    )

    page.save_button.click()

    assert confirmations[0][0] == "duplicates"
    assert service.saved == []


def test_blacklist_warning_can_cancel_print_before_output(qtbot):
    page, _viewmodel, service, confirmations = make_page(
        qtbot,
        confirm_result=False,
    )
    fill_required(page)
    service.warning_value = EmployeeBadgeWarnings(
        blacklist=({"incident": "test"},),
    )

    page.print_button.click()

    assert confirmations[0][0] == "blacklist"
    assert service.printed == []


def test_confirmed_warnings_allow_pdf_save(qtbot):
    page, _viewmodel, service, confirmations = make_page(qtbot)
    fill_required(page)
    service.warning_value = EmployeeBadgeWarnings(
        duplicates=({"tab_num": "01035"},),
        blacklist=({"incident": "test"},),
    )

    page.save_button.click()

    assert [item[0] for item in confirmations] == ["duplicates", "blacklist"]
    assert len(service.saved) == 1
    assert service.saved[0][1] == "badge.pdf"


def test_print_mode_and_printer_bind_to_viewmodel_output(qtbot):
    page, _viewmodel, service, _confirmations = make_page(qtbot)
    fill_required(page)
    page.mode_combo.setCurrentIndex(page.mode_combo.findData("a4_single"))
    page.printer_combo.setCurrentText("Printer B")

    page.print_button.click()

    assert len(service.printed) == 1
    state, printer = service.printed[0]
    assert state.print_mode == "a4_single"
    assert printer == "Printer B"
