from getpass_app.models.backup import (
    BackupCreated,
    BackupInspection,
    BackupRestored,
)
from getpass_qt.viewmodels.backups_viewmodel import BackupsViewModel


class FakePool:
    def __init__(self):
        self.started = []

    def start(self, worker):
        self.started.append(worker)


class FakeBackupService:
    def __init__(self):
        self.calls = []
        self.fail_restore = False

    def create(self, path, password):
        self.calls.append(("create", path, password))
        return BackupCreated(path, 4, 2048, path.lower().endswith(".gupbak"))

    def inspect(self, path, password):
        self.calls.append(("inspect", path, password))
        return BackupInspection(path, ("data/gup.sqlite3",), (), path.lower().endswith(".gupbak"))

    def restore(self, path, password):
        self.calls.append(("restore", path, password))
        if self.fail_restore:
            raise RuntimeError("restore failed")
        return BackupRestored(path, 1, ())


def test_create_dispatches_worker_without_eager_service_call(qtbot):
    service = FakeBackupService()
    pool = FakePool()
    vm = BackupsViewModel(service, pool=pool)
    created = []
    busy = []
    vm.backup_created.connect(created.append)
    vm.busy_changed.connect(busy.append)

    assert vm.create("backup.gupbak", "password-123") is True
    assert service.calls == []
    assert busy == [True]
    assert len(pool.started) == 1

    pool.started[0].run()

    assert service.calls == [("create", "backup.gupbak", "password-123")]
    assert created[0].path == "backup.gupbak"
    assert busy == [True, False]


def test_inspect_then_matching_restore_requires_completed_inspection(qtbot):
    service = FakeBackupService()
    pool = FakePool()
    vm = BackupsViewModel(service, pool=pool)
    inspections = []
    restored = []
    failures = []
    vm.inspection_ready.connect(inspections.append)
    vm.backup_restored.connect(restored.append)
    vm.operation_failed.connect(failures.append)

    assert vm.restore("backup.zip", None) is False
    assert not pool.started

    assert vm.inspect("backup.zip", None) is True
    assert service.calls == []
    pool.started[-1].run()

    assert inspections[-1].path == "backup.zip"
    assert vm.restore("other.zip", None) is False
    assert len(pool.started) == 1

    assert vm.restore("backup.zip", None) is True
    assert len(pool.started) == 2
    assert service.calls == [("inspect", "backup.zip", None)]
    pool.started[-1].run()

    assert service.calls[-1] == ("restore", "backup.zip", None)
    assert restored[-1].restored_count == 1
    assert any("проверьте" in message.lower() for message in failures)


def test_restore_failure_invalidates_prior_inspection(qtbot):
    service = FakeBackupService()
    pool = FakePool()
    vm = BackupsViewModel(service, pool=pool)
    failures = []
    vm.operation_failed.connect(failures.append)

    vm.inspect("backup.gupbak", "password-123")
    pool.started[-1].run()
    service.fail_restore = True

    assert vm.restore("backup.gupbak", "password-123") is True
    pool.started[-1].run()
    assert failures[-1] == "restore failed"

    worker_count = len(pool.started)
    assert vm.restore("backup.gupbak", "password-123") is False
    assert len(pool.started) == worker_count


def test_cancel_marks_current_worker(qtbot):
    pool = FakePool()
    vm = BackupsViewModel(FakeBackupService(), pool=pool)

    vm.create("backup.zip", None)
    vm.cancel()

    assert pool.started[0].cancelled.is_set()
