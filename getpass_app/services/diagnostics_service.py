from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import closing

from getpass_app.models.diagnostics import DiagnosticsSnapshot
from getpass_core import config


class DiagnosticsService:
    def __init__(
        self,
        *,
        data_dir=config.DATA_DIR,
        database_file=config.DB_FILE,
        backup_dir=config.BACKUP_DIR,
        python_version=lambda: sys.version.split()[0],
        path_exists=os.path.exists,
        getsize=os.path.getsize,
        isdir=os.path.isdir,
        listdir=os.listdir,
        sqlite_connect=sqlite3.connect,
    ) -> None:
        self._data_dir = data_dir
        self._database_file = database_file
        self._backup_dir = backup_dir
        self._python_version = python_version
        self._path_exists = path_exists
        self._getsize = getsize
        self._isdir = isdir
        self._listdir = listdir
        self._sqlite_connect = sqlite_connect

    def snapshot(self) -> DiagnosticsSnapshot:
        exists = self._path_exists(self._database_file)
        size = self._getsize(self._database_file) if exists else None
        integrity = self._integrity() if exists else "нет"
        return DiagnosticsSnapshot(
            python_version=self._python_version(),
            data_dir=self._data_dir,
            database_file=self._database_file,
            backup_dir=self._backup_dir,
            database_size_bytes=size,
            sqlite_integrity=integrity,
            recent_backups=self._recent_backups(),
        )

    def _integrity(self) -> str:
        try:
            with closing(self._sqlite_connect(self._database_file, timeout=3)) as conn:
                return str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        except Exception as exc:
            return f"ошибка: {exc}"

    def _recent_backups(self) -> tuple[str, ...]:
        if not self._isdir(self._backup_dir):
            return ()
        names = (
            name for name in self._listdir(self._backup_dir)
            if name.startswith("backup_")
        )
        return tuple(sorted(names, reverse=True)[:10])
