"""Резервное копирование и восстановление данных."""
from __future__ import annotations

import filecmp
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timedelta

from . import config
from .atomic import atomic_output

MANIFEST = "manifest.txt"
_ALLOWED_PREFIXES = ("data/", "photos/", "fonts/")
_ALLOWED_FILES = ("template.png", "app_icon.ico", MANIFEST)


def _existing_file_items(paths) -> list[tuple[str, str]]:
    return [
        (path, "data/" + os.path.basename(path))
        for path in paths
        if os.path.exists(path)
    ]


def _directory_items(directory: str, prefix: str) -> list[tuple[str, str]]:
    if not os.path.isdir(directory):
        return []
    return [
        (os.path.join(directory, name), f"{prefix}/{name}")
        for name in sorted(os.listdir(directory))
        if os.path.isfile(os.path.join(directory, name))
    ]


def _backup_items() -> list[tuple[str, str]]:
    items = _existing_file_items(
        (
            config.CONFIG_FILE,
            config.LOG_CSV_FILE,
            config.LOG_XLSX_FILE,
            config.BADGE_LOG_CSV,
            config.BADGE_LOG_XLSX,
            config.CARS_CACHE_FILE,
            config.BLACKLIST_FILE,
        )
    )
    if os.path.exists(config.TEMPLATE_FILE):
        items.append((config.TEMPLATE_FILE, "template.png"))
    if os.path.exists(config.ICON_FILE):
        items.append((config.ICON_FILE, "app_icon.ico"))
    items.extend(_directory_items(config.FONTS_DIR, "fonts"))
    items.extend(_directory_items(config.PHOTO_DIR, "photos"))
    return items


def create_backup(filepath: str, password=None) -> tuple[int, int]:
    if password is not None:
        from .encryption import encrypt

        with tempfile.TemporaryDirectory(prefix="get-encrypted-") as temporary:
            plain = os.path.join(temporary, "backup.zip")
            result = _create_backup(plain)
            encrypt(plain, filepath, password)
            return result
    return _create_backup(filepath)


def _create_backup(filepath):
    """Создать архив. Возвращает (файлов, байт)."""
    items = _backup_items()
    total = 0
    temp_db_snapshot = None

    if os.path.exists(config.DB_FILE):
        fd, temp_db_snapshot = tempfile.mkstemp(prefix="gup_db_bkp_", suffix=".sqlite3")
        os.close(fd)
        try:
            with closing(sqlite3.connect(config.DB_FILE)) as src_conn, \
                    closing(sqlite3.connect(temp_db_snapshot)) as dst_conn:
                src_conn.backup(dst_conn)
                if dst_conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Повреждена база данных")
            items.append((temp_db_snapshot, "data/" + os.path.basename(config.DB_FILE)))
        except Exception:
            if os.path.exists(temp_db_snapshot):
                os.remove(temp_db_snapshot)
            raise

    try:
        with atomic_output(filepath) as temporary, zipfile.ZipFile(
            temporary, "w", zipfile.ZIP_DEFLATED
        ) as zf:
            checksums = {}
            for src, arc in items:
                digest = hashlib.sha256()
                with open(src, "rb") as stream, zf.open(arc, "w") as target:
                    while chunk := stream.read(1024 * 1024):
                        digest.update(chunk)
                        target.write(chunk)
                checksums[arc] = digest.hexdigest()
                total += os.path.getsize(src)
            zf.writestr(MANIFEST, _manifest_text(items))
            zf.writestr("checksums.json", json.dumps(checksums))
    finally:
        if temp_db_snapshot and os.path.exists(temp_db_snapshot):
            try:
                os.remove(temp_db_snapshot)
            except Exception:
                pass

    return len(items), total


