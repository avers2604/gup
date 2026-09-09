"""Реестр нарушителей, сохраняемый отдельно от журналов выдачи."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime

from . import config
from .domain import normalize_plate


def _name_key(value: str | None) -> str:
    return " ".join((value or "").upper().split())


def load() -> list[dict]:
    try:
        with open(config.BLACKLIST_FILE, "r", encoding="utf-8") as stream:
            value = json.load(stream)
        return value if isinstance(value, list) else []
    except (OSError, ValueError):
        return []


def save(entries: list[dict]) -> None:
    os.makedirs(os.path.dirname(config.BLACKLIST_FILE) or ".", exist_ok=True)
    temporary = config.BLACKLIST_FILE + ".tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(entries, stream, ensure_ascii=False, indent=2)
    os.replace(temporary, config.BLACKLIST_FILE)


def add(plate: str = "", fio: str = "", incident: str = "") -> dict:
    entry = {
        "id": uuid.uuid4().hex[:12],
        "plate": normalize_plate(plate),
        "fio": " ".join((fio or "").upper().split()),
        "incident": (incident or "").strip(),
        "created_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
    }
    entries = load()
    entries.append(entry)
    save(entries)
    return entry


def remove(entry_id: str) -> None:
    save([entry for entry in load() if entry.get("id") != entry_id])


def find(plate: str = "", fio: str = "") -> list[dict]:
    plate_key = normalize_plate(plate)
    fio_key = _name_key(fio)
    if not plate_key and not fio_key:
        return []
    matches = []
    for entry in load():
        if plate_key and plate_key == normalize_plate(entry.get("plate")):
            matches.append(entry)
        elif fio_key and fio_key == _name_key(entry.get("fio")):
            matches.append(entry)
    return matches