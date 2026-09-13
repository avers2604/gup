from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from getpass_qt.models.operations_table_model import OperationsTableModel


class OperationsPage(QWidget):
    def __init__(
        self,
        viewmodel,
        *,
        open_document=None,
        confirm_action=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("OperationsPage")
        self._viewmodel = viewmodel
        self._open_document = open_document or self._default_open_document
        self._confirm_action = confirm_action or self._default_confirm_action

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.addWidget(self._build_intro())
        root.addWidget(self._build_table(), 1)
        root.addWidget(self._build_actions())

        self._connect_viewmodel()
        self._sync_operations(self._viewmodel.operations)

    def _build_intro(self) -> QWidget:
        card = QFrame()
        card.setProperty("role", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        title = QLabel("Незавершённые выдачи")
        title.setObjectName("OperationsTitle")
        layout.addWidget(title)
        hint = QLabel(
            "Здесь показаны операции, подготовленные к выдаче, но не "
            "подтверждённые после внешнего вывода."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "muted")
        layout.addWidget(hint)
        return card

    def _build_table(self) -> QTableView:
        self.table = QTableView()
        self.table.setObjectName("OperationsTable")
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        return self.table

    def _build_actions(self) -> QWidget:
        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.status_label = QLabel()
        self.status_label.setObjectName("OperationsStatus")
        self.status_label.setProperty("role", "muted")
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self.refresh_button = self._button("Обновить", "OperationsRefreshButton")
        self.refresh_button.clicked.connect(self._viewmodel.refresh)
        layout.addWidget(self.refresh_button)
        self.open_button = self._button("Открыть файл", "OperationsOpenButton")
        self.open_button.clicked.connect(self._open_selected)
        layout.addWidget(self.open_button)
        self.cancel_button = self._button("Отменить", "OperationsCancelButton")
        self.cancel_button.clicked.connect(self._cancel_selected)
        layout.addWidget(self.cancel_button)
        self.confirm_button = self._button(
            "Подтвердить выдачу",
            "OperationsConfirmButton",
        )
        self.confirm_button.setProperty("role", "accent")
        self.confirm_button.clicked.connect(self._confirm_selected)
        layout.addWidget(self.confirm_button)
        return actions

    def _connect_viewmodel(self) -> None:
        self._viewmodel.operations_changed.connect(self._sync_operations)
        self._viewmodel.busy_changed.connect(self._set_busy)
        self._viewmodel.operation_succeeded.connect(self._show_status)
        self._viewmodel.operation_failed.connect(self._show_status)

    def _sync_operations(self, operations) -> None:
        model = self.table.model()
        if isinstance(model, OperationsTableModel):
            model.set_operations(operations)
        else:
            self.table.setModel(OperationsTableModel(operations, self.table))
            self.table.selectionModel().selectionChanged.connect(
                self._selection_changed
            )
        self.table.resizeColumnsToContents()
        self._selection_changed()
        self.status_label.setText(f"Незавершённых операций: {len(operations)}")

    def _selection_changed(self, *_args) -> None:
        selected = self._selected_operations()
        self.confirm_button.setEnabled(bool(selected))
        self.cancel_button.setEnabled(bool(selected))
        self.open_button.setEnabled(
            len(selected) == 1 and selected[0].document_status == "Файл готов"
        )

    def _selected_operations(self):
        selection = self.table.selectionModel()
        if selection is None:
            return ()
        model = self.table.model()
        return tuple(model.operation(index.row()) for index in selection.selectedRows())

    def _selected_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self._selected_operations())

    def _open_selected(self) -> None:
        selected = self._selected_operations()
        if len(selected) == 1 and selected[0].document_status == "Файл готов":
            self._open_document(selected[0].document_path)

    def _confirm_selected(self) -> None:
        ids = self._selected_ids()
        if ids and self._confirm_action("confirm", len(ids)):
            self._viewmodel.confirm(ids)

    def _cancel_selected(self) -> None:
        ids = self._selected_ids()
        if ids and self._confirm_action("cancel", len(ids)):
            self._viewmodel.cancel(ids)

    def _set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)
        if busy:
            self.open_button.setEnabled(False)
            self.confirm_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
        else:
            self._selection_changed()

    def _show_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _default_confirm_action(self, action: str, count: int) -> bool:
        if action == "confirm":
            title = "Подтверждение выдачи"
            text = f"Подтвердить выбранные операции ({count} шт.)?"
        else:
            title = "Отмена операции"
            text = f"Отменить выбранные операции ({count} шт.)?"
        answer = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    @staticmethod
    def _default_open_document(path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @staticmethod
    def _button(text: str, object_name: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        return button
