from __future__ import annotations

from getpass_app.models.blacklist import BlacklistEntry
from getpass_core import blacklist


class BlacklistService:
    def __init__(
        self,
        *,
        load=blacklist.load,
        add=blacklist.add,
        remove=blacklist.remove,
    ) -> None:
        self._load = load
        self._add = add
        self._remove = remove

    def list_entries(self) -> tuple[BlacklistEntry, ...]:
        return tuple(BlacklistEntry.from_mapping(value) for value in self._load())

    def add_entry(self, *, plate: str, fio: str, incident: str) -> BlacklistEntry:
        clean_incident = incident.strip()
        if not plate.strip() and not fio.strip():
            raise ValueError("Укажите госномер или ФИО.")
        if not clean_incident:
            raise ValueError("Опишите инцидент.")
        value = self._add(
            plate=plate,
            fio=fio,
            incident=clean_incident,
        )
        return BlacklistEntry.from_mapping(value)

    def remove_entry(self, entry_id: str) -> None:
        if not entry_id:
            raise ValueError("Не выбрана запись черного списка.")
        self._remove(entry_id)
