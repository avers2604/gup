from PySide6.QtCore import QObject, Signal
from PySide6.QtCore import Qt

from getpass_app.models.backup import BackupCreated, BackupInspection, BackupRestored
from getpass_qt.views.backups import BackupsPage


class FakeBackupsViewModel(QObject):
    inspection_ready = Signal(object)
    backup_created = Signal(object)
    backup_restored = Signal(object)
    busy_changed = Signal(bool)
    operation_failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.calls = []

    def create(self, path, password):
        self.calls.append(("create", path, password))
        return True

    def inspect(self, path, password):
        self.calls.append(("inspect", path, password))
        return True

    def restore(self, path, password):
        self.calls.append(("restore", path, password))
        return True

    def cancel(self):
        self.calls.append(("cancel",))


def _page(qtbot):
    vm = FakeBackupsViewModel()
    page = BackupsPage(
        vm,
        save_path_dialog=lambda encrypted: "copy.gupbak" if encrypted else "copy.zip",
        open_path_dialog=lambda: "restore.gupbak",
        new_password_dialog=lambda: "very-secret-123",
        password_dialog=lambda: "restore-secret-123",
        confirm_restore=lambda inspection: True,
    )
    qtbot.addWidget(page)
    return page, vm


def test_backup_page_creates_protected_and_plain_archives(qtbot):
    page, vm = _page(qtbot)

    qtbot.mouseClick(page.create_protected_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(page.create_zip_button, Qt.MouseButton.LeftButton)

    assert vm.calls == [
        ("create", "copy.gupbak", "very-secret-123"),
        ("create", "copy.zip", None),
    ]


def test_backup_page_inspects_before_enabling_restore(qtbot):
    page, vm = _page(qtbot)
    assert page.restore_button.isEnabled() is False

    qtbot.mouseClick(page.inspect_button, Qt.MouseButton.LeftButton)
    assert vm.calls[-1] == ("inspect", "restore.gupbak", "restore-secret-123")

    inspection = BackupInspection(
        path="restore.gupbak",
        accepted=("data/gup.sqlite3", "data/settings.json"),
        skipped=("foreign.exe",),
        encrypted=True,
    )
    vm.inspection_ready.emit(inspection)

    assert page.restore_button.isEnabled() is True
    assert "2" in page.inspection_label.text()
    assert "1" in page.inspection_label.text()

    qtbot.mouseClick(page.restore_button, Qt.MouseButton.LeftButton)
    assert vm.calls[-1] == ("restore", "restore.gupbak", "restore-secret-123")


def test_backup_page_reports_results_and_restart_requirement(qtbot):
    page, vm = _page(qtbot)

    vm.backup_created.emit(BackupCreated("copy.zip", 5, 4096, False))
    assert "5" in page.status_label.text()

    vm.backup_restored.emit(BackupRestored("copy.zip", 3, ()))
    assert "перезапуст" in page.status_label.text().lower()
