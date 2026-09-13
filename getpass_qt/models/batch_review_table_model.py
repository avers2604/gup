from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from getpass_app.models.batch import BatchReview

_STATE_ROLE = int(Qt.ItemDataRole.UserRole) + 1
_COLUMNS = (
    ("row_number", "Строка"),
    ("number", "Номер"),
    ("person", "Сотрудник / водитель"),
    ("result", "Проверка"),
)


class BatchReviewTableModel(QAbstractTableModel):
    def __init__(self, review: BatchReview, parent=None) -> None:
        super().__init__(parent)
        self._review = review

    @property
    def review(self) -> BatchReview:
        return self._review

    def set_review(self, review: BatchReview) -> None:
        self.beginResetModel()
        self._review = review
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._review.rows)

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
        row = self._review.rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            key = _COLUMNS[index.column()][0]
            return getattr(row, key)
        if role == _STATE_ROLE:
            return row.state
        return None

    def row(self, index: int):
        return self._review.rows[index]