def rotate_backups(retention_days: int = 14, now: datetime | None = None) -> str:
    """Создать автоматический архив и удалить архивы старше срока хранения."""
    now = now or datetime.now()
    os.makedirs(config.BACKUP_DIR, exist_ok=True)
    filename = f"backup_{now.strftime('%Y-%m-%d_%H-%M-%S')}.zip"
    filepath = os.path.join(config.BACKUP_DIR, filename)
    create_backup(filepath)
    cutoff = now - timedelta(days=retention_days)
    for name in os.listdir(config.BACKUP_DIR):
        if not name.startswith("backup_") or not name.lower().endswith(".zip") or name == filename:
            continue
        candidate = os.path.join(config.BACKUP_DIR, name)
        try:
            if datetime.fromtimestamp(os.path.getmtime(candidate)) < cutoff:
                os.remove(candidate)
        except (OSError, ValueError):
            continue
    return filepath


def _manifest_text(items) -> str:
    lines = [
        "Резервная копия системы пропусков СПб ГУП «Горэлектротранс»",
        f"Создана: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        f"Источник: {config.DATA_DIR}",
        "",
        "ВНИМАНИЕ: архив содержит персональные данные (ФИО, телефоны,",
        "госномера, фотографии) и НЕ зашифрован. Храните его на носителе",
        "с ограниченным доступом и не пересылайте по открытым каналам.",
        "",
        "Состав:",
    ]
    lines += [f"  {arc}" for _, arc in items]
    return "\n".join(lines)


def _is_allowed_archive_name(norm: str) -> bool:
    allowed = norm in _ALLOWED_FILES or norm.startswith(_ALLOWED_PREFIXES)
    safe = ".." not in norm and not norm.startswith("/") and ":" not in norm
    return allowed and safe and len(norm.split("/")) <= 2


def inspect_backup(filepath: str, password=None) -> tuple[list[str], list[str]]:
    if password is not None:
        from .encryption import decrypt

        with tempfile.TemporaryDirectory(prefix="get-inspect-") as temporary:
            plain = os.path.join(temporary, "backup.zip")
            decrypt(filepath, plain, password)
            return inspect_backup(plain)
    """Что будет восстановлено и что пропущено. Возвращает списки строк."""
    accepted: list[str] = []
    skipped: list[str] = []
    with zipfile.ZipFile(filepath, "r") as zf:
        infos = zf.infolist()
        if len(infos) > 20000 or sum(i.file_size for i in infos) > 2 * 1024**3:
            raise ValueError("Архив превышает допустимый размер")
        seen = set()
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            norm = name.replace("\\", "/")
            if norm in seen:
                raise ValueError("Повторяющееся имя в архиве")
            seen.add(norm)
            if _is_allowed_archive_name(norm):
                accepted.append(norm)
            else:
                skipped.append(name)
    return accepted, skipped


def _restore_destination(norm_name: str) -> str | None:
    direct = {
        "template.png": config.TEMPLATE_FILE,
        "app_icon.ico": config.ICON_FILE,
    }
    if norm_name in direct:
        return direct[norm_name]
    roots = (
        ("data/", config.DATA_DIR),
        ("photos/", config.PHOTO_DIR),
        ("fonts/", config.FONTS_DIR),
    )
    for prefix, root in roots:
        if norm_name.startswith(prefix):
            return os.path.join(root, os.path.basename(norm_name))
    return None


def _archive_checksums(zf: zipfile.ZipFile) -> dict[str, str] | None:
    if "checksums.json" not in zf.namelist():
        return None
    return json.loads(zf.read("checksums.json"))


def _stage_member(
    zf: zipfile.ZipFile,
    orig_name: str,
    norm_name: str,
    staged: str,
    checksums: dict[str, str] | None,
) -> None:
    with zf.open(orig_name) as src, open(staged, "wb") as out:
        shutil.copyfileobj(src, out)
    if checksums is None:
        return
    with open(staged, "rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if checksums.get(orig_name) != actual:
        raise ValueError(f"Контрольная сумма не совпала: {norm_name}")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name=?",
            (table,),
        ).fetchone()
    )


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}  # nosec B608


