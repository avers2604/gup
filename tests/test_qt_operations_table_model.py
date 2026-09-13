from PySide6.QtCore import Qt

from getpass_app.models.operation import PendingOperation
from getpass_qt.models.operations_table_model import OperationsTableModel


def _operations():
    return (
        PendingOperation(
            id="op1",
            journal_key="pass",
            journal_name="Журнал пропусков ТС",
            created_at="2026-09-12T00:00:00",
            destination="HP LaserJet",
            document_status="Прямая печать",
        ),
        PendingOperation(
            id="op2",
            journal_key="badge",
            journal_name="Журнал постоянных бейджей",
            created_at="2026-09-12T00:01:00",
            destination="/tmp/badge.pdf",
            document_status="Файл готов",
            document_path="/tmp/badge.pdf",
        ),
    )


def test_operations_table_model_exposes_columns_and_operation_identity():
    model = OperationsTableModel(_operations())

    assert model.rowCount() == 2
    assert model.columnCount() == 4
    assert [
        model.headerData(i, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        for i in range(model.columnCount())
    ] == ["Создано", "Журнал", "Назначение", "Документ"]
    assert model.data(model.index(0, 3), Qt.ItemDataRole.DisplayRole) == "Прямая печать"
    assert model.data(model.index(1, 0), Qt.ItemDataRole.UserRole) == "op2"
    assert model.operation(1).document_path == "/tmp/badge.pdf"


def test_operations_table_model_can_reset_rows():
    model = OperationsTableModel(_operations())

    model.set_operations((_operations()[1],))

    assert model.rowCount() == 1
    assert model.data(model.index(0, 1)) == "Журнал постоянных бейджей"
