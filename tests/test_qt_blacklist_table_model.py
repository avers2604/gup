from PySide6.QtCore import Qt

from getpass_app.models.blacklist import BlacklistEntry
from getpass_qt.models.blacklist_table_model import BlacklistTableModel


def entry(*, entry_id="abc123", plate="А111АА78", fio="ИВАНОВ И.И."):
    return BlacklistEntry(
        id=entry_id,
        plate=plate,
        fio=fio,
        incident="Нарушение режима",
        created_at="13.09.2026 12:30",
    )


def test_blacklist_table_model_exposes_operator_columns_and_id_role():
    model = BlacklistTableModel((entry(),))

    assert model.rowCount() == 1
    assert model.columnCount() == 4
    assert [
        model.headerData(i, Qt.Orientation.Horizontal)
        for i in range(model.columnCount())
    ] == ["Госномер", "ФИО", "Инцидент", "Дата"]

    assert model.data(model.index(0, 0)) == "А111АА78"
    assert model.data(model.index(0, 1)) == "ИВАНОВ И.И."
    assert model.data(model.index(0, 2)) == "Нарушение режима"
    assert model.data(model.index(0, 3)) == "13.09.2026 12:30"
    assert model.data(model.index(0, 0), Qt.ItemDataRole.UserRole) == "abc123"


def test_blacklist_table_model_can_replace_entries():
    model = BlacklistTableModel((entry(),))
    replacement = entry(entry_id="def456", plate="В222ВВ78")

    model.set_entries((replacement,))

    assert model.rowCount() == 1
    assert model.data(model.index(0, 0)) == "В222ВВ78"
    assert model.data(model.index(0, 0), Qt.ItemDataRole.UserRole) == "def456"
    assert model.entry(0) == replacement
