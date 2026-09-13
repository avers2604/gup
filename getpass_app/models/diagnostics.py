from dataclasses import dataclass


@dataclass(frozen=True)
class DiagnosticsSnapshot:
    python_version: str
    data_dir: str
    database_file: str
    backup_dir: str
    database_size_bytes: int | None
    sqlite_integrity: str
    recent_backups: tuple[str, ...]

    @property
    def database_size_text(self) -> str:
        if self.database_size_bytes is None:
            return "нет"
        return f"{self.database_size_bytes // 1024} КБ"
