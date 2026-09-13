import pytest
from PySide6.QtTest import QSignalSpy

from getpass_app.models.preferences import OperatorDefaults
from getpass_qt.viewmodels.settings_viewmodel import SettingsViewModel


class FakeSettingsService:
    def __init__(self):
        self.saved = []
        self.error = None
        self.result = True

    def save_operator_defaults(self, defaults):
        if self.error:
            raise self.error
        self.saved.append(defaults)
        return self.result


def test_settings_viewmodel_starts_from_supplied_immutable_snapshot(qtbot):
    defaults = OperatorDefaults(territory="Площадка 1")
    vm = SettingsViewModel(FakeSettingsService(), defaults=defaults)

    assert vm.defaults is defaults


def test_settings_viewmodel_updates_known_field_and_emits_state(qtbot):
    vm = SettingsViewModel(FakeSettingsService(), defaults=OperatorDefaults())
    changed = QSignalSpy(vm.state_changed)

    vm.set_field("territory", "Площадка 2")

    assert vm.defaults.territory == "Площадка 2"
    assert changed.count() == 1


def test_settings_viewmodel_rejects_unknown_field():
    vm = SettingsViewModel(FakeSettingsService(), defaults=OperatorDefaults())

    with pytest.raises(ValueError, match="Unknown settings field"):
        vm.set_field("window_geometry", "secret")


def test_settings_viewmodel_saves_current_snapshot(qtbot):
    service = FakeSettingsService()
    vm = SettingsViewModel(service, defaults=OperatorDefaults())
    vm.set_field("last_pass_num", "777-26")
    success = QSignalSpy(vm.operation_succeeded)

    assert vm.save() is True

    assert service.saved == [vm.defaults]
    assert success.count() == 1


def test_settings_viewmodel_reports_save_failure(qtbot):
    service = FakeSettingsService()
    service.error = ValueError("Unsupported print_mode: x")
    vm = SettingsViewModel(service, defaults=OperatorDefaults())
    failed = QSignalSpy(vm.operation_failed)

    assert vm.save() is False

    assert failed.count() == 1
    assert "Unsupported print_mode" in failed.at(0)[0]
