from PySide6.QtCore import QObject, Qt, Signal

from getpass_app.models.diagnostics import DiagnosticsSnapshot
from getpass_qt.views.diagnostics import DiagnosticsPage


class FakeDiagnosticsViewModel(QObject):
    snapshot_changed = Signal(object)
    busy_changed = Signal(bool)
    operation_failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.calls = []

    def refresh(self):
        self.calls.append("refresh")
        return True

    def cancel(self):
        self.calls.append("cancel")


def _snapshot():
    return DiagnosticsSnapshot(
        python_version="3.14.7",
        data_dir="/data",
        database_file="/data/gup.sqlite3",
        backup_dir="/data/backups",
        database_size_bytes=8192,
        sqlite_integrity="ok",
        recent_backups=("backup_2.zip", "backup_1.zip"),
    )


def test_diagnostics_page_refreshes_and_renders_snapshot(qtbot):
    vm = FakeDiagnosticsViewModel()
    page = DiagnosticsPage(vm)
    qtbot.addWidget(page)

    qtbot.mouseClick(page.refresh_button, Qt.MouseButton.LeftButton)
    assert vm.calls == ["refresh"]

    vm.snapshot_changed.emit(_snapshot())

    assert "3.14.7" in page.python_label.text()
    assert "/data" in page.data_dir_label.text()
    assert "8 КБ" in page.database_size_label.text()
    assert "ok" in page.integrity_label.text()
    assert "backup_2.zip" in page.recent_backups_label.text()


def test_diagnostics_page_busy_and_error_state(qtbot):
    vm = FakeDiagnosticsViewModel()
    page = DiagnosticsPage(vm)
    qtbot.addWidget(page)

    vm.busy_changed.emit(True)
    assert page.refresh_button.isEnabled() is False

    vm.busy_changed.emit(False)
    assert page.refresh_button.isEnabled() is True

    vm.operation_failed.emit("diagnostics failed")
    assert page.status_label.text() == "diagnostics failed"
