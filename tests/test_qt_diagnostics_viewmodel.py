from getpass_app.models.diagnostics import DiagnosticsSnapshot
from getpass_qt.viewmodels.diagnostics_viewmodel import DiagnosticsViewModel


class FakePool:
    def __init__(self):
        self.started = []

    def start(self, worker):
        self.started.append(worker)


class FakeDiagnosticsService:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def snapshot(self):
        self.calls += 1
        if self.fail:
            raise RuntimeError("diagnostics failed")
        return DiagnosticsSnapshot(
            python_version="3.14.7",
            data_dir="/data",
            database_file="/data/gup.sqlite3",
            backup_dir="/data/backups",
            database_size_bytes=8192,
            sqlite_integrity="ok",
            recent_backups=("backup_2.zip", "backup_1.zip"),
        )


def test_refresh_dispatches_worker_without_eager_snapshot(qtbot):
    service = FakeDiagnosticsService()
    pool = FakePool()
    vm = DiagnosticsViewModel(service, pool=pool)
    snapshots = []
    busy = []
    vm.snapshot_changed.connect(snapshots.append)
    vm.busy_changed.connect(busy.append)

    assert vm.refresh() is True
    assert service.calls == 0
    assert busy == [True]
    assert len(pool.started) == 1

    pool.started[0].run()

    assert service.calls == 1
    assert snapshots[-1].sqlite_integrity == "ok"
    assert vm.snapshot == snapshots[-1]
    assert busy == [True, False]


def test_refresh_failure_emits_error_and_clears_busy(qtbot):
    service = FakeDiagnosticsService()
    service.fail = True
    pool = FakePool()
    vm = DiagnosticsViewModel(service, pool=pool)
    failures = []
    vm.operation_failed.connect(failures.append)

    assert vm.refresh() is True
    pool.started[0].run()

    assert failures == ["diagnostics failed"]
    assert vm.busy is False
    assert vm.snapshot is None


def test_refresh_while_busy_is_rejected(qtbot):
    pool = FakePool()
    vm = DiagnosticsViewModel(FakeDiagnosticsService(), pool=pool)

    assert vm.refresh() is True
    assert vm.refresh() is False
    assert len(pool.started) == 1
