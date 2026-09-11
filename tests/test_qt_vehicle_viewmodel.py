from PySide6.QtTest import QSignalSpy

from getpass_qt.viewmodels.vehicle_pass_viewmodel import VehiclePassViewModel


class FakeVehicleService:
    def __init__(self):
        self.lookup_result = None
        self.preview_result = object()
        self.preview_calls = []
        self.saved = []
        self.printed = []

    def lookup_vehicle(self, plate):
        return self.lookup_result

    def render_preview(self, data, common):
        self.preview_calls.append((data, common))
        return self.preview_result

    def save_pdf(self, state, path):
        self.saved.append((state, path))

    def print_passes(self, state, printer, *, confirm_flip=None):
        self.printed.append((state, printer, confirm_flip))

    def zones(self):
        return ('ПТО "Шаврова"', "Парковка")

    def brands(self):
        return ("Лада", "Volvo")


def test_defaults_match_phase2_vehicle_output():
    vm = VehiclePassViewModel(FakeVehicleService())

    assert vm.state.page_format == "a4"
    assert vm.state.print_back is False
    assert vm.state.first.plate == ""
    assert vm.state.second.plate == ""


def test_set_plate_uppercases_input_and_emits_state_change(qtbot):
    vm = VehiclePassViewModel(FakeVehicleService())
    spy = QSignalSpy(vm.state_changed)

    vm.set_pass_field("first", "plate", "а111аа78")

    assert vm.state.first.plate == "А111АА78"
    assert spy.count() == 1


def test_autocomplete_fills_only_blank_vehicle_fields():
    service = FakeVehicleService()
    service.lookup_result = {
        "brand": "Лада",
        "model": "Веста",
        "type": "легковой",
        "color": "белый",
    }
    vm = VehiclePassViewModel(service)
    vm.set_pass_field("first", "plate", "А111АА78")
    vm.set_pass_field("first", "brand", "Уже введено")
    vm.set_pass_field("first", "driver_name", "Новый водитель")
    vm.set_pass_field("first", "phone", "+7 999 000-00-00")
    vm.set_pass_field("first", "territory", "Парковка")

    assert vm.autocomplete_vehicle("first") is True

    assert vm.state.first.brand == "Уже введено"
    assert vm.state.first.model == "Веста"
    assert vm.state.first.vehicle_type == "легковой"
    assert vm.state.first.color == "белый"
    assert vm.state.first.driver_name == "Новый водитель"
    assert vm.state.first.phone == "+7 999 000-00-00"
    assert vm.state.first.territory == "Парковка"


def test_sync_second_number_uses_existing_domain_incrementer():
    vm = VehiclePassViewModel(FakeVehicleService())
    vm.set_pass_field("first", "num", "100-26")

    vm.sync_second_number()

    assert vm.state.second.num == "101-26"


def test_preview_result_is_emitted_unchanged():
    service = FakeVehicleService()
    vm = VehiclePassViewModel(service)
    spy = QSignalSpy(vm.preview_changed)

    result = vm.refresh_preview("first")

    assert result is service.preview_result
    assert spy.count() == 1
    assert spy.at(0)[0] is service.preview_result


def test_invalid_save_stops_before_service_output_and_emits_validation():
    service = FakeVehicleService()
    vm = VehiclePassViewModel(service)
    validation_spy = QSignalSpy(vm.validation_changed)
    failure_spy = QSignalSpy(vm.operation_failed)

    assert vm.save_pdf("out.pdf") is False

    assert service.saved == []
    assert validation_spy.count() == 1
    issues = validation_spy.at(0)[0]
    assert issues[0].field == "first.plate"
    assert failure_spy.count() == 1


def test_valid_save_delegates_snapshot_and_reports_success():
    service = FakeVehicleService()
    vm = VehiclePassViewModel(service)
    vm.set_pass_field("first", "plate", "А111АА78")
    success_spy = QSignalSpy(vm.operation_succeeded)

    assert vm.save_pdf("out.pdf") is True

    assert len(service.saved) == 1
    assert service.saved[0][0] == vm.state
    assert service.saved[0][1] == "out.pdf"
    assert success_spy.count() == 1


def test_format_change_preserves_second_pass_and_reaches_output_service():
    service = FakeVehicleService()
    vm = VehiclePassViewModel(service)
    vm.set_pass_field("first", "plate", "А111АА78")
    vm.set_pass_field("second", "plate", "В222ВВ78")
    vm.set_page_format("a5")

    assert vm.state.second.plate == "В222ВВ78"
    assert vm.save_pdf("out.pdf") is True
    assert service.saved[0][0].page_format == "a5"
