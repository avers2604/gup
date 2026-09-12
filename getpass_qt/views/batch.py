from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from getpass_app.models.employee_badge import BADGE_PARKS
from getpass_qt.models.batch_review_table_model import BatchReviewTableModel


class BatchPage(QWidget):
    def __init__(
        self,
        viewmodel,
        *,
        choose_csv=None,
        choose_template=None,
        choose_pdf=None,
        confirm_warnings=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("BatchPage")
        self._viewmodel = viewmodel
        self._choose_csv = choose_csv or self._default_choose_csv
        self._choose_template = choose_template or self._default_choose_template
        self._choose_pdf = choose_pdf or self._default_choose_pdf
        self._confirm_warnings = confirm_warnings or self._default_confirm_warnings

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.addWidget(self._build_setup_card())
        root.addWidget(self._build_review_card(), 1)
        root.addWidget(self._build_output_card())

        self._connect_viewmodel()
        self._sync_kind(self._viewmodel.kind)
        self._sync_review(self._viewmodel.review)
        self._set_busy(self._viewmodel.busy)

    def _build_setup_card(self) -> QWidget:
        card = QFrame()
        card.setProperty("role", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Массовая печать")
        title.setObjectName("BatchTitle")
        layout.addWidget(title)
        hint = QLabel(
            "Выберите тип документов, скачайте CSV-шаблон, заполните его и "
            "проверьте импорт перед формированием PDF."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "muted")
        layout.addWidget(hint)

        self.kind_combo = QComboBox()
        self.kind_combo.setObjectName("BatchKind")
        self.kind_combo.addItem("Пропуска ТС", "pass")
        self.kind_combo.addItem("Пропуска работников", "badge")
        layout.addWidget(self.kind_combo)

        common_form = QFormLayout()
        self.issue_date_edit = QLineEdit()
        self.issue_date_edit.setPlaceholderText("ДД.ММ.ГГГГ")
        self.valid_until_edit = QLineEdit()
        self.valid_until_edit.setPlaceholderText("ДД.ММ.ГГГГ")
        common_form.addRow("Дата выдачи", self.issue_date_edit)
        common_form.addRow("Действителен до", self.valid_until_edit)
        layout.addLayout(common_form)

        self.defaults_stack = QStackedWidget()
        self.defaults_stack.setObjectName("BatchDefaults")
        self.pass_defaults = self._build_pass_defaults()
        self.badge_defaults = self._build_badge_defaults()
        self.defaults_stack.addWidget(self.pass_defaults)
        self.defaults_stack.addWidget(self.badge_defaults)
        layout.addWidget(self.defaults_stack)

        buttons = QHBoxLayout()
        self.template_button = QPushButton("Сохранить CSV-шаблон")
        self.template_button.setObjectName("BatchTemplateButton")
        buttons.addWidget(self.template_button)
        self.import_button = QPushButton("Выбрать CSV")
        self.import_button.setObjectName("BatchImportButton")
        self.import_button.setProperty("role", "primary")
        buttons.addWidget(self.import_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return card

    def _build_pass_defaults(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("BatchPassDefaults")
        form = QFormLayout(frame)
        self.otb_post_edit = QLineEdit()
        self.otb_name_edit = QLineEdit()
        self.temporary_check = QCheckBox("Временные пропуска")
        form.addRow("Должность ОТБ", self.otb_post_edit)
        form.addRow("ФИО ОТБ", self.otb_name_edit)
        form.addRow("", self.temporary_check)
        return frame

    def _build_badge_defaults(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("BatchBadgeDefaults")
        form = QFormLayout(frame)
        self.park_combo = QComboBox()
        self.park_combo.addItems(BADGE_PARKS)
        form.addRow("Подразделение по умолчанию", self.park_combo)
        return frame

    def _build_review_card(self) -> QWidget:
        card = QFrame()
        card.setProperty("role", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self.summary_label = QLabel("CSV ещё не выбран.")
        self.summary_label.setObjectName("BatchSummary")
        layout.addWidget(self.summary_label)

        self.review_table = QTableView()
        self.review_table.setObjectName("BatchReviewTable")
        self.review_table.setAlternatingRowColors(True)
        self.review_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.review_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.review_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.review_table.verticalHeader().setVisible(False)
        self.review_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.review_table, 1)
        return card

    def _build_output_card(self) -> QWidget:
        card = QFrame()
        card.setProperty("role", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self.status_label = QLabel("Готово к импорту CSV.")
        self.status_label.setObjectName("BatchStatus")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("BatchProgress")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.setObjectName("BatchCancelButton")
        self.cancel_button.setEnabled(False)
        actions.addWidget(self.cancel_button)
        self.generate_button = QPushButton("Сформировать PDF")
        self.generate_button.setObjectName("BatchGenerateButton")
        self.generate_button.setProperty("role", "accent")
        actions.addWidget(self.generate_button)
        layout.addLayout(actions)
        return card

    def _connect_viewmodel(self) -> None:
        self.kind_combo.currentIndexChanged.connect(self._kind_selected)
        self.template_button.clicked.connect(self._export_template)
        self.import_button.clicked.connect(self._import_csv)
        self.generate_button.clicked.connect(self._generate_pdf)
        self.cancel_button.clicked.connect(self._viewmodel.cancel)

        self._viewmodel.kind_changed.connect(self._sync_kind)
        self._viewmodel.review_changed.connect(self._sync_review)
        self._viewmodel.busy_changed.connect(self._set_busy)
        self._viewmodel.progress_changed.connect(self._set_progress)
        self._viewmodel.output_succeeded.connect(self._output_succeeded)
        self._viewmodel.operation_failed.connect(self._operation_failed)

    def _kind_selected(self, index: int) -> None:
        kind = self.kind_combo.itemData(index)
        if kind:
            self._viewmodel.set_kind(kind)

    def _sync_kind(self, kind: str) -> None:
        index = self.kind_combo.findData(kind)
        if index >= 0 and index != self.kind_combo.currentIndex():
            self.kind_combo.setCurrentIndex(index)
        self.defaults_stack.setCurrentIndex(0 if kind == "pass" else 1)

    def _sync_review(self, review) -> None:
        if review is None:
            self.review_table.setModel(None)
            self.summary_label.setText("CSV ещё не выбран.")
        else:
            model = self.review_table.model()
            if isinstance(model, BatchReviewTableModel):
                model.set_review(review)
            else:
                self.review_table.setModel(
                    BatchReviewTableModel(review, self.review_table)
                )
            self.review_table.resizeColumnsToContents()
            self.summary_label.setText(
                f"Записей: {review.total} · С ошибками: {review.error_count} · "
                f"Предупреждений: {review.warning_count}"
            )
        self._sync_generate_enabled()

    def _apply_defaults(self) -> None:
        if self._viewmodel.kind == "pass":
            self._viewmodel.set_pass_defaults(
                issue_date=self.issue_date_edit.text().strip(),
                valid_until=self.valid_until_edit.text().strip(),
                otb_post=self.otb_post_edit.text().strip(),
                otb_name=self.otb_name_edit.text().strip(),
                is_temporary=self.temporary_check.isChecked(),
            )
            return
        self._viewmodel.set_badge_defaults(
            park=self.park_combo.currentText().strip(),
            issue_date=self.issue_date_edit.text().strip(),
            valid_until=self.valid_until_edit.text().strip(),
        )

    def _export_template(self) -> None:
        path = self._choose_template(self._viewmodel.kind)
        if path and self._viewmodel.export_template(path):
            self.status_label.setText(f"CSV-шаблон сохранён: {path}")

    def _import_csv(self) -> None:
        path = self._choose_csv(self._viewmodel.kind)
        if not path:
            return
        self._apply_defaults()
        if self._viewmodel.load_csv(path):
            self.status_label.setText(f"CSV загружен: {path}")

    def _generate_pdf(self) -> None:
        review = self._viewmodel.review
        if review is None or not review.can_generate:
            return
        if review.warning_count and not self._confirm_warnings(review.warning_count):
            return
        path = self._choose_pdf(self._viewmodel.kind, review.total)
        if path:
            self._viewmodel.generate_pdf(path)

    def _set_busy(self, busy: bool) -> None:
        self.kind_combo.setEnabled(not busy)
        self.template_button.setEnabled(not busy)
        self.import_button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        if busy:
            self.status_label.setText("Формирование PDF…")
        self._sync_generate_enabled()

    def _sync_generate_enabled(self) -> None:
        self.generate_button.setEnabled(self._viewmodel.can_generate)

    def _set_progress(self, current: int, total: int) -> None:
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(current)

    def _output_succeeded(self, result) -> None:
        self.status_label.setText(
            f"Готово: {result.item_count} записей, {result.page_count} стр. · "
            f"{result.path}"
        )

    def _operation_failed(self, message: str) -> None:
        self.status_label.setText(message)

    def _default_choose_csv(self, kind: str) -> str:
        title = "CSV с пропусками ТС" if kind == "pass" else "CSV с пропусками работников"
        path, _filter = QFileDialog.getOpenFileName(
            self,
            title,
            "",
            "CSV (*.csv);;Все файлы (*.*)",
        )
        return path

    def _default_choose_template(self, kind: str) -> str:
        filename = (
            "Шаблон_массовой_печати_ТС.csv"
            if kind == "pass"
            else "Шаблон_массовой_печати_бейджей.csv"
        )
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Сохранить CSV-шаблон",
            filename,
            "CSV (*.csv)",
        )
        return path

    def _default_choose_pdf(self, kind: str, count: int) -> str:
        prefix = "Массовая_печать_ТС" if kind == "pass" else "Массовая_печать_бейджей"
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Сохранить PDF",
            f"{prefix}_{count}шт.pdf",
            "PDF (*.pdf)",
        )
        return path

    def _default_confirm_warnings(self, count: int) -> bool:
        answer = QMessageBox.question(
            self,
            "Подтвердить предупреждения",
            f"Найдено предупреждений: {count}. Продолжить формирование PDF?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
