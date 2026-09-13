from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

_COLUMNS = (
    ("plate", "Госномер"),
    ("fio", "ФИО"),
    ("incident", "Инцидент"),
    ("created_at", "Дата"),
)


class BlacklistTableModel(QAbstractTableModel):
    def __init__(self, entries=(), parent=None) -> None:
        super().__init__(parent)
        self._entries = tuple(entries)

    def set_entries(self, entries) -> None:
        self.beginResetModel()
        self._entries = tuple(entries)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._entries)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(_COLUMNS):
            return _COLUMNS[section][1]
        if orientation == Qt.Orientation.Vertical:
            return section + 1
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        entry = self._entries[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return str(getattr(entry, _COLUMNS[index.column()][0]) or "")
        if role == Qt.ItemDataRole.UserRole:
            return entry.id
        return None

    def entry(self, index: int):
        return self._entries[index]
