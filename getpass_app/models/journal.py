from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Mapping

from getpass_core.domain import parse_date
from getpass_core.storage import STATUS_REVOKED

JournalState = Literal["active", "expired", "revoked", "unknown"]

_STATE_LABELS = {
    "expired": "просрочен",
    "unknown": "нет срока",
}
_EXACT_EXTRA_FILTERS = frozenset({"zone", "park", "role"})
_DATE_SORT_KEYS = frozenset({"issue_date", "valid_until", "revoked_at"})


@dataclass(frozen=True)
class JournalField:
    key: str
    title: str
    tree_width: int
    anchor: str = "w"


@dataclass(frozen=True)
class JournalFilters:
    search: str = ""
    status: str = "active"
    date_from: str = ""
    date_to: str = ""
    extra: tuple[tuple[str, str], ...] = ()

    def extra_values(self) -> dict[str, str]:
        return dict(self.extra)


@dataclass(frozen=True)
class JournalRow:
    id: str
    values: Mapping[str, str]
    state: JournalState

    def display_value(self, key: str) -> str:
        if key == "status" and self.state in _STATE_LABELS:
            return _STATE_LABELS[self.state]
        return str(self.values.get(key, "") or "")


@dataclass(frozen=True)
class JournalSnapshot:
    journal_key: str
    journal_name: str
    fields: tuple[JournalField, ...]
    rows: tuple[JournalRow, ...]
    total_records: int
    filtered_records: int
    page: int
    page_size: int
    page_count: int

    @property
    def visible_fields(self) -> tuple[JournalField, ...]:
        return tuple(field for field in self.fields if field.tree_width > 0)


@dataclass(frozen=True)
class JournalHistoryChange:
    key: str
    title: str
    before: str
    after: str


@dataclass(frozen=True)
class JournalHistoryEvent:
    occurred_at: str
    actor: str
    action: str
    changes: tuple[JournalHistoryChange, ...]


def record_state(record: Mapping[str, object], today: date) -> JournalState:
    if record.get("status") == STATUS_REVOKED:
        return "revoked"
    valid_until = parse_date(str(record.get("valid_until", "") or ""))
    if valid_until is None:
        return "unknown"
    return "active" if valid_until.date() >= today else "expired"


def record_matches(
    record: Mapping[str, object],
    filters: JournalFilters,
    today: date,
) -> tuple[bool, JournalState]:
    state = record_state(record, today)
    query = filters.search.lower().strip()
    if query and not any(query in str(value).lower() for value in record.values()):
        return False, state
    if filters.status != "all" and state != filters.status:
        return False, state
    if not _matches_date_range(record, filters):
        return False, state
    if not _matches_extra(record, filters.extra_values()):
        return False, state
    return True, state


def sort_records(
    records: list[dict],
    key: str | None,
    reverse: bool,
) -> list[dict]:
    if not key:
        return list(records)
    return sorted(records, key=lambda record: _sort_value(record, key), reverse=reverse)


def _matches_date_range(record: Mapping[str, object], filters: JournalFilters) -> bool:
    date_from = parse_date(filters.date_from)
    date_to = parse_date(filters.date_to)
    issue = parse_date(str(record.get("issue_date", "") or ""))
    if date_from and (issue is None or issue.date() < date_from.date()):
        return False
    if date_to and (issue is None or issue.date() > date_to.date()):
        return False
    return True


def _matches_extra(record: Mapping[str, object], extras: Mapping[str, str]) -> bool:
    for key, raw_value in extras.items():
        value = (raw_value or "").strip()
        if not value:
            continue
        cell = str(record.get(key, "") or "")
        if key in _EXACT_EXTRA_FILTERS and cell != value:
            return False
        if key not in _EXACT_EXTRA_FILTERS and value.lower() not in cell.lower():
            return False
    return True


def _sort_value(record: Mapping[str, object], key: str):
    if key in _DATE_SORT_KEYS:
        return parse_date(str(record.get(key, "") or "")) or datetime.min
    return str(record.get(key, "") or "").lower()
