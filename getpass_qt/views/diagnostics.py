from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class DiagnosticsPage(QWidget):
    def __init__(self, viewmodel, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DiagnosticsPage")
        self._viewmodel = viewmodel

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.addWidget(self._build_intro())
        root.addWidget(self._build_details())
        root.addStretch(1)

        self._connect_viewmodel()

    def _build_intro(self) -> QWidget:
        card = QFrame()
        card.setProperty("role", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        title = QLabel("Диагностика")
        title.setObjectName("DiagnosticsTitle")
        layout.addWidget(title)
        hint = QLabel(
            "Проверка выполняется только на чтение: пути данных, размер базы, "
            "SQLite integrity_check и список последних резервных копий."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "muted")
        layout.addWidget(hint)
        return card

    def _build_details(self) -> QWidget:
        card = QFrame()
        card.setProperty("role", "card")
        root = QVBoxLayout(card)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        self.python_label = self._add_row(grid, 0, "Версия Python")
        self.data_dir_label = self._add_row(grid, 1, "Каталог данных")
        self.database_label = self._add_row(grid, 2, "База данных")
        self.database_size_label = self._add_row(grid, 3, "Размер БД")
        self.integrity_label = self._add_row(grid, 4, "Проверка SQLite")
        self.backup_dir_label = self._add_row(grid, 5, "Резервные копии")
        self.recent_backups_label = self._add_row(grid, 6, "Последние копии")
        self.recent_backups_label.setWordWrap(True)
        root.addLayout(grid)

        self.status_label = QLabel("Нажмите «Обновить», чтобы выполнить проверку.")
        self.status_label.setObjectName("DiagnosticsStatus")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setObjectName("DiagnosticsRefreshButton")
        self.refresh_button.setProperty("role", "primary")
        self.refresh_button.clicked.connect(self._viewmodel.refresh)
        root.addWidget(self.refresh_button)
        return card

    def _connect_viewmodel(self) -> None:
        self._viewmodel.snapshot_changed.connect(self._render_snapshot)
        self._viewmodel.busy_changed.connect(self._set_busy)
        self._viewmodel.operation_failed.connect(self._show_error)

    def _render_snapshot(self, snapshot) -> None:
        self.python_label.setText(snapshot.python_version)
        self.data_dir_label.setText(snapshot.data_dir)
        self.database_label.setText(snapshot.database_file)
        self.database_size_label.setText(snapshot.database_size_text)
        self.integrity_label.setText(snapshot.sqlite_integrity)
        self.backup_dir_label.setText(snapshot.backup_dir)
        backups = "\n".join(snapshot.recent_backups) or "нет файлов"
        self.recent_backups_label.setText(backups)
        self.status_label.setText("Диагностика обновлена.")

    def _set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)
        if busy:
            self.status_label.setText("Выполняется проверка…")

    def _show_error(self, message: str) -> None:
        self.status_label.setText(message)

    @staticmethod
    def _add_row(grid: QGridLayout, row: int, title: str) -> QLabel:
        key = QLabel(title)
        key.setProperty("role", "muted")
        value = QLabel("—")
        value.setTextInteractionFlags(value.textInteractionFlags())
        grid.addWidget(key, row, 0)
        grid.addWidget(value, row, 1)
        return value
