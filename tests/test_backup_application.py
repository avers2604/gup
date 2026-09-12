from getpass_app.models.backup import (
    BackupCreated,
    BackupInspection,
    BackupRestored,
)
from getpass_app.services.backup_service import BackupService


def _service(calls):
    def create(path, password=None):
        calls.append(("create", path, password))
        return 7, 4096

    def inspect(path, password=None):
        calls.append(("inspect", path, password))
        return ["data/settings.json", "data/gup.sqlite3"], ["other.exe"]

    def restore(path, password=None):
        calls.append(("restore", path, password))
        return 2, ["other.exe"]

    return BackupService(
        create_backup=create,
        inspect_backup=inspect,
        restore_backup=restore,
    )


def test_create_projects_encrypted_backup_and_forwards_password():
    calls = []
    service = _service(calls)

    result = service.create("backup.gupbak", "very-secret-123")

    assert result == BackupCreated(
        path="backup.gupbak",
        file_count=7,
        byte_count=4096,
        encrypted=True,
    )
    assert calls == [("create", "backup.gupbak", "very-secret-123")]


def test_create_plain_zip_does_not_invent_password():
    calls = []
    service = _service(calls)

    result = service.create("backup.zip", None)

    assert result.encrypted is False
    assert calls == [("create", "backup.zip", None)]


def test_inspect_preserves_accepted_skipped_and_encryption_kind():
    calls = []
    service = _service(calls)

    result = service.inspect("backup.gupbak", "very-secret-123")

    assert result == BackupInspection(
        path="backup.gupbak",
        accepted=("data/settings.json", "data/gup.sqlite3"),
        skipped=("other.exe",),
        encrypted=True,
    )
    assert result.can_restore is True
    assert calls == [("inspect", "backup.gupbak", "very-secret-123")]


def test_inspect_empty_archive_cannot_restore():
    service = BackupService(
        create_backup=lambda *_args, **_kwargs: (0, 0),
        inspect_backup=lambda *_args, **_kwargs: ([], ["unexpected.bin"]),
        restore_backup=lambda *_args, **_kwargs: (0, []),
    )

    result = service.inspect("empty.zip", None)

    assert result.can_restore is False
    assert result.accepted == ()
    assert result.skipped == ("unexpected.bin",)


def test_restore_projects_result_and_keeps_core_skipped_list():
    calls = []
    service = _service(calls)

    result = service.restore("backup.zip", None)

    assert result == BackupRestored(
        path="backup.zip",
        restored_count=2,
        skipped=("other.exe",),
    )
    assert calls == [("restore", "backup.zip", None)]


def test_encrypted_path_is_case_insensitive():
    calls = []
    service = _service(calls)

    result = service.inspect("BACKUP.GUPBAK", "password-123")

    assert result.encrypted is True
