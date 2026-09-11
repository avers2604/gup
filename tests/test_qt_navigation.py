import pytest

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
