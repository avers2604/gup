"""Резервное копирование и восстановление данных."""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime

from . import config

MANIFEST = "manifest.txt"
_ALLOWED_PREFIXES = ("data/", "photos/", "fonts/")
_ALLOWED_FILES = ("template.png", "app_icon.ico", MANIFEST)


def _backup_items() -> list[tuple[str, str]]:
    items = []
    for path in (config.CONFIG_FILE, config.LOG_CSV_FILE,
                 config.LOG_XLSX_FILE, config.BADGE_LOG_CSV, config.BADGE_LOG_XLSX,
                 config.CARS_CACHE_FILE):
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


def create_backup(filepath: str) -> tuple[int, int]:
    """Создать архив. Возвращает (файлов, байт)."""
    items = _backup_items()
    total = 0
    temp_db_snapshot = None

    if os.path.exists(config.DB_FILE):
        fd, temp_db_snapshot = tempfile.mkstemp(prefix="gup_db_bkp_", suffix=".sqlite3")
        os.close(fd)
        try:
            src_conn = sqlite3.connect(config.DB_FILE)
            dst_conn = sqlite3.connect(temp_db_snapshot)
            with dst_conn:
                src_conn.backup(dst_conn)
            src_conn.close()
            dst_conn.close()
            items.append((temp_db_snapshot, "data/" + os.path.basename(config.DB_FILE)))
        except Exception:
            if os.path.exists(temp_db_snapshot):
                os.remove(temp_db_snapshot)
            temp_db_snapshot = None

    try:
        with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
            for src, arc in items:
                zf.write(src, arc)
                total += os.path.getsize(src)
            zf.writestr(MANIFEST, _manifest_text(items))
    finally:
        if temp_db_snapshot and os.path.exists(temp_db_snapshot):
            try:
                os.remove(temp_db_snapshot)
            except Exception:
                pass

    return len(items), total


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


def inspect_backup(filepath: str) -> tuple[list[str], list[str]]:
    """Что будет восстановлено и что пропущено. Возвращает списки строк."""
    accepted: list[str] = []
    skipped: list[str] = []
    with zipfile.ZipFile(filepath, "r") as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            norm = name.replace("\\", "/")
            if (norm in _ALLOWED_FILES or norm.startswith(_ALLOWED_PREFIXES)) \
                    and ".." not in norm and not norm.startswith("/"):
                accepted.append(norm)
            else:
                skipped.append(name)
    return accepted, skipped


def restore_backup(filepath: str) -> tuple[int, list[str]]:
    accepted, skipped = inspect_backup(filepath)
    targets = {
        "template.png": config.TEMPLATE_FILE,
        "app_icon.ico": config.ICON_FILE,
    }
    restored = 0
    with zipfile.ZipFile(filepath, "r") as zf:
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
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(orig_name) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
            restored += 1
    return restored, skipped