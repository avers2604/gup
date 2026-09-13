from __future__ import annotations

import json
from datetime import date
from math import ceil
from typing import Iterable, Mapping

from getpass_app.models.journal import (
    JournalField,
    JournalFilters,
    JournalHistoryChange,
    JournalHistoryEvent,
    JournalRow,
    JournalSnapshot,
    record_matches,
    sort_records,
)
from getpass_core import blacklist
from getpass_core.storage import (
    BADGE_JOURNAL,
    PASS_JOURNAL,
    export_records_to_xlsx,
)


class JournalService:
    def __init__(
        self,
        *,
        pass_journal=PASS_JOURNAL,
        badge_journal=BADGE_JOURNAL,
        today=date.today,
        export_xlsx=export_records_to_xlsx,
        blacklist_add=blacklist.add,
    ) -> None:
        self._journals = {
            "pass": pass_journal,
            "badge": badge_journal,
        }
        self._today = today
        self._export_xlsx = export_xlsx
        self._blacklist_add = blacklist_add

    def journal_keys(self) -> tuple[str, ...]:
        return tuple(self._journals)

    def snapshot(
        self,
        journal_key: str,
        filters: JournalFilters,
        *,
        sort_key: str | None = None,
        sort_reverse: bool = False,
        page: int = 0,
        page_size: int = 100,
    ) -> JournalSnapshot:
        if page_size < 1:
            raise ValueError("page_size must be positive")
        journal = self._journal(journal_key)
        records = sort_records(journal.read(), sort_key, sort_reverse)
        rows = self._filtered_rows(records, filters)
        page_count = max(1, ceil(len(rows) / page_size))
        safe_page = max(0, min(int(page), page_count - 1))
        start = safe_page * page_size
        stop = start + page_size
        return JournalSnapshot(
            journal_key=journal_key,
            journal_name=journal.schema.name,
            fields=self._fields(journal),
            rows=tuple(rows[start:stop]),
            total_records=len(records),
            filtered_records=len(rows),
            page=safe_page,
            page_size=page_size,
            page_count=page_count,
        )

    def distinct(self, journal_key: str, key: str) -> tuple[str, ...]:
        return tuple(self._journal(journal_key).distinct(key))

    def update_record(
        self,
        journal_key: str,
        record_id: str,
        values: Mapping[str, str],
        expected: Mapping[str, object],
    ) -> None:
        self._journal(journal_key).update_record(
            record_id,
            dict(values),
            dict(expected),
        )

    def revoke(self, journal_key: str, ids: Iterable[str], reason: str) -> None:
        self._journal(journal_key).revoke_ids(tuple(ids), reason)

    def history(self, journal_key: str, record_id: str) -> tuple[JournalHistoryEvent, ...]:
        journal = self._journal(journal_key)
        conn = journal._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM journal_events WHERE journal=? AND record_id=? "
                "ORDER BY event_id",
                (journal.schema.table, record_id),
            ).fetchall()
        finally:
            conn.close()
        titles = {field.key: field.title for field in journal.schema.fields}
        return tuple(self._history_event(row, titles) for row in rows)

    def export(self, journal_key: str, rows: Iterable[JournalRow], path: str) -> int:
        journal = self._journal(journal_key)
        records = list(rows)
        values = [
            [record.values.get(key, "") for key in journal.schema.keys]
            for record in records
        ]
        self._export_xlsx(values, journal.schema.cols_def, path, journal.schema.name)
        return len(records)

    def add_revoked_to_blacklist(
        self,
        journal_key: str,
        ids: Iterable[str],
        reason: str,
    ) -> int:
        journal = self._journal(journal_key)
        wanted = set(ids)
        records = [record for record in journal.read() if record.get("id") in wanted]
        for record in records:
            plate = record.get("plate", "")
            fio = record.get("driver") or record.get("fio") or ""
            self._blacklist_add(plate, fio, reason)
        return len(records)

    def _journal(self, journal_key: str):
        try:
            return self._journals[journal_key]
        except KeyError as exc:
            raise ValueError(f"Unknown journal: {journal_key}") from exc

    def _filtered_rows(
        self,
        records: list[dict],
        filters: JournalFilters,
    ) -> list[JournalRow]:
        today = self._today()
        out = []
        for record in records:
            matches, state = record_matches(record, filters, today)
            if matches:
                out.append(
                    JournalRow(
                        id=str(record.get("id", "")),
                        values=dict(record),
                        state=state,
                    )
                )
        return out

    @staticmethod
    def _fields(journal) -> tuple[JournalField, ...]:
        return tuple(
            JournalField(
                key=field.key,
                title=field.title,
                tree_width=field.tree_width,
                anchor=field.anchor,
            )
            for field in journal.schema.fields
        )

    @staticmethod
    def _history_event(row, titles: Mapping[str, str]) -> JournalHistoryEvent:
        before = json.loads(row["before_json"])
        after = json.loads(row["after_json"])
        changes = tuple(
            JournalHistoryChange(
                key=key,
                title=titles.get(key, key),
                before=str(before.get(key, "") or ""),
                after=str(after.get(key, "") or ""),
            )
            for key in titles
            if before.get(key) != after.get(key)
        )
        return JournalHistoryEvent(
            occurred_at=row["occurred_at"],
            actor=row["actor"],
            action=row["action"],
            changes=changes,
        )
