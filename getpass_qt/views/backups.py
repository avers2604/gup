from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class BackupsPage(QWidget):
    def __init__(
        self,
        viewmodel,
        *,
        save_path_dialog=None,
        open_path_dialog=None,
        new_password_dialog=None,
        password_dialog=None,
        confirm_restore=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("BackupsPage")
        self._viewmodel = viewmodel
        self._save_path_dialog = save_path_dialog or self._default_save_path
        self._open_path_dialog = open_path_dialog or self._default_open_path
        self._new_password_dialog = new_password_dialog or self._default_new_password
        self._password_dialog = password_dialog or self._default_password
        self._confirm_restore = confirm_restore or self._default_confirm_restore
        self._restore_path = ""
        self._restore_password = None
        self._inspection = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.addWidget(self._build_intro())
        root.addWidget(self._build_create_card())
        root.addWidget(self._build_restore_card())
        root.addStretch(1)

        self._connect_viewmodel()
        self._sync_restore_button()

    def _build_intro(self) -> QWidget:
        card = QFrame()
        card.setProperty("role", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        title = QLabel("Резервные копии")
        title.setObjectName("BackupsTitle")
        layout.addWidget(title)
        hint = QLabel(
            "Защищённая копия .gupbak шифруется паролем. ZIP без пароля "
            "содержит персональные данные в незашифрованном виде."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "muted")
        layout.addWidget(hint)
        return card

    def _build_create_card(self) -> QWidget:
        card = QFrame()
        card.setProperty("role", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Создать копию"))

        actions = QHBoxLayout()
        self.create_protected_button = QPushButton("Защищённая .gupbak")
        self.create_protected_button.setObjectName("CreateProtectedBackupButton")
        self.create_protected_button.setProperty("role", "primary")
        self.create_protected_button.clicked.connect(self._create_protected)
        actions.addWidget(self.create_protected_button)

        self.create_zip_button = QPushButton("ZIP без пароля")
        self.create_zip_button.setObjectName("CreatePlainBackupButton")
        self.create_zip_button.clicked.connect(self._create_plain)
        actions.addWidget(self.create_zip_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.status_label = QLabel("Готово к работе.")
        self.status_label.setObjectName("BackupsStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setProperty("role", "muted")
        layout.addWidget(self.status_label)
        return card

    def _build_restore_card(self) -> QWidget:
        card = QFrame()
        card.setProperty("role", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Восстановить данные"))

        self.inspection_label = QLabel(
            "Сначала выберите и проверьте резервную копию."
        )
        self.inspection_label.setObjectName("BackupInspectionStatus")
        self.inspection_label.setWordWrap(True)
        self.inspection_label.setProperty("role", "muted")
        layout.addWidget(self.inspection_label)

        actions = QHBoxLayout()
        self.inspect_button = QPushButton("Выбрать и проверить")
        self.inspect_button.setObjectName("InspectBackupButton")
        self.inspect_button.clicked.connect(self._inspect_backup)
        actions.addWidget(self.inspect_button)

        self.restore_button = QPushButton("Восстановить")
        self.restore_button.setObjectName("RestoreBackupButton")
        self.restore_button.setProperty("role", "accent")
        self.restore_button.clicked.connect(self._restore_backup)
        actions.addWidget(self.restore_button)

        self.cancel_button = QPushButton("Отменить операцию")
        self.cancel_button.setObjectName("CancelBackupOperationButton")
        self.cancel_button.clicked.connect(self._viewmodel.cancel)
        actions.addWidget(self.cancel_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        return card

    def _connect_viewmodel(self) -> None:
        self._viewmodel.inspection_ready.connect(self._on_inspection)
        self._viewmodel.backup_created.connect(self._on_created)
        self._viewmodel.backup_restored.connect(self._on_restored)
        self._viewmodel.busy_changed.connect(self._set_busy)
        self._viewmodel.operation_failed.connect(self._on_error)

    def _create_protected(self) -> None:
        path = self._save_path_dialog(True)
        if not path:
            return
        password = self._new_password_dialog()
        if not password:
            return
        self._viewmodel.create(path, password)

    def _create_plain(self) -> None:
        path = self._save_path_dialog(False)
        if path:
            self._viewmodel.create(path, None)

    def _inspect_backup(self) -> None:
        path = self._open_path_dialog()
        if not path:
            return
        password = self._password_for(path)
        if path.lower().endswith(".gupbak") and not password:
            return
        self._inspection = None
        self._restore_path = path
        self._restore_password = password
        self._sync_restore_button()
        self._viewmodel.inspect(path, password)

    def _restore_backup(self) -> None:
        if self._inspection is None or not self._inspection.can_restore:
            return
        if not self._confirm_restore(self._inspection):
            return
        self._viewmodel.restore(self._restore_path, self._restore_password)

    def _on_inspection(self, inspection) -> None:
        self._inspection = inspection
        self.inspection_label.setText(
            f"Будет восстановлено: {len(inspection.accepted)}. "
            f"Будет пропущено: {len(inspection.skipped)}."
        )
        self._sync_restore_button()

    def _on_created(self, result) -> None:
        self.status_label.setText(
            f"Копия создана: {result.file_count} файлов, "
            f"{result.byte_count} байт."
        )

    def _on_restored(self, result) -> None:
        self._inspection = None
        self._sync_restore_button()
        self.status_label.setText(
            f"Восстановлено файлов: {result.restored_count}. "
            "Перезапустите приложение перед дальнейшей работой."
        )

    def _on_error(self, message: str) -> None:
        self._inspection = None
        self._sync_restore_button()
        self.status_label.setText(message)

    def _set_busy(self, busy: bool) -> None:
        self.create_protected_button.setEnabled(not busy)
        self.create_zip_button.setEnabled(not busy)
        self.inspect_button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self._sync_restore_button(busy=busy)

    def _sync_restore_button(self, *, busy: bool = False) -> None:
        can_restore = self._inspection is not None and self._inspection.can_restore
        self.restore_button.setEnabled(can_restore and not busy)

    def _password_for(self, path: str):
        if path.lower().endswith(".gupbak"):
            return self._password_dialog()
        return None

    def _default_save_path(self, encrypted: bool) -> str:
        if encrypted:
            title = "Создать защищённую резервную копию"
            file_filter = "Защищённая копия (*.gupbak)"
            default_name = "Backup_GET.gupbak"
        else:
            title = "Создать ZIP без пароля"
            file_filter = "ZIP без пароля (*.zip)"
            default_name = "Backup_GET.zip"
        path, _ = QFileDialog.getSaveFileName(
            self,
            title,
            default_name,
            file_filter,
        )
        return path

    def _default_open_path(self) -> str:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите резервную копию",
            "",
            "Резервные копии (*.gupbak *.zip)",
        )
        return path

    def _default_new_password(self):
        first = self._ask_password(
            "Пароль копии",
            "Введите пароль не короче 12 символов.",
        )
        if first is None:
            return None
        if len(first) < 12:
            QMessageBox.warning(self, "Слабый пароль", "Пароль должен содержать не менее 12 символов.")
            return None
        second = self._ask_password("Повтор пароля", "Введите пароль ещё раз.")
        if second is None:
            return None
        if first != second:
            QMessageBox.warning(self, "Пароли не совпадают", "Копия не создана.")
            return None
        return first

    def _default_password(self):
        return self._ask_password("Пароль копии", "Введите пароль резервной копии.")

    def _ask_password(self, title: str, text: str):
        value, ok = QInputDialog.getText(
            self,
            title,
            text,
            QLineEdit.EchoMode.Password,
        )
        return value if ok else None

    def _default_confirm_restore(self, inspection) -> bool:
        text = (
            f"Будет восстановлено файлов: {len(inspection.accepted)}.\n"
            f"Будет пропущено: {len(inspection.skipped)}.\n\n"
            "Текущие данные будут заменены. Продолжить?"
        )
        answer = QMessageBox.question(
            self,
            "Восстановление данных",
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
