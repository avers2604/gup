from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from getpass_qt.viewmodels.vehicle_pass_viewmodel import VehiclePassViewModel
from getpass_qt.views.vehicle_pass import VehiclePassPage
from getpass_qt.widgets.image_preview import ImagePreview


class FakePageService:
    def __init__(self):
        self.lookup_result = None
        self.preview_image = Image.new("RGB", (400, 200), "white")
        self.preview_calls = []
        self.saved = []
        self.printed = []

    def lookup_vehicle(self, plate):
        return self.lookup_result

    def render_preview(self, data, common):
        self.preview_calls.append((data, common))
        return self.preview_image

    def save_pdf(self, state, path):
        self.saved.append((state, path))

    def print_passes(self, state, printer, *, confirm_flip=None):
        self.printed.append((state, printer, confirm_flip))

    def zones(self):
        return ('ПТО "Шаврова"', "Парковка")

    def brands(self):
        return ("Лада", "Volvo")

    def printers(self):
        return ("По умолчанию", "Office Printer")


def make_page(qtbot):
    service = FakePageService()
    vm = VehiclePassViewModel(service)
    page = VehiclePassPage(
        vm,
        save_dialog=lambda: "out.pdf",
    )
    qtbot.addWidget(page)
    page.resize(1180, 760)
    page.show()
    return page, vm, service


def test_image_preview_accepts_pil_image_and_preserves_aspect_ratio(qtbot):
    preview = ImagePreview()
    qtbot.addWidget(preview)
    preview.resize(240, 240)
    preview.show()

    image = Image.new("RGB", (400, 200), "white")
    preview.set_pil_image(image)
    qtbot.wait(10)

    pixmap = preview.image_label.pixmap()
    assert preview.has_image is True
    assert pixmap is not None
    assert not pixmap.isNull()
    assert pixmap.width() <= preview.image_label.width()
    assert pixmap.height() <= preview.image_label.height()
    assert abs((pixmap.width() / pixmap.height()) - 2.0) < 0.05


def test_image_preview_rescales_from_original_on_resize(qtbot):
    preview = ImagePreview()
    qtbot.addWidget(preview)
    image = Image.new("RGB", (600, 300), "white")
    preview.resize(180, 140)
    preview.show()
    preview.set_pil_image(image)
    qtbot.wait(10)
    first_size = preview.image_label.pixmap().size()

    preview.resize(360, 280)
    qtbot.wait(10)
    second_size = preview.image_label.pixmap().size()

    assert second_size.width() >= first_size.width()
    assert second_size.height() >= first_size.height()
    assert image.size == (600, 300)


def test_image_preview_none_clears_pixmap_and_shows_empty_state(qtbot):
    preview = ImagePreview()
    qtbot.addWidget(preview)
    preview.set_pil_image(Image.new("RGB", (100, 50), "white"))

    preview.set_pil_image(None)

    pixmap = preview.image_label.pixmap()
    assert preview.has_image is False
    assert pixmap is None or pixmap.isNull()
    assert "предпросмотр" in preview.image_label.text().lower()
    assert preview.image_label.alignment() & Qt.AlignmentFlag.AlignCenter


def test_vehicle_page_has_variant_a_structure(qtbot):
    page, vm, service = make_page(qtbot)

    assert page.objectName() == "VehiclePassPage"
    assert page.slot_tabs.objectName() == "PassSlotTabs"
    assert page.preview.objectName() == "VehiclePreview"
    assert page.save_button.objectName() == "SavePdfButton"
    assert page.print_button.objectName() == "PrintButton"
    assert page.print_settings.objectName() == "PrintSettings"
    assert page.slot_tabs.count() == 2
    assert page.slot_tabs.tabText(0) == "Пропуск №1"
    assert page.slot_tabs.tabText(1) == "Пропуск №2"
    assert page.preview_target.count() == 2

    expected_fields = {
        "num",
        "plate",
        "brand",
        "model",
        "vehicle_type",
        "color",
        "driver_position",
        "driver_name",
        "phone",
        "territory",
    }
    assert set(page.pass_fields["first"]) == expected_fields
    assert set(page.pass_fields["second"]) == expected_fields
    assert set(page.common_fields) == {
        "issue_date",
        "valid_until",
        "is_temporary",
        "otb_post",
        "otb_name",
    }

    button_texts = {button.text() for button in page.findChildren(QPushButton)}
    assert "Напечатать" in button_texts
    assert "Сохранить PDF" in button_texts
    assert "Массовая печать" not in button_texts
    assert "Журнал" not in button_texts
    assert "Выгрузить таблицу" not in button_texts


def test_editing_plate_updates_viewmodel(qtbot):
    page, vm, service = make_page(qtbot)

    page.pass_fields["first"]["plate"].setText("а111аа78")

    assert vm.state.first.plate == "А111АА78"


def test_preview_rendering_is_debounced_during_typing(qtbot):
    page, vm, service = make_page(qtbot)
    initial_calls = len(service.preview_calls)
    plate = page.pass_fields["first"]["plate"]

    plate.setText("А")
    plate.setText("А1")
    plate.setText("А11")

    assert len(service.preview_calls) == initial_calls
    qtbot.wait(200)
    assert len(service.preview_calls) == initial_calls + 1


def test_plate_editing_finished_autocompletes_vehicle_only(qtbot):
    page, vm, service = make_page(qtbot)
    service.lookup_result = {
        "brand": "Лада",
        "model": "Веста",
        "type": "легковой",
        "color": "белый",
    }
    vm.set_pass_field("first", "driver_name", "Новый водитель")
    vm.set_pass_field("first", "phone", "+7 999 000-00-00")
    vm.set_pass_field("first", "territory", "Парковка")

    plate = page.pass_fields["first"]["plate"]
    plate.setText("А111АА78")
    plate.editingFinished.emit()
    qtbot.wait(10)

    assert page.pass_fields["first"]["brand"].text() == "Лада"
    assert page.pass_fields["first"]["model"].text() == "Веста"
    assert page.pass_fields["first"]["vehicle_type"].text() == "легковой"
    assert page.pass_fields["first"]["color"].text() == "белый"
    assert vm.state.first.driver_name == "Новый водитель"
    assert vm.state.first.phone == "+7 999 000-00-00"
    assert vm.state.first.territory == "Парковка"


def test_validation_marks_plate_field_semantically_invalid(qtbot):
    page, vm, service = make_page(qtbot)

    vm.validate()
    qtbot.wait(10)

    assert page.pass_fields["first"]["plate"].property("invalid") is True


def test_preview_signal_updates_image_preview(qtbot):
    page, vm, service = make_page(qtbot)

    vm.refresh_preview("first")
    qtbot.wait(10)

    assert page.preview.has_image is True


def test_print_button_delegates_to_viewmodel_service(qtbot):
    page, vm, service = make_page(qtbot)
    page.pass_fields["first"]["plate"].setText("А111АА78")
    page.printer_combo.setCurrentText("Office Printer")

    qtbot.mouseClick(page.print_button, Qt.MouseButton.LeftButton)

    assert len(service.printed) == 1
    assert service.printed[0][1] == "Office Printer"


def test_save_button_uses_injected_file_dialog(qtbot):
    page, vm, service = make_page(qtbot)
    page.pass_fields["first"]["plate"].setText("А111АА78")

    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)

    assert len(service.saved) == 1
    assert service.saved[0][1] == "out.pdf"
