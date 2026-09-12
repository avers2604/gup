from PySide6.QtCore import Qt

from getpass_app.models.journal import JournalField, JournalRow, JournalSnapshot
from getpass_qt.models.journal_table_model import JournalTableModel


def _snapshot():
    return JournalSnapshot(
        journal_key="pass",
        journal_name="Журнал пропусков ТС",
        fields=(
            JournalField("id", "ID", 0),
            JournalField("plate", "Номер машины", 110, "center"),
            JournalField("status", "Статус", 115, "center"),
        ),
        rows=(
            JournalRow(
                id="p1",
                values={"id": "p1", "plate": "А111АА78", "status": "действует"},
                state="expired",
            ),
        ),
        total_records=1,
        filtered_records=1,
        page=0,
        page_size=100,
        page_count=1,
    )


def test_table_model_uses_only_visible_schema_fields():
    model = JournalTableModel(_snapshot())

    assert model.rowCount() == 1
    assert model.columnCount() == 2
    assert model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "Номер машины"
    assert model.headerData(1, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "Статус"


def test_table_model_exposes_computed_status_and_identity_roles():
    model = JournalTableModel(_snapshot())
    plate = model.index(0, 0)
    status = model.index(0, 1)

    assert model.data(plate, Qt.ItemDataRole.DisplayRole) == "А111АА78"
    assert model.data(status, Qt.ItemDataRole.DisplayRole) == "просрочен"
    assert model.data(plate, Qt.ItemDataRole.UserRole) == "p1"
    assert model.data(status, Qt.ItemDataRole.UserRole + 1) == "expired"
    assert model.row(0).id == "p1"
