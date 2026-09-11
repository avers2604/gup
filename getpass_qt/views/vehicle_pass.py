from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from getpass_qt.viewmodels.vehicle_pass_viewmodel import VehiclePassViewModel
from getpass_qt.widgets.image_preview import ImagePreview

_PASS_LABELS = {
    "num": "Номер бланка",
    "plate": "Госномер",
    "brand": "Марка",
    "model": "Модель",
    "vehicle_type": "Тип ТС",
    "color": "Цвет",
    "driver_position": "Должность водителя",
    "driver_name": "ФИО водителя",
    "phone": "Телефон",
    "territory": "Зона допуска",
}

_COMMON_LABELS = {
    "issue_date": "Дата выдачи",
    "valid_until": "Действителен до",
    "otb_post": "Должность ОТБ",
    "otb_name": "ФИО ОТБ",
}


class VehiclePassPage(QWidget):
    def __init__(
        self,
        viewmodel: VehiclePassViewModel,
        *,
        save_dialog=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("VehiclePassPage")
        self._viewmodel = viewmodel
        self._save_dialog = save_dialog or self._default_save_dialog
        self.pass_fields: dict[str, dict[str, QLineEdit]] = {
            "first": {},
            "second": {},
        }
        self.common_fields: dict[str, QWidget] = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)
        root.addWidget(self._build_form_panel(), 3)
        root.addWidget(self._build_preview_panel(), 2)

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self._refresh_current_preview)

        self._connect_viewmodel()
        self._sync_state(self._viewmodel.state)
        self._refresh_current_preview()

    def _build_form_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(14)

        self.slot_tabs = QTabWidget()
        self.slot_tabs.setObjectName("PassSlotTabs")
        self.slot_tabs.addTab(self._build_pass_tab("first"), "Пропуск №1")
        self.slot_tabs.addTab(self._build_pass_tab("second"), "Пропуск №2")
        self.slot_tabs.currentChanged.connect(self._slot_tab_changed)
        layout.addWidget(self.slot_tabs)

        layout.addWidget(self._build_common_card())
        self.print_settings = self._build_print_settings()
        self.print_settings.setObjectName("PrintSettings")
        layout.addWidget(self.print_settings)
        layout.addWidget(self._build_actions())
        layout.addStretch(1)

        scroll.setWidget(container)
        return scroll

    def _build_pass_tab(self, slot: str) -> QWidget:
        card = QFrame()
        card.setProperty("role", "card")
        form = QFormLayout(card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        for field, label in _PASS_LABELS.items():
            edit = QLineEdit()
            edit.setObjectName(f"{slot}_{field}")
            edit.textChanged.connect(
                partial(self._viewmodel.set_pass_field, slot, field)
            )
            if field == "plate":
                edit.editingFinished.connect(
                    partial(self._finish_plate, slot)
                )
            self.pass_fields[slot][field] = edit
            form.addRow(label, edit)

        self._add_completer(
            self.pass_fields[slot]["brand"],
            self._viewmodel.brands(),
        )
        self._add_completer(
            self.pass_fields[slot]["territory"],
            self._viewmodel.zones(),
        )
        return card

    def _build_common_card(self) -> QWidget:
        card = QFrame()
        card.setProperty("role", "card")
        form = QFormLayout(card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        for field, label in _COMMON_LABELS.items():
            edit = QLineEdit()
            edit.setObjectName(f"common_{field}")
            edit.textChanged.connect(
                partial(self._viewmodel.set_common_field, field)
            )
            self.common_fields[field] = edit
            form.addRow(label, edit)

        temporary = QCheckBox("Временный пропуск")
        temporary.setObjectName("common_is_temporary")
        temporary.toggled.connect(
            partial(self._viewmodel.set_common_field, "is_temporary")
        )
        self.common_fields["is_temporary"] = temporary
        form.addRow("", temporary)
        return card

    def _build_print_settings(self) -> QFrame:
        card = QFrame()
        card.setProperty("role", "card")
        form = QFormLayout(card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        self.printer_combo = QComboBox()
        self.printer_combo.setObjectName("PrinterCombo")
        printers = self._viewmodel.printers() or ("По умолчанию",)
        self.printer_combo.addItems(printers)
        form.addRow("Принтер", self.printer_combo)

        self.format_combo = QComboBox()
        self.format_combo.setObjectName("PageFormat")
        self.format_combo.addItem("A4 — два пропуска", "a4")
        self.format_combo.addItem("A5 — один пропуск", "a5")
        self.format_combo.currentIndexChanged.connect(self._page_format_changed)
        form.addRow("Формат", self.format_combo)

        self.print_back_checkbox = QCheckBox("Печатать оборотную сторону")
        self.print_back_checkbox.setObjectName("PrintBack")
        self.print_back_checkbox.toggled.connect(self._viewmodel.set_print_back)
        form.addRow("", self.print_back_checkbox)
        return card

    def _build_actions(self) -> QWidget:
        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addStretch(1)

        self.save_button = QPushButton("Сохранить PDF")
        self.save_button.setObjectName("SavePdfButton")
        self.save_button.setProperty("role", "primary")
        self.save_button.clicked.connect(self._save_pdf)
        layout.addWidget(self.save_button)

        self.print_button = QPushButton("Напечатать")
        self.print_button.setObjectName("PrintButton")
        self.print_button.setProperty("role", "accent")
        self.print_button.clicked.connect(self._print)
        layout.addWidget(self.print_button)
        return actions

    def _build_preview_panel(self) -> QWidget:
        card = QFrame()
        card.setProperty("role", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Предпросмотр")
        layout.addWidget(title)

        self.preview_target = QComboBox()
        self.preview_target.setObjectName("PreviewTarget")
        self.preview_target.addItem("Пропуск №1", "first")
        self.preview_target.addItem("Пропуск №2", "second")
        self.preview_target.currentIndexChanged.connect(
            self._preview_target_changed
        )
        layout.addWidget(self.preview_target)

        self.preview = ImagePreview()
        self.preview.setObjectName("VehiclePreview")
        layout.addWidget(self.preview, 1)

        self.status_label = QLabel("Готово к вводу данных")
        self.status_label.setObjectName("VehicleStatus")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        return card

    def _connect_viewmodel(self) -> None:
        self._viewmodel.state_changed.connect(self._state_changed)
        self._viewmodel.preview_changed.connect(self.preview.set_pil_image)
        self._viewmodel.validation_changed.connect(self._show_validation)
        self._viewmodel.busy_changed.connect(self._set_busy)
        self._viewmodel.operation_succeeded.connect(self._show_status)
        self._viewmodel.operation_failed.connect(self._show_status)

    def _state_changed(self, state) -> None:
        self._sync_state(state)
        self._preview_timer.start()

    def _sync_state(self, state) -> None:
        for slot in ("first", "second"):
            pass_data = getattr(state, slot)
            for field, edit in self.pass_fields[slot].items():
                self._set_line_text(edit, getattr(pass_data, field))

        for field, widget in self.common_fields.items():
            value = getattr(state.common, field)
            if isinstance(widget, QCheckBox):
                self._set_checked(widget, bool(value))
            else:
                self._set_line_text(widget, value)

        index = self.format_combo.findData(state.page_format)
        if index >= 0 and index != self.format_combo.currentIndex():
            old = self.format_combo.blockSignals(True)
            self.format_combo.setCurrentIndex(index)
            self.format_combo.blockSignals(old)
        self._set_checked(self.print_back_checkbox, state.print_back)

        second_enabled = state.page_format == "a4"
        self.slot_tabs.setTabEnabled(1, second_enabled)
        if not second_enabled and self.slot_tabs.currentIndex() == 1:
            self.slot_tabs.setCurrentIndex(0)

    def _show_validation(self, issues) -> None:
        for fields in self.pass_fields.values():
            for widget in fields.values():
                self._set_invalid(widget, False)

        for issue in issues:
            slot, separator, field = issue.field.partition(".")
            if separator and slot in self.pass_fields:
                widget = self.pass_fields[slot].get(field)
                if widget is not None:
                    self._set_invalid(widget, True)
        if issues:
            self._show_status(issues[0].message)

    def _finish_plate(self, slot: str) -> None:
        self._viewmodel.autocomplete_vehicle(slot)
        self._viewmodel.validate()

    def _page_format_changed(self) -> None:
        page_format = self.format_combo.currentData()
        if page_format:
            self._viewmodel.set_page_format(page_format)

    def _slot_tab_changed(self, index: int) -> None:
        if 0 <= index < self.preview_target.count():
            self.preview_target.setCurrentIndex(index)

    def _preview_target_changed(self) -> None:
        self._preview_timer.stop()
        self._refresh_current_preview()

    def _refresh_current_preview(self) -> None:
        slot = self.preview_target.currentData() or "first"
        self._viewmodel.refresh_preview(slot)

    def _save_pdf(self) -> None:
        path = self._save_dialog()
        if path:
            self._viewmodel.save_pdf(path)

    def _print(self) -> None:
        self._viewmodel.print_passes(
            self.printer_combo.currentText(),
            confirm_flip=self._confirm_flip,
        )

    def _confirm_flip(self) -> bool:
        answer = QMessageBox.question(
            self,
            "Оборотная сторона",
            "Переверните лист для печати оборотной стороны и нажмите «Да».",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _default_save_dialog(self) -> str:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить пропуск",
            "Пропуск.pdf",
            "PDF (*.pdf)",
        )
        return path

    def _set_busy(self, busy: bool) -> None:
        self.save_button.setEnabled(not busy)
        self.print_button.setEnabled(not busy)

    def _show_status(self, message: str) -> None:
        self.status_label.setText(message)

    @staticmethod
    def _add_completer(edit: QLineEdit, values) -> None:
        completer = QCompleter(list(values), edit)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        edit.setCompleter(completer)

    @staticmethod
    def _set_line_text(edit: QLineEdit, value) -> None:
        text = str(value or "")
        if edit.text() == text:
            return
        old = edit.blockSignals(True)
        edit.setText(text)
        edit.blockSignals(old)

    @staticmethod
    def _set_checked(widget: QCheckBox, checked: bool) -> None:
        if widget.isChecked() == checked:
            return
        old = widget.blockSignals(True)
        widget.setChecked(checked)
        widget.blockSignals(old)

    @staticmethod
    def _set_invalid(widget: QWidget, invalid: bool) -> None:
        if widget.property("invalid") is invalid:
            return
        widget.setProperty("invalid", invalid)
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
