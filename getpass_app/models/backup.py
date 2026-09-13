from dataclasses import dataclass


@dataclass(frozen=True)
class BackupCreated:
    path: str
    file_count: int
    byte_count: int
    encrypted: bool


@dataclass(frozen=True)
class BackupInspection:
    path: str
    accepted: tuple[str, ...]
    skipped: tuple[str, ...]
    encrypted: bool

    @property
    def can_restore(self) -> bool:
        return bool(self.accepted)


@dataclass(frozen=True)
class BackupRestored:
    path: str
    restored_count: int
    skipped: tuple[str, ...]
