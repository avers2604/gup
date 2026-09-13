from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from getpass_qt.models.blacklist_table_model import BlacklistTableModel


class SettingsPage(QWidget):
    def __init__(
        self,
        settings_viewmodel,
        blacklist_viewmodel,
        *,
        confirm_remove=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings_viewmodel
        self._blacklist = blacklist_viewmodel
        self._confirm_remove = confirm_remove or self._confirm_remove_dialog

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        note = QLabel(
            "Настройки применяются к новым формам. Уже открытые документы "
            "не изменяются автоматически."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        self.tabs = QTabWidget()
        self.parameters_tab = self._build_parameters_tab()
        self.blacklist_tab = self._build_blacklist_tab()
        self.tabs.addTab(self.parameters_tab, "Параметры")
        self.tabs.addTab(self.blacklist_tab, "Черный список")
        root.addWidget(self.tabs, 1)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self._settings.operation_succeeded.connect(self._show_status)
        self._settings.operation_failed.connect(self._show_error)
        self._blacklist.operation_succeeded.connect(self._show_status)
        self._blacklist.operation_failed.connect(self._show_error)
        self._blacklist.entries_changed.connect(self.blacklist_model.set_entries)
        self._blacklist.refresh()

    def _build_parameters_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(14)

        pass_group = QGroupBox("Пропуск ТС")
        pass_form = QFormLayout(pass_group)
        defaults = self._settings.defaults

        self.last_pass_num_edit = self._line_edit("last_pass_num", defaults.last_pass_num)
        self.territory_edit = self._line_edit("territory", defaults.territory)
        self.valid_until_edit = self._line_edit("valid_until", defaults.valid_until)
        self.otb_post_edit = self._line_edit("otb_post", defaults.otb_post)
        self.otb_name_edit = self._line_edit("otb_name", defaults.otb_name)
        self.temporary_checkbox = self._checkbox(
            "is_temporary_car",
            defaults.is_temporary_car,
        )
        self.print_mode_combo = self._combo(
            "print_mode",
            (("A4", "a4"), ("A5", "a5")),
            defaults.print_mode,
        )
        self.print_back_checkbox = self._checkbox(
            "print_pass_back",
            defaults.print_pass_back,
        )
        self.preview_target_combo = self._combo(
            "auto_preview_target",
            (("Пропуск 1", "1"), ("Пропуск 2", "2")),
            defaults.auto_preview_target,
        )

        pass_form.addRow("Номер бланка", self.last_pass_num_edit)
        pass_form.addRow("Территория", self.territory_edit)
        pass_form.addRow("Срок действия", self.valid_until_edit)
        pass_form.addRow("Должность ОТБ", self.otb_post_edit)
        pass_form.addRow("ФИО ОТБ", self.otb_name_edit)
        pass_form.addRow("Временный ТС", self.temporary_checkbox)
        pass_form.addRow("Формат", self.print_mode_combo)
        pass_form.addRow("Печатать оборот", self.print_back_checkbox)
        pass_form.addRow("Автопредпросмотр", self.preview_target_combo)
        layout.addWidget(pass_group)

        badge_group = QGroupBox("Пропуск работника")
        badge_form = QFormLayout(badge_group)
        self.badge_park_edit = self._line_edit("badge_park", defaults.badge_park)
        self.badge_tab_num_edit = self._line_edit(
            "badge_tab_num",
            defaults.badge_tab_num,
        )
        self.badge_print_mode_combo = self._combo(
            "badge_print_mode",
            (
                ("Карточка", "card"),
                ("Сетка 3×3 на A4", "a4_grid"),
                ("Один пропуск на A4", "a4_single"),
            ),
            defaults.badge_print_mode,
        )
        self.warn_duplicates_checkbox = self._checkbox(
            "warn_duplicates",
            defaults.warn_duplicates,
        )
        badge_form.addRow("Подразделение", self.badge_park_edit)
        badge_form.addRow("Табельный номер", self.badge_tab_num_edit)
        badge_form.addRow("Формат печати", self.badge_print_mode_combo)
        badge_form.addRow("Предупреждать о дублях", self.warn_duplicates_checkbox)
        layout.addWidget(badge_group)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.save_button = QPushButton("Сохранить настройки")
        self.save_button.clicked.connect(self._settings.save)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        layout.addStretch(1)
        return tab

    def _build_blacklist_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(12)

        editor = QGroupBox("Новая запись")
        form = QFormLayout(editor)
        self.plate_edit = QLineEdit()
        self.fio_edit = QLineEdit()
        self.incident_edit = QLineEdit()
        form.addRow("Госномер", self.plate_edit)
        form.addRow("ФИО", self.fio_edit)
        form.addRow("Инцидент", self.incident_edit)
        layout.addWidget(editor)

        editor_actions = QHBoxLayout()
        self.add_blacklist_button = QPushButton("Добавить")
        self.add_blacklist_button.clicked.connect(self._add_blacklist)
        editor_actions.addWidget(self.add_blacklist_button)
        editor_actions.addStretch(1)
        self.refresh_blacklist_button = QPushButton("Обновить")
        self.refresh_blacklist_button.clicked.connect(self._blacklist.refresh)
        editor_actions.addWidget(self.refresh_blacklist_button)
        layout.addLayout(editor_actions)

        self.blacklist_model = BlacklistTableModel(self._blacklist.entries)
        self.blacklist_table = QTableView()
        self.blacklist_table.setModel(self.blacklist_model)
        self.blacklist_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.blacklist_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.blacklist_table.setAlternatingRowColors(True)
        self.blacklist_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.blacklist_table, 1)

        table_actions = QHBoxLayout()
        table_actions.addStretch(1)
        self.remove_blacklist_button = QPushButton("Удалить выбранную")
        self.remove_blacklist_button.clicked.connect(self._remove_selected)
        table_actions.addWidget(self.remove_blacklist_button)
        layout.addLayout(table_actions)
        return tab

    def _line_edit(self, field: str, value: str) -> QLineEdit:
        widget = QLineEdit(value)
        widget.textChanged.connect(
            lambda text, key=field: self._settings.set_field(key, text)
        )
        return widget

    def _checkbox(self, field: str, value: bool) -> QCheckBox:
        widget = QCheckBox()
        widget.setChecked(bool(value))
        widget.toggled.connect(
            lambda checked, key=field: self._settings.set_field(key, checked)
        )
        return widget

    def _combo(self, field: str, options, value: str) -> QComboBox:
        widget = QComboBox()
        for label, data in options:
            widget.addItem(label, data)
        index = widget.findData(value)
        widget.setCurrentIndex(index if index >= 0 else 0)
        widget.currentIndexChanged.connect(
            lambda _index, key=field, combo=widget: self._settings.set_field(
                key,
                combo.currentData(),
            )
        )
        return widget

    def _add_blacklist(self) -> None:
        if self._blacklist.add(
            self.plate_edit.text(),
            self.fio_edit.text(),
            self.incident_edit.text(),
        ):
            self.plate_edit.clear()
            self.fio_edit.clear()
            self.incident_edit.clear()

    def _remove_selected(self) -> None:
        rows = self.blacklist_table.selectionModel().selectedRows()
        if not rows:
            self._show_error("Выберите запись для удаления.")
            return
        entry = self.blacklist_model.entry(rows[0].row())
        if self._confirm_remove(entry):
            self._blacklist.remove(entry.id)

    def _confirm_remove_dialog(self, entry) -> bool:
        label = entry.plate or entry.fio or entry.id
        answer = QMessageBox.question(
            self,
            "Удаление из черного списка",
            f"Удалить запись «{label}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _show_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("status", "success")

    def _show_error(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setProperty("status", "error")
