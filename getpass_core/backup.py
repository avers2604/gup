"""Резервное копирование и восстановление данных."""
from __future__ import annotations

import os
import zipfile
from datetime import datetime

from . import config

#: Что кладём в архив: (путь, имя в архиве)
def _backup_items() -> list[tuple[str, str]]:
    items = []
    for path in (config.CONFIG_FILE, config.LOG_CSV_FILE, config.LOG_XLSX_FILE,
                 config.BADGE_LOG_CSV, config.BADGE_LOG_XLSX, config.CARS_CACHE_FILE):
        if os.path.exists(path):
            items.append((path, "data/" + os.path.basename(path)))
    # шаблон бланка и шрифты — без них восстановленная копия неработоспособна
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


MANIFEST = "manifest.txt"


def create_backup(filepath: str) -> tuple[int, int]:
    """Создать архив. Возвращает (файлов, байт)."""
    items = _backup_items()
    total = 0
    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arc in items:
            zf.write(src, arc)
            total += os.path.getsize(src)
        zf.writestr(MANIFEST, _manifest_text(items))
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


#: Куда разрешено распаковывать. Всё остальное игнорируется.
_ALLOWED_PREFIXES = ("data/", "photos/", "fonts/")
_ALLOWED_FILES = ("template.png", "app_icon.ico", MANIFEST)


def inspect_backup(filepath: str) -> tuple[list[str], list[str]]:
    """Что будет восстановлено и что пропущено."""
    accepted, skipped = [], []
    with zipfile.ZipFile(filepath, "r") as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            norm = name.replace("\\", "/")
            if (norm in _ALLOWED_FILES or norm.startswith(_ALLOWED_PREFIXES)) \
                    and ".." not in norm and not norm.startswith("/"):
                accepted.append(norm)
            else:
                skipped.append(norm)
    return accepted, skipped


def restore_backup(filepath: str) -> tuple[int, list[str]]:
    """Восстановить только известные файлы.

    Раньше распаковывался любой архив целиком в каталог программы, что
    позволяло подложить рядом с exe произвольные файлы.
    """
    accepted, skipped = inspect_backup(filepath)
    targets = {
        "template.png": config.TEMPLATE_FILE,
        "app_icon.ico": config.ICON_FILE,
    }
    restored = 0
    with zipfile.ZipFile(filepath, "r") as zf:
        for name in accepted:
            if name == MANIFEST:
                continue
            if name in targets:
                dest = targets[name]
            elif name.startswith("data/"):
                dest = os.path.join(config.DATA_DIR, os.path.basename(name))
            elif name.startswith("photos/"):
                dest = os.path.join(config.PHOTO_DIR, os.path.basename(name))
            elif name.startswith("fonts/"):
                dest = os.path.join(config.FONTS_DIR, os.path.basename(name))
            else:
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(name) as src, open(dest, "wb") as out:
                out.write(src.read())
            restored += 1
    return restored, skipped
