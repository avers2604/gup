"""Резервное копирование и восстановление данных."""
from __future__ import annotations

import os
import hashlib
import json
import filecmp
from contextlib import closing
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta

from . import config
from .atomic import atomic_output

MANIFEST = "manifest.txt"
_ALLOWED_PREFIXES = ("data/", "photos/", "fonts/")
_ALLOWED_FILES = ("template.png", "app_icon.ico", MANIFEST)


def _backup_items() -> list[tuple[str, str]]:
    items = []
    for path in (config.CONFIG_FILE, config.LOG_CSV_FILE,
                 config.LOG_XLSX_FILE, config.BADGE_LOG_CSV, config.BADGE_LOG_XLSX,
                 config.CARS_CACHE_FILE, config.BLACKLIST_FILE):
        if os.path.exists(path):
            items.append((path, "data/" + os.path.basename(path)))

    if os.path.exists(config.TEMPLATE_FILE):
        items.append((config.TEMPLATE_FILE, "template.png"))
    if os.path.exists(config.ICON_FILE):
        items.append((config.ICON_FILE, "app_icon.ico"))

    if os.path.isdir(config.FONTS_DIR):
        for name in sorted(os.listdir(config.FONTS_DIR)):
            full = os.path.join(config.FONTS_DIR, name)
            if os.path.isfile(full):
                items.append((full, f"fonts/{name}"))

    if os.path.isdir(config.PHOTO_DIR):
        for name in sorted(os.listdir(config.PHOTO_DIR)):
            full = os.path.join(config.PHOTO_DIR, name)
            if os.path.isfile(full):
                items.append((full, f"photos/{name}"))
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
        with atomic_output(filepath) as temporary, zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as zf:
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
            if (norm in _ALLOWED_FILES or norm.startswith(_ALLOWED_PREFIXES)) \
                    and ".." not in norm and not norm.startswith("/") and ":" not in norm \
                    and len(norm.split("/")) <= 2:
                accepted.append(norm)
            else:
                skipped.append(name)
    return accepted, skipped


def restore_backup(filepath: str, password=None) -> tuple[int, list[str]]:
    if password is not None:
        from .encryption import decrypt
        with tempfile.TemporaryDirectory(prefix="get-decrypt-") as temporary:
            plain = os.path.join(temporary, "backup.zip")
            decrypt(filepath, plain, password)
            return restore_backup(plain)
    accepted, skipped = inspect_backup(filepath)
    targets = {
        "template.png": config.TEMPLATE_FILE,
        "app_icon.ico": config.ICON_FILE,
    }
    restored = 0
    with tempfile.TemporaryDirectory(prefix="get-restore-") as staging, zipfile.ZipFile(filepath, "r") as zf:
        checksums = json.loads(zf.read("checksums.json")) if "checksums.json" in zf.namelist() else None
        planned = []
        # Карта нормализованных имен к фактическим именам в архиве
        name_map = {n.replace("\\", "/"): n for n in zf.namelist()}
        for norm_name in accepted:
            if norm_name == MANIFEST:
                continue
            if norm_name in targets:
                dest = targets[norm_name]
            elif norm_name.startswith("data/"):
                dest = os.path.join(config.DATA_DIR, os.path.basename(norm_name))
            elif norm_name.startswith("photos/"):
                dest = os.path.join(config.PHOTO_DIR, os.path.basename(norm_name))
            elif norm_name.startswith("fonts/"):
                dest = os.path.join(config.FONTS_DIR, os.path.basename(norm_name))
            else:
                continue

            orig_name = name_map.get(norm_name, norm_name)
            staged = os.path.join(staging, str(len(planned)))
            with zf.open(orig_name) as src, open(staged, "wb") as out:
                shutil.copyfileobj(src, out)
            if checksums is not None:
                with open(staged, "rb") as stream:
                    if checksums.get(orig_name) != hashlib.file_digest(stream, "sha256").hexdigest():
                        raise ValueError(f"Контрольная сумма не совпала: {norm_name}")
            if dest == config.DB_FILE:
                with closing(sqlite3.connect(staged)) as conn:
                    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError("Повреждённая база в архиве")
                    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='badge_journal'").fetchone():
                        columns = {r[1] for r in conn.execute("PRAGMA table_info(badge_journal)")}
                        if "photo_path" in columns:
                            for record_id, photo in conn.execute("SELECT id, photo_path FROM badge_journal").fetchall():
                                if photo:
                                    name = photo.replace("\\", "/").rsplit("/", 1)[-1]
                                    if "photos/" + name in accepted:
                                        conn.execute("UPDATE badge_journal SET photo_path=? WHERE id=?",
                                                     (os.path.join(config.PHOTO_DIR, name), record_id))
                            conn.commit()
            planned.append((staged, dest))
        rollback = []
        try:
            if any(dest == config.DB_FILE for _, dest in planned) and os.path.exists(config.DB_FILE):
                with closing(sqlite3.connect(config.DB_FILE, timeout=10)) as conn:
                    if conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]:
                        raise ValueError("База занята: закройте другие экземпляры программы")
            for staged, dest in planned:
                if os.path.isfile(dest) and filecmp.cmp(staged, dest, shallow=False):
                    restored += 1
                    continue
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                old = os.path.join(staging, f"old-{len(rollback)}")
                existed = os.path.exists(dest)
                if existed:
                    shutil.copy2(dest, old)
                with atomic_output(dest) as temporary:
                    shutil.copyfile(staged, temporary)
                rollback.append((dest, old if existed else None))
                restored += 1
        except Exception:
            for dest, old in reversed(rollback):
                if old:
                    with atomic_output(dest) as temporary:
                        shutil.copyfile(old, temporary)
                elif os.path.exists(dest):
                    os.unlink(dest)
            raise
    return restored, skipped
