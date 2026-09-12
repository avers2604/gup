from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from getpass_qt.models.journal_table_model import JournalTableModel

_EXTRA_FILTERS = {
    "pass": (
        ("zone", "Зона допуска", "combo"),
        ("driver", "Водитель", "text"),
    ),
    "badge": (
        ("park", "Подразделение", "combo"),
        ("role", "Должность", "combo"),
    ),
}
_PROTECTED_FIELDS = frozenset({"id", "status", "revoked_at", "revoke_reason"})


class JournalsPage(QWidget):
    def __init__(
        self,
        viewmodel,
        *,
        save_dialog=None,
        ask_revoke_reason=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("JournalsPage")
        self._viewmodel = viewmodel
        self._save_dialog = save_dialog or self._default_save_dialog
        self._ask_revoke_reason = ask_revoke_reason or self._default_revoke_reason
        self.extra_filters: dict[str, QWidget] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.addWidget(self._build_filter_card())
        root.addWidget(self._build_table(), 1)
        root.addWidget(self._build_footer())

        self._connect_viewmodel()
        self._sync_snapshot(self._viewmodel.snapshot)

    def _build_filter_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("JournalFilterCard")
        card.setProperty("role", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self.journal_combo = QComboBox()
        self.journal_combo.setObjectName("JournalSelector")
        self.journal_combo.addItem("Пропуски ТС", "pass")
        self.journal_combo.addItem("Пропуска работников", "badge")
        self.journal_combo.currentIndexChanged.connect(self._journal_changed)
        top.addWidget(self.journal_combo)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("JournalSearch")
        self.search_edit.setPlaceholderText("Поиск по журналу")
        self.search_edit.textChanged.connect(self._viewmodel.set_search)
        top.addWidget(self.search_edit, 1)

        self.status_combo = QComboBox()
        self.status_combo.setObjectName("JournalStatusFilter")
        for label, value in (
            ("Все", "all"),
            ("Действующие", "active"),
            ("Просроченные", "expired"),
            ("Аннулированные", "revoked"),
            ("Без срока", "unknown"),
        ):
            self.status_combo.addItem(label, value)
        self.status_combo.currentIndexChanged.connect(self._status_changed)
        top.addWidget(self.status_combo)
        layout.addLayout(top)

        dates = QHBoxLayout()
        self.date_from = QLineEdit()
        self.date_from.setObjectName("JournalDateFrom")
        self.date_from.setPlaceholderText("Дата выдачи с · ДД.ММ.ГГГГ")
        self.date_from.editingFinished.connect(self._date_range_changed)
        dates.addWidget(self.date_from)
        self.date_to = QLineEdit()
        self.date_to.setObjectName("JournalDateTo")
        self.date_to.setPlaceholderText("по · ДД.ММ.ГГГГ")
        self.date_to.editingFinished.connect(self._date_range_changed)
        dates.addWidget(self.date_to)
        layout.addLayout(dates)

        extra_host = QWidget()
        extra_host.setObjectName("JournalExtraFilters")
        self._extra_layout = QHBoxLayout(extra_host)
        self._extra_layout.setContentsMargins(0, 0, 0, 0)
        self._extra_layout.setSpacing(10)
        layout.addWidget(extra_host)
        return card

    def _build_table(self) -> QTableView:
        self.table = QTableView()
        self.table.setObjectName("JournalTable")
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().sectionClicked.connect(self._sort_column)
        return self.table

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.status_label = QLabel()
        self.status_label.setObjectName("JournalStatus")
        self.status_label.setProperty("role", "muted")
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self.previous_button = self._button("←", "JournalPreviousPage")
        self.previous_button.clicked.connect(partial(self._turn_page, -1))
        layout.addWidget(self.previous_button)
        self.page_label = QLabel()
        self.page_label.setObjectName("JournalPageLabel")
        layout.addWidget(self.page_label)
        self.next_button = self._button("→", "JournalNextPage")
        self.next_button.clicked.connect(partial(self._turn_page, 1))
        layout.addWidget(self.next_button)

        self.refresh_button = self._button("Обновить", "JournalRefreshButton")
        self.refresh_button.clicked.connect(self._viewmodel.refresh)
        layout.addWidget(self.refresh_button)
        self.history_button = self._button("История", "JournalHistoryButton")
        self.history_button.clicked.connect(self._show_history)
        layout.addWidget(self.history_button)
        self.edit_button = self._button("Изменить", "JournalEditButton")
        self.edit_button.clicked.connect(self._edit_selected)
        layout.addWidget(self.edit_button)
        self.revoke_button = self._button("Аннулировать", "JournalRevokeButton")
        self.revoke_button.clicked.connect(self._revoke_selected)
        layout.addWidget(self.revoke_button)
        self.export_button = self._button("Экспорт текущего", "JournalExportButton")
        self.export_button.setProperty("role", "primary")
        self.export_button.clicked.connect(self._export_current)
        layout.addWidget(self.export_button)
        return footer

    def _connect_viewmodel(self) -> None:
        self._viewmodel.snapshot_changed.connect(self._sync_snapshot)
        self._viewmodel.busy_changed.connect(self._set_busy)
        self._viewmodel.operation_failed.connect(self._show_status)
        self._viewmodel.operation_succeeded.connect(self._show_status)

    def _sync_snapshot(self, snapshot) -> None:
        model = self.table.model()
        if isinstance(model, JournalTableModel):
            model.set_snapshot(snapshot)
        else:
            self.table.setModel(JournalTableModel(snapshot, self.table))
            self.table.selectionModel().selectionChanged.connect(
                self._selection_changed
            )
        self._sync_journal_selector(snapshot.journal_key)
        self._sync_filters()
        self._rebuild_extra_filters(snapshot.journal_key)
        self._resize_columns(snapshot)
        self._selection_changed()
        self._update_pagination(snapshot)

    def _sync_journal_selector(self, journal_key: str) -> None:
        index = self.journal_combo.findData(journal_key)
        if index >= 0 and index != self.journal_combo.currentIndex():
            old = self.journal_combo.blockSignals(True)
            self.journal_combo.setCurrentIndex(index)
            self.journal_combo.blockSignals(old)

    def _sync_filters(self) -> None:
        filters = self._viewmodel.filters
        self._set_line_text(self.search_edit, filters.search)
        self._set_line_text(self.date_from, filters.date_from)
        self._set_line_text(self.date_to, filters.date_to)
        status_index = self.status_combo.findData(filters.status)
        if status_index >= 0 and status_index != self.status_combo.currentIndex():
            old = self.status_combo.blockSignals(True)
            self.status_combo.setCurrentIndex(status_index)
            self.status_combo.blockSignals(old)

    def _rebuild_extra_filters(self, journal_key: str) -> None:
        self._clear_extra_filters()
        values = self._viewmodel.filters.extra_values()
        for key, label, kind in _EXTRA_FILTERS[journal_key]:
            widget = self._make_extra_filter(key, label, kind, values.get(key, ""))
            self.extra_filters[key] = widget
            self._extra_layout.addWidget(widget)
        self._extra_layout.addStretch(1)

    def _clear_extra_filters(self) -> None:
        while self._extra_layout.count():
            item = self._extra_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.extra_filters.clear()

    def _make_extra_filter(self, key: str, label: str, kind: str, current: str):
        if kind == "combo":
            widget = QComboBox()
            widget.addItem(label, "")
            for value in self._viewmodel.distinct(key):
                widget.addItem(value, value)
            index = widget.findData(current)
            if index >= 0:
                widget.setCurrentIndex(index)
            widget.currentIndexChanged.connect(
                partial(self._extra_combo_changed, key, widget)
            )
        else:
            widget = QLineEdit(current)
            widget.setPlaceholderText(label)
            widget.editingFinished.connect(
                partial(self._extra_text_changed, key, widget)
            )
        widget.setObjectName(f"JournalFilter{key.title()}")
        return widget

    def _resize_columns(self, snapshot) -> None:
        header = self.table.horizontalHeader()
        for index, field in enumerate(snapshot.visible_fields):
            header.resizeSection(index, max(80, field.tree_width))

    def _update_pagination(self, snapshot) -> None:
        self.status_label.setText(
            f"Показано: {snapshot.filtered_records} из {snapshot.total_records} · "
            f"{snapshot.journal_name}"
        )
        self.page_label.setText(f"{snapshot.page + 1} / {snapshot.page_count}")
        self.previous_button.setEnabled(snapshot.page > 0)
        self.next_button.setEnabled(snapshot.page + 1 < snapshot.page_count)

    def _journal_changed(self) -> None:
        journal_key = self.journal_combo.currentData()
        if journal_key:
            self._viewmodel.select_journal(journal_key)

    def _status_changed(self) -> None:
        status = self.status_combo.currentData()
        if status:
            self._viewmodel.set_status(status)

    def _date_range_changed(self) -> None:
        self._viewmodel.set_date_range(
            self.date_from.text().strip(),
            self.date_to.text().strip(),
        )

    def _extra_combo_changed(self, key: str, widget: QComboBox) -> None:
        self._viewmodel.set_extra_filter(key, widget.currentData() or "")

    def _extra_text_changed(self, key: str, widget: QLineEdit) -> None:
        self._viewmodel.set_extra_filter(key, widget.text())

    def _sort_column(self, column: int) -> None:
        fields = self._viewmodel.snapshot.visible_fields
        if 0 <= column < len(fields):
            self._viewmodel.sort_by(fields[column].key)

    def _turn_page(self, delta: int) -> None:
        self._viewmodel.set_page(self._viewmodel.snapshot.page + delta)

    def _selection_changed(self, *_args) -> None:
        selected = self._selected_ids()
        self.edit_button.setEnabled(len(selected) == 1)
        self.history_button.setEnabled(len(selected) == 1)
        self.revoke_button.setEnabled(bool(selected))

    def _selected_ids(self) -> tuple[str, ...]:
        selection = self.table.selectionModel()
        if selection is None:
            return ()
        model = self.table.model()
        return tuple(
            str(model.data(index, Qt.ItemDataRole.UserRole))
            for index in selection.selectedRows()
        )

    def _edit_selected(self) -> None:
        selected = self._selected_ids()
        if len(selected) != 1:
            return
        row = self._find_row(selected[0])
        if row is None:
            return
        dialog = EditJournalRecordDialog(
            self._viewmodel.snapshot.fields,
            row.values,
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._viewmodel.update_record(row.id, dialog.values())

    def _show_history(self) -> None:
        selected = self._selected_ids()
        if len(selected) != 1:
            return
        JournalHistoryDialog(self._viewmodel.history(selected[0]), self).exec()

    def _revoke_selected(self) -> None:
        selected = self._selected_ids()
        if not selected:
            return
        reason = self._ask_revoke_reason(len(selected))
        if reason is None:
            return
        reason = reason.strip() or "не указана"
        if not self._viewmodel.revoke(selected, reason):
            return
        if self._confirm_blacklist():
            self._viewmodel.add_revoked_to_blacklist(selected, reason)

    def _confirm_blacklist(self) -> bool:
        answer = QMessageBox.question(
            self,
            "Чёрный список",
            "Добавить аннулированные записи в чёрный список нарушителей?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _export_current(self) -> None:
        path = self._save_dialog()
        if path:
            self._viewmodel.export(path)

    def _find_row(self, record_id: str):
        return next(
            (row for row in self._viewmodel.snapshot.rows if row.id == record_id),
            None,
        )

    def _default_save_dialog(self) -> str:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт текущей выборки",
            "выборка_журнала.xlsx",
            "Excel (*.xlsx)",
        )
        return path

    def _default_revoke_reason(self, count: int):
        value, accepted = QInputDialog.getText(
            self,
            "Аннулирование",
            f"Причина аннулирования ({count} шт.):",
        )
        return value if accepted else None

    def _set_busy(self, busy: bool) -> None:
        for widget in (
            self.journal_combo,
            self.search_edit,
            self.status_combo,
            self.refresh_button,
            self.export_button,
        ):
            widget.setEnabled(not busy)

    def _show_status(self, message: str) -> None:
        self.status_label.setText(message)

    @staticmethod
    def _button(text: str, object_name: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        return button

    @staticmethod
    def _set_line_text(widget: QLineEdit, value: str) -> None:
        if widget.text() == value:
            return
        old = widget.blockSignals(True)
        widget.setText(value)
        widget.blockSignals(old)


class EditJournalRecordDialog(QDialog):
    def __init__(self, fields, values, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Редактирование записи")
        self._entries: dict[str, QLineEdit] = {}
        root = QVBoxLayout(self)
        form = QFormLayout()
        for field in fields:
            if field.key in _PROTECTED_FIELDS:
                continue
            edit = QLineEdit(str(values.get(field.key, "") or ""))
            edit.setObjectName(f"JournalEdit{field.key.title()}")
            self._entries[field.key] = edit
            form.addRow(field.title, edit)
        root.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def values(self) -> dict[str, str]:
        return {key: edit.text().strip() for key, edit in self._entries.items()}


class JournalHistoryDialog(QDialog):
    def __init__(self, events, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("История записи")
        self.resize(760, 480)
        layout = QVBoxLayout(self)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(self._history_text(events))
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _history_text(events) -> str:
        if not events:
            return "Запись создана до включения истории изменений."
        blocks = []
        for event in events:
            lines = [f"{event.occurred_at} · {event.actor} · {event.action}"]
            lines.extend(
                f"{change.title}: {change.before} → {change.after}"
                for change in event.changes
            )
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)
