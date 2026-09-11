"""Validation shared by import preview and batch issuance."""
from pathlib import Path
from PIL import Image
from .domain import parse_date, normalize_plate
from . import blacklist


def photo_in_folder(folder, filename):
    if not filename:
        return ""
    root = Path(folder).resolve()
    candidate = Path(filename)
    if candidate.is_absolute():
        raise ValueError("Фото должно находиться в папке таблицы")
    path = (root / candidate).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Фото находится за пределами папки таблицы")
    return str(path) if path.is_file() else ""


def validate_photo(path):
    if not path or not Path(path).is_file():
        raise ValueError("Нет фотографии")
    if Path(path).stat().st_size > 20 * 1024**2:
        raise ValueError("Фото превышает 20 МБ")
    with Image.open(path) as image:
        if image.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValueError("Допустимы JPEG, PNG и WEBP")
        if image.width * image.height > 25_000_000:
            raise ValueError("Фото превышает 25 мегапикселей")
        image.verify()


def validate_items(items, journal, badge=False):
    results = []
    seen = set()
    for index, item in enumerate(items, 2):
        errors, warnings = [], []
        key = item.get("tab_num" if badge else "plate", "").strip()
        normalized = key.upper() if badge else normalize_plate(key)
        if not key:
            errors.append("Не указан номер")
        if normalized in seen:
            errors.append("Повтор в таблице")
        seen.add(normalized)
        if journal.find_duplicates(key):
            warnings.append("Есть действующий пропуск")
        if blacklist.find(plate="" if badge else key, fio=item.get("fio", item.get("d_fio", ""))):
            warnings.append("Чёрный список")
        issue, valid = parse_date(item.get("issue_date")), parse_date(item.get("valid_until"))
        if not issue or not valid:
            errors.append("Некорректная дата")
        elif valid < issue:
            errors.append("Срок заканчивается раньше выдачи")
        if badge:
            if not item.get("surname") or not item.get("name"):
                errors.append("Не заполнены фамилия и имя")
            try:
                validate_photo(item.get("photo_path"))
            except (OSError, ValueError, Image.DecompressionBombError) as exc:
                errors.append(str(exc))
        elif not item.get("num"):
            errors.append("Не указан номер пропуска")
        results.append((index, errors, warnings))
    return results
