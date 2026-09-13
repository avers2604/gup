from __future__ import annotations

from getpass_app.models.backup import (
    BackupCreated,
    BackupInspection,
    BackupRestored,
)
from getpass_core import backup


class BackupService:
    def __init__(
        self,
        *,
        create_backup=backup.create_backup,
        inspect_backup=backup.inspect_backup,
        restore_backup=backup.restore_backup,
    ) -> None:
        self._create_backup = create_backup
        self._inspect_backup = inspect_backup
        self._restore_backup = restore_backup

    def create(self, path: str, password: str | None) -> BackupCreated:
        file_count, byte_count = self._create_backup(path, password=password)
        return BackupCreated(
            path=path,
            file_count=file_count,
            byte_count=byte_count,
            encrypted=self._is_encrypted(path),
        )

    def inspect(self, path: str, password: str | None) -> BackupInspection:
        accepted, skipped = self._inspect_backup(path, password=password)
        return BackupInspection(
            path=path,
            accepted=tuple(accepted),
            skipped=tuple(skipped),
            encrypted=self._is_encrypted(path),
        )

    def restore(self, path: str, password: str | None) -> BackupRestored:
        restored_count, skipped = self._restore_backup(path, password=password)
        return BackupRestored(
            path=path,
            restored_count=restored_count,
            skipped=tuple(skipped),
        )

    @staticmethod
    def _is_encrypted(path: str) -> bool:
        return path.lower().endswith(".gupbak")
