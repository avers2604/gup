from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

_COLUMNS = (
    ("created_at", "Создано"),
    ("journal_name", "Журнал"),
    ("destination", "Назначение"),
    ("document_status", "Документ"),
)


class OperationsTableModel(QAbstractTableModel):
    def __init__(self, operations=(), parent=None) -> None:
        super().__init__(parent)
        self._operations = tuple(operations)

    def set_operations(self, operations) -> None:
        self.beginResetModel()
        self._operations = tuple(operations)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._operations)

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
        operation = self._operations[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return str(getattr(operation, _COLUMNS[index.column()][0]) or "")
        if role == Qt.ItemDataRole.UserRole:
            return operation.id
        return None

    def operation(self, index: int):
        return self._operations[index]
