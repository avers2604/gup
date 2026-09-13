from getpass_app.models.operation import PendingOperation
from getpass_qt.viewmodels.operations_viewmodel import OperationsViewModel


class FakeOperationsService:
    def __init__(self):
        self.items = (
            PendingOperation(
                id="op1",
                journal_key="pass",
                journal_name="Журнал пропусков ТС",
                created_at="2026-09-12T00:00:00",
                destination="Printer",
                document_status="Прямая печать",
            ),
        )
        self.confirmed = []
        self.cancelled = []
        self.fail_pending = False

    def pending(self):
        if self.fail_pending:
            raise RuntimeError("db unavailable")
        return self.items

    def confirm(self, ids):
        self.confirmed.append(tuple(ids))
        self.items = ()

    def cancel(self, ids):
        self.cancelled.append(tuple(ids))
        self.items = ()


def test_operations_viewmodel_loads_pending_on_init(qtbot):
    service = FakeOperationsService()
    vm = OperationsViewModel(service)

    assert [item.id for item in vm.operations] == ["op1"]


def test_confirm_delegates_and_refreshes(qtbot):
    service = FakeOperationsService()
    vm = OperationsViewModel(service)
    messages = []
    vm.operation_succeeded.connect(messages.append)

    assert vm.confirm(["op1"]) is True

    assert service.confirmed == [("op1",)]
    assert vm.operations == ()
    assert messages == ["Операция подтверждена."]


def test_cancel_delegates_and_refreshes(qtbot):
    service = FakeOperationsService()
    vm = OperationsViewModel(service)

    assert vm.cancel(["op1"]) is True

    assert service.cancelled == [("op1",)]
    assert vm.operations == ()


def test_refresh_error_preserves_last_operations(qtbot):
    service = FakeOperationsService()
    vm = OperationsViewModel(service)
    previous = vm.operations
    service.fail_pending = True
    messages = []
    vm.operation_failed.connect(messages.append)

    assert vm.refresh() is False

    assert vm.operations is previous
    assert messages == ["db unavailable"]