def _remap_badge_photo_paths(conn: sqlite3.Connection, accepted: set[str]) -> None:
    if not _table_exists(conn, "badge_journal"):
        return
    if "photo_path" not in _table_columns(conn, "badge_journal"):
        return
    rows = conn.execute("SELECT id, photo_path FROM badge_journal").fetchall()
    for record_id, photo in rows:
        if not photo:
            continue
        name = photo.replace("\\", "/").rsplit("/", 1)[-1]
        if "photos/" + name not in accepted:
            continue
        conn.execute(
            "UPDATE badge_journal SET photo_path=? WHERE id=?",
            (os.path.join(config.PHOTO_DIR, name), record_id),
        )
    conn.commit()


def _validate_staged_database(staged: str, accepted: set[str]) -> None:
    with closing(sqlite3.connect(staged)) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Повреждённая база в архиве")
        _remap_badge_photo_paths(conn, accepted)


def _stage_restore_plan(
    zf: zipfile.ZipFile,
    accepted: list[str],
    staging: str,
) -> list[tuple[str, str]]:
    checksums = _archive_checksums(zf)
    name_map = {name.replace("\\", "/"): name for name in zf.namelist()}
    accepted_set = set(accepted)
    planned: list[tuple[str, str]] = []
    for norm_name in accepted:
        if norm_name == MANIFEST:
            continue
        dest = _restore_destination(norm_name)
        if dest is None:
            continue
        orig_name = name_map.get(norm_name, norm_name)
        staged = os.path.join(staging, str(len(planned)))
        _stage_member(zf, orig_name, norm_name, staged, checksums)
        if dest == config.DB_FILE:
            _validate_staged_database(staged, accepted_set)
        planned.append((staged, dest))
    return planned


def _checkpoint_live_database(planned: list[tuple[str, str]]) -> None:
    has_database = any(dest == config.DB_FILE for _, dest in planned)
    if not has_database or not os.path.exists(config.DB_FILE):
        return
    with closing(sqlite3.connect(config.DB_FILE, timeout=10)) as conn:
        if conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]:
            raise ValueError("База занята: закройте другие экземпляры программы")


def _apply_staged_file(
    staged: str,
    dest: str,
    staging: str,
    rollback: list[tuple[str, str | None]],
) -> None:
    if os.path.isfile(dest) and filecmp.cmp(staged, dest, shallow=False):
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    existed = os.path.exists(dest)
    old = os.path.join(staging, f"old-{len(rollback)}")
    if existed:
        shutil.copy2(dest, old)
    with atomic_output(dest) as temporary:
        shutil.copyfile(staged, temporary)
    rollback.append((dest, old if existed else None))


def _rollback_restore(rollback: list[tuple[str, str | None]]) -> None:
    for dest, old in reversed(rollback):
        if old:
            with atomic_output(dest) as temporary:
                shutil.copyfile(old, temporary)
        elif os.path.exists(dest):
            os.unlink(dest)


def _apply_restore_plan(planned: list[tuple[str, str]], staging: str) -> int:
    _checkpoint_live_database(planned)
    rollback: list[tuple[str, str | None]] = []
    try:
        for staged, dest in planned:
            _apply_staged_file(staged, dest, staging, rollback)
    except Exception:
        _rollback_restore(rollback)
        raise
    return len(planned)


def restore_backup(filepath: str, password=None) -> tuple[int, list[str]]:
    if password is not None:
        from .encryption import decrypt

        with tempfile.TemporaryDirectory(prefix="get-decrypt-") as temporary:
            plain = os.path.join(temporary, "backup.zip")
            decrypt(filepath, plain, password)
            return restore_backup(plain)
    accepted, skipped = inspect_backup(filepath)
    with tempfile.TemporaryDirectory(prefix="get-restore-") as staging, zipfile.ZipFile(
        filepath, "r"
    ) as zf:
        planned = _stage_restore_plan(zf, accepted, staging)
        restored = _apply_restore_plan(planned, staging)
    return restored, skipped
