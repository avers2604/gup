from __future__ import annotations

from functools import partial

from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from getpass_app.models.employee_badge import BADGE_PARKS
from getpass_qt.viewmodels.employee_badge_viewmodel import EmployeeBadgeViewModel
from getpass_qt.widgets.image_preview import ImagePreview
from getpass_qt.widgets.photo_crop_dialog import PhotoCropDialog


class EmployeeBadgePage(QWidget):
    def __init__(
        self,
        viewmodel: EmployeeBadgeViewModel,
        *,
        open_image=None,
        crop_image=None,
        save_dialog=None,
        confirm_warning=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("EmployeeBadgePage")
        self._viewmodel = viewmodel
        self._open_image = open_image or self._default_open_image
        self._crop_image = crop_image or self._default_crop_image
        self._save_dialog = save_dialog or self._default_save_dialog
        self._confirm_warning = confirm_warning or self._default_confirm_warning
        self.photo_path = ""
        self._field_widgets: dict[str, QWidget] = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)
        root.addWidget(self._build_form_panel(), 3)
        root.addWidget(self._build_preview_panel(), 2)

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self._refresh_preview)

        self._connect_viewmodel()
        self._sync_state(self._viewmodel.state)
        self._refresh_preview()

    def _build_form_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(14)
        layout.addWidget(self._build_employee_card())
        layout.addWidget(self._build_photo_card())
        layout.addWidget(self._build_validity_card())
        layout.addWidget(self._build_print_card())
        layout.addWidget(self._build_actions())
        layout.addStretch(1)
        scroll.setWidget(container)
        return scroll

    def _build_employee_card(self) -> QFrame:
        card, form = self._form_card("BadgeEmployeeCard")

        self.park_combo = QComboBox()
        self.park_combo.setObjectName("BadgePark")
        self.park_combo.addItems(BADGE_PARKS)
        self.park_combo.currentTextChanged.connect(partial(self._viewmodel.set_field, "park"))
        self._field_widgets["park"] = self.park_combo
        form.addRow("Подразделение", self.park_combo)

        self.tab_num_edit = self._line_edit("badge_tab_num", "tab_num")
        form.addRow("Табельный №", self.tab_num_edit)

        self.role_combo = QComboBox()
        self.role_combo.setObjectName("BadgeRole")
        self.role_combo.setEditable(True)
        self.role_combo.addItems(self._viewmodel.roles())
        self.role_combo.currentTextChanged.connect(partial(self._viewmodel.set_field, "role"))
        self._field_widgets["role"] = self.role_combo
        form.addRow("Должность", self.role_combo)

        self.surname_edit = self._line_edit("badge_surname", "surname")
        self.name_edit = self._line_edit("badge_name", "name")
        self.patronymic_edit = self._line_edit("badge_patronymic", "patronymic")
        self.phone_edit = self._line_edit("badge_phone", "phone")
        form.addRow("Фамилия", self.surname_edit)
        form.addRow("Имя", self.name_edit)
        form.addRow("Отчество", self.patronymic_edit)
        form.addRow("Телефон", self.phone_edit)
        return card

    def _build_photo_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("BadgePhotoCard")
        card.setProperty("role", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("Фотография 3:4")
        layout.addWidget(title)

        self.photo_status = QLabel("Фото не выбрано")
        self.photo_status.setObjectName("BadgePhotoStatus")
        self.photo_status.setProperty("role", "muted")
        self.photo_status.setWordWrap(True)
        layout.addWidget(self.photo_status)

        self.photo_button = QPushButton("Выбрать и кадрировать фото")
        self.photo_button.setObjectName("BadgePhotoButton")
        self.photo_button.clicked.connect(self._select_photo)
        self._field_widgets["photo_path"] = self.photo_button
        layout.addWidget(self.photo_button)
        return card

    def _build_validity_card(self) -> QFrame:
        card, form = self._form_card("BadgeValidityCard")
        self.issue_edit = self._line_edit("badge_issue_date", "issue_date")
        self.valid_until_edit = self._line_edit("badge_valid_until", "valid_until")
        form.addRow("Выдан", self.issue_edit)
        form.addRow("Действителен до", self.valid_until_edit)

        buttons = QWidget()
        row = QHBoxLayout(buttons)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.one_year_button = QPushButton("+1 год")
        self.one_year_button.setObjectName("BadgeOneYearButton")
        self.one_year_button.clicked.connect(lambda: self._viewmodel.set_years(1))
        row.addWidget(self.one_year_button)
        self.five_year_button = QPushButton("+5 лет")
        self.five_year_button.setObjectName("BadgeFiveYearButton")
        self.five_year_button.clicked.connect(lambda: self._viewmodel.set_years(5))
        row.addWidget(self.five_year_button)
        row.addStretch(1)
        form.addRow("Срок", buttons)
        return card

    def _build_print_card(self) -> QFrame:
        card, form = self._form_card("BadgePrintSettings")

        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("BadgePrintMode")
        self.mode_combo.addItem("Пластиковая карта 85×54 мм", "card")
        self.mode_combo.addItem("A4 — 3×3, 9 копий", "a4_grid")
        self.mode_combo.addItem("A4 — один по центру", "a4_single")
        self.mode_combo.currentIndexChanged.connect(self._print_mode_changed)
        form.addRow("Формат", self.mode_combo)

        self.printer_combo = QComboBox()
        self.printer_combo.setObjectName("BadgePrinter")
        printers = self._viewmodel.printers() or ("По умолчанию",)
        self.printer_combo.addItems(printers)
        form.addRow("Принтер", self.printer_combo)
        return card

    def _build_actions(self) -> QWidget:
        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addStretch(1)

        self.save_button = QPushButton("Сохранить PDF")
        self.save_button.setObjectName("BadgeSavePdfButton")
        self.save_button.setProperty("role", "primary")
        self.save_button.clicked.connect(self._save_pdf)
        layout.addWidget(self.save_button)

        self.print_button = QPushButton("Напечатать")
        self.print_button.setObjectName("BadgePrintButton")
        self.print_button.setProperty("role", "accent")
        self.print_button.clicked.connect(self._print)
        layout.addWidget(self.print_button)
        return actions

    def _build_preview_panel(self) -> QFrame:
        card = QFrame()
        card.setProperty("role", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(QLabel("Предпросмотр пропуска работника"))

        self.preview = ImagePreview()
        self.preview.setObjectName("BadgePreview")
        layout.addWidget(self.preview, 1)

        self.status_label = QLabel("Готово к вводу данных")
        self.status_label.setObjectName("BadgeStatus")
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
        data = state.data
        self._set_combo_text(self.park_combo, data.park)
        self._set_line_text(self.tab_num_edit, data.tab_num)
        self._set_combo_text(self.role_combo, data.role)
        self._set_line_text(self.surname_edit, data.surname)
        self._set_line_text(self.name_edit, data.name)
        self._set_line_text(self.patronymic_edit, data.patronymic)
        self._set_line_text(self.phone_edit, data.phone)
        self._set_line_text(self.issue_edit, data.issue_date)
        self._set_line_text(self.valid_until_edit, data.valid_until)
        self.photo_path = data.photo_path
        self.photo_status.setText("Фото выбрано и подготовлено" if data.photo_path else "Фото не выбрано")

        index = self.mode_combo.findData(state.print_mode)
        if index >= 0 and index != self.mode_combo.currentIndex():
            old = self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(index)
            self.mode_combo.blockSignals(old)

    def _show_validation(self, issues) -> None:
        for widget in self._field_widgets.values():
            self._set_invalid(widget, False)
        for issue in issues:
            widget = self._field_widgets.get(issue.field)
            if widget is not None:
                self._set_invalid(widget, True)
        if issues:
            self._show_status(issues[0].message)

    def _select_photo(self) -> None:
        source = self._open_image()
        if source is None:
            return
        cropped = self._crop_image(source, self)
        if cropped is None:
            return
        try:
            self._viewmodel.store_photo(cropped)
        except Exception as exc:
            self._show_status(f"Не удалось сохранить фотографию: {exc}")

    def _print_mode_changed(self) -> None:
        mode = self.mode_combo.currentData()
        if mode:
            self._viewmodel.set_print_mode(mode)

    def _save_pdf(self) -> None:
        if not self._confirm_output_warnings():
            return
        path = self._save_dialog(self._suggested_prefix())
        if path:
            self._viewmodel.save_pdf(path)

    def _print(self) -> None:
        if not self._confirm_output_warnings():
            return
        self._viewmodel.print_badge(self.printer_combo.currentText())

    def _confirm_output_warnings(self) -> bool:
        issues = self._viewmodel.validate()
        if issues:
            return False
        warnings = self._viewmodel.warnings()
        if warnings.duplicates and not self._confirm_warning("duplicates", warnings.duplicates):
            return False
        if warnings.blacklist and not self._confirm_warning("blacklist", warnings.blacklist):
            return False
        return True

    def _refresh_preview(self) -> None:
        self._viewmodel.refresh_preview()

    def _suggested_prefix(self) -> str:
        data = self._viewmodel.state.data
        tab_num = data.tab_num.strip() or "00001"
        surname = data.surname.strip() or "Сотрудник"
        mode = self._viewmodel.state.print_mode
        if mode == "a4_grid":
            return f"Пропуска_{tab_num}_9шт_А4"
        if mode == "a4_single":
            return f"Пропуск_{tab_num}_1шт_А4"
        return f"Пропуск_{tab_num}_{surname}_CR80"

    def _set_busy(self, busy: bool) -> None:
        self.save_button.setEnabled(not busy)
        self.print_button.setEnabled(not busy)
        self.photo_button.setEnabled(not busy)

    def _show_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _line_edit(self, object_name: str, field: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setObjectName(object_name)
        edit.textChanged.connect(partial(self._viewmodel.set_field, field))
        self._field_widgets[field] = edit
        return edit

    @staticmethod
    def _form_card(object_name: str) -> tuple[QFrame, QFormLayout]:
        card = QFrame()
        card.setObjectName(object_name)
        card.setProperty("role", "card")
        form = QFormLayout(card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        return card, form

    @staticmethod
    def _set_line_text(edit: QLineEdit, value) -> None:
        text = str(value or "")
        if edit.text() == text:
            return
        old = edit.blockSignals(True)
        edit.setText(text)
        edit.blockSignals(old)

    @staticmethod
    def _set_combo_text(combo: QComboBox, value) -> None:
        text = str(value or "")
        if combo.currentText() == text:
            return
        old = combo.blockSignals(True)
        index = combo.findText(text)
        if index >= 0:
            combo.setCurrentIndex(index)
        elif combo.isEditable():
            combo.setEditText(text)
        combo.blockSignals(old)

    @staticmethod
    def _set_invalid(widget: QWidget, invalid: bool) -> None:
        if widget.property("invalid") is invalid:
            return
        widget.setProperty("invalid", invalid)
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)

    @staticmethod
    def _default_open_image():
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Выберите фотографию сотрудника",
            "",
            "Изображения (*.jpg *.jpeg *.png *.bmp *.webp)",
        )
        if not path:
            return None
        with Image.open(path) as source:
            return source.copy()

    @staticmethod
    def _default_crop_image(image, parent):
        dialog = PhotoCropDialog(image, parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        cropped, _box = dialog.cropped_image()
        return cropped

    @staticmethod
    def _default_save_dialog(prefix: str) -> str:
        path, _ = QFileDialog.getSaveFileName(
            None,
            "Сохранить пропуск работника",
            f"{prefix}.pdf",
            "PDF (*.pdf)",
        )
        return path

    @staticmethod
    def _default_confirm_warning(kind: str, items) -> bool:
        if kind == "duplicates":
            details = "\n".join(
                f"• {item.get('fio', '')} — до {item.get('valid_until', '')}"
                for item in items[:5]
            )
            title = "Табельный номер уже выдан"
            text = f"На этот табельный номер есть действующий пропуск:\n{details}\n\nВыдать ещё один?"
        else:
            details = "\n".join(
                f"• {item.get('created_at', '')}: {item.get('incident', '')}"
                for item in items[:5]
            )
            title = "ВНИМАНИЕ: запись в черном списке"
            text = f"ФИО найдено в реестре нарушителей:\n{details}\n\nПродолжить выдачу?"
        answer = QMessageBox.question(
            None,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
