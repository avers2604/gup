from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from getpass_app.models.journal import JournalSnapshot

_STATE_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class JournalTableModel(QAbstractTableModel):
    def __init__(self, snapshot: JournalSnapshot, parent=None) -> None:
        super().__init__(parent)
        self._snapshot = snapshot

    @property
    def snapshot(self) -> JournalSnapshot:
        return self._snapshot

    def set_snapshot(self, snapshot: JournalSnapshot) -> None:
        self.beginResetModel()
        self._snapshot = snapshot
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._snapshot.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._snapshot.visible_fields)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation != Qt.Orientation.Horizontal:
            return section + 1
        fields = self._snapshot.visible_fields
        if 0 <= section < len(fields):
            return fields[section].title
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._snapshot.rows[index.row()]
        field = self._snapshot.visible_fields[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return row.display_value(field.key)
        if role == Qt.ItemDataRole.UserRole:
            return row.id
        if role == _STATE_ROLE:
            return row.state
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return self._alignment(field.anchor)
        return None

    def row(self, index: int):
        return self._snapshot.rows[index]

    @staticmethod
    def _alignment(anchor: str):
        if anchor == "center":
            return Qt.AlignmentFlag.AlignCenter
        if anchor in {"e", "right"}:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
