from getpass_app.models.diagnostics import DiagnosticsSnapshot
from getpass_app.services.diagnostics_service import DiagnosticsService


class FakeConnection:
    def __init__(self, value="ok", *, error=None):
        self._value = value
        self._error = error
        self.closed = False

    def execute(self, sql):
        assert sql == "PRAGMA integrity_check"
        if self._error is not None:
            raise self._error
        return self

    def fetchone(self):
        return (self._value,)

    def close(self):
        self.closed = True


def test_snapshot_collects_paths_size_integrity_and_recent_backups():
    connection = FakeConnection()
    names = [f"backup_2026-09-{day:02d}.zip" for day in range(1, 13)]
    names += ["notes.txt", "manual.zip"]
    service = DiagnosticsService(
        data_dir="/data",
        database_file="/data/gup.sqlite3",
        backup_dir="/data/backups",
        python_version=lambda: "3.14.7",
        path_exists=lambda path: path == "/data/gup.sqlite3",
        getsize=lambda path: 8192,
        isdir=lambda path: path == "/data/backups",
        listdir=lambda path: names,
        sqlite_connect=lambda path, timeout=3: connection,
    )

    snapshot = service.snapshot()

    assert snapshot == DiagnosticsSnapshot(
        python_version="3.14.7",
        data_dir="/data",
        database_file="/data/gup.sqlite3",
        backup_dir="/data/backups",
        database_size_bytes=8192,
        sqlite_integrity="ok",
        recent_backups=tuple(sorted(names[:12], reverse=True)[:10]),
    )
    assert snapshot.database_size_text == "8 КБ"
    assert connection.closed is True


def test_snapshot_reports_missing_database_without_connecting():
    connected = []
    service = DiagnosticsService(
        data_dir="/data",
        database_file="/data/missing.sqlite3",
        backup_dir="/data/backups",
        python_version=lambda: "3.13.15",
        path_exists=lambda _path: False,
        getsize=lambda _path: 0,
        isdir=lambda _path: False,
        listdir=lambda _path: [],
        sqlite_connect=lambda *_args, **_kwargs: connected.append(True),
    )

    snapshot = service.snapshot()

    assert snapshot.database_size_bytes is None
    assert snapshot.database_size_text == "нет"
    assert snapshot.sqlite_integrity == "нет"
    assert snapshot.recent_backups == ()
    assert connected == []


def test_snapshot_turns_sqlite_failure_into_operator_diagnostic():
    connection = FakeConnection(error=RuntimeError("database is locked"))
    service = DiagnosticsService(
        data_dir="/data",
        database_file="/data/gup.sqlite3",
        backup_dir="/data/backups",
        python_version=lambda: "3.14.7",
        path_exists=lambda _path: True,
        getsize=lambda _path: 1024,
        isdir=lambda _path: False,
        listdir=lambda _path: [],
        sqlite_connect=lambda path, timeout=3: connection,
    )

    snapshot = service.snapshot()

    assert snapshot.sqlite_integrity == "ошибка: database is locked"
    assert connection.closed is True


def test_database_size_text_uses_integer_kilobytes_like_legacy_ui():
    snapshot = DiagnosticsSnapshot(
        python_version="3.14.7",
        data_dir="/data",
        database_file="/data/gup.sqlite3",
        backup_dir="/data/backups",
        database_size_bytes=1535,
        sqlite_integrity="ok",
        recent_backups=(),
    )

    assert snapshot.database_size_text == "1 КБ"
