from PySide6.QtWidgets import QPushButton, QTableView

from getpass_app.models.operation import PendingOperation
from getpass_qt.viewmodels.operations_viewmodel import OperationsViewModel
from getpass_qt.views.operations import OperationsPage


class FakePageOperationsService:
    def __init__(self):
        self.items = (
            PendingOperation(
                id="op1",
                journal_key="badge",
                journal_name="Журнал постоянных бейджей",
                created_at="2026-09-12T00:01:00",
                destination="/tmp/ready.pdf",
                document_status="Файл готов",
                document_path="/tmp/ready.pdf",
            ),
            PendingOperation(
                id="op2",
                journal_key="pass",
                journal_name="Журнал пропусков ТС",
                created_at="2026-09-12T00:02:00",
                destination="Printer",
                document_status="Прямая печать",
            ),
        )
        self.confirmed = []
        self.cancelled = []

    def pending(self):
        return self.items

    def confirm(self, ids):
        ids = tuple(ids)
        self.confirmed.append(ids)
        self.items = tuple(item for item in self.items if item.id not in ids)

    def cancel(self, ids):
        ids = tuple(ids)
        self.cancelled.append(ids)
        self.items = tuple(item for item in self.items if item.id not in ids)


def _page(qtbot):
    service = FakePageOperationsService()
    vm = OperationsViewModel(service)
    opened = []
    page = OperationsPage(
        vm,
        open_document=opened.append,
        confirm_action=lambda action, count: True,
    )
    qtbot.addWidget(page)
    page.show()
    return page, vm, service, opened


def test_operations_page_uses_qt_model_view_and_disables_actions_without_selection(qtbot):
    page, _, _, _ = _page(qtbot)

    assert page.findChild(QTableView, "OperationsTable") is page.table
    assert page.table.model().rowCount() == 2
    assert page.findChild(QPushButton, "OperationsConfirmButton").isEnabled() is False
    assert page.findChild(QPushButton, "OperationsCancelButton").isEnabled() is False
    assert page.findChild(QPushButton, "OperationsOpenButton").isEnabled() is False


def test_ready_file_selection_enables_open_and_uses_document_path(qtbot):
    page, _, _, opened = _page(qtbot)

    page.table.selectRow(0)
    qtbot.wait(1)

    assert page.open_button.isEnabled() is True
    page.open_button.click()
    assert opened == ["/tmp/ready.pdf"]


def test_direct_print_selection_keeps_open_disabled(qtbot):
    page, _, _, _ = _page(qtbot)

    page.table.selectRow(1)
    qtbot.wait(1)

    assert page.open_button.isEnabled() is False
    assert page.confirm_button.isEnabled() is True
    assert page.cancel_button.isEnabled() is True


def test_confirm_selected_delegates_to_viewmodel_and_removes_row(qtbot):
    page, _, service, _ = _page(qtbot)
    page.table.selectRow(0)
    qtbot.wait(1)

    page.confirm_button.click()
    qtbot.wait(1)

    assert service.confirmed == [("op1",)]
    assert page.table.model().rowCount() == 1
