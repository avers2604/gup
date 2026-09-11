"""Validation shared by import preview and batch issuance."""
from pathlib import Path

from PIL import Image

from . import blacklist
from .domain import normalize_plate, parse_date


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


def _item_key(item, badge: bool) -> tuple[str, str]:
    key = item.get("tab_num" if badge else "plate", "").strip()
    normalized = key.upper() if badge else normalize_plate(key)
    return key, normalized


def _date_errors(item) -> list[str]:
    issue = parse_date(item.get("issue_date"))
    valid = parse_date(item.get("valid_until"))
    if not issue or not valid:
        return ["Некорректная дата"]
    if valid < issue:
        return ["Срок заканчивается раньше выдачи"]
    return []


def _badge_errors(item) -> list[str]:
    errors = []
    if not item.get("surname") or not item.get("name"):
        errors.append("Не заполнены фамилия и имя")
    try:
        validate_photo(item.get("photo_path"))
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        errors.append(str(exc))
    return errors


def _pass_errors(item) -> list[str]:
    return [] if item.get("num") else ["Не указан номер пропуска"]


def _item_warnings(item, journal, badge: bool, key: str) -> list[str]:
    warnings = []
    if journal.find_duplicates(key):
        warnings.append("Есть действующий пропуск")
    fio = item.get("fio", item.get("d_fio", ""))
    if blacklist.find(plate="" if badge else key, fio=fio):
        warnings.append("Чёрный список")
    return warnings


def _validate_item(item, journal, badge: bool, seen: set[str]) -> tuple[list[str], list[str]]:
    errors = []
    key, normalized = _item_key(item, badge)
    if not key:
        errors.append("Не указан номер")
    if normalized in seen:
        errors.append("Повтор в таблице")
    seen.add(normalized)

    warnings = _item_warnings(item, journal, badge, key)
    errors.extend(_date_errors(item))
    errors.extend(_badge_errors(item) if badge else _pass_errors(item))
    return errors, warnings


def validate_items(items, journal, badge=False):
    results = []
    seen = set()
    for index, item in enumerate(items, 2):
        errors, warnings = _validate_item(item, journal, badge, seen)
        results.append((index, errors, warnings))
    return results
