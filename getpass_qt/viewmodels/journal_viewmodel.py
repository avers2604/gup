from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, Signal

from getpass_app.models.journal import JournalFilters

_ALLOWED_STATUSES = frozenset({"all", "active", "expired", "revoked", "unknown"})


class JournalViewModel(QObject):
    snapshot_changed = Signal(object)
    busy_changed = Signal(bool)
    operation_succeeded = Signal(str)
    operation_failed = Signal(str)

    def __init__(self, service, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._journal_key = "pass"
        self._filters = JournalFilters()
        self._sort_key: str | None = None
        self._sort_reverse = False
        self._page = 0
        self._page_size = 100
        self._snapshot = self._load_snapshot()

    @property
    def journal_key(self) -> str:
        return self._journal_key

    @property
    def filters(self) -> JournalFilters:
        return self._filters

    @property
    def sort_key(self) -> str | None:
        return self._sort_key

    @property
    def sort_reverse(self) -> bool:
        return self._sort_reverse

    @property
    def snapshot(self):
        return self._snapshot

    def journal_keys(self) -> tuple[str, ...]:
        return tuple(self._service.journal_keys())

    def select_journal(self, journal_key: str) -> bool:
        if journal_key not in self.journal_keys():
            raise ValueError(f"Unknown journal: {journal_key}")
        self._journal_key = journal_key
        self._filters = JournalFilters()
        self._sort_key = None
        self._sort_reverse = False
        self._page = 0
        return self.refresh()

    def set_search(self, value: str) -> bool:
        self._filters = replace(self._filters, search=value)
        self._page = 0
        return self.refresh()

    def set_status(self, status: str) -> bool:
        if status not in _ALLOWED_STATUSES:
            raise ValueError(f"Unknown journal status: {status}")
        self._filters = replace(self._filters, status=status)
        self._page = 0
        return self.refresh()

    def set_date_range(self, date_from: str, date_to: str) -> bool:
        self._filters = replace(
            self._filters,
            date_from=date_from,
            date_to=date_to,
        )
        self._page = 0
        return self.refresh()

    def set_extra_filter(self, key: str, value: str) -> bool:
        extras = self._filters.extra_values()
        clean_value = value.strip()
        if clean_value:
            extras[key] = clean_value
        else:
            extras.pop(key, None)
        self._filters = replace(
            self._filters,
            extra=tuple(sorted(extras.items())),
        )
        self._page = 0
        return self.refresh()

    def sort_by(self, key: str) -> bool:
        if self._sort_key == key:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_key = key
            self._sort_reverse = False
        self._page = 0
        return self.refresh()

    def set_page(self, page: int) -> bool:
        self._page = max(0, int(page))
        return self.refresh()

    def distinct(self, key: str) -> tuple[str, ...]:
        return tuple(self._service.distinct(self._journal_key, key))

    def refresh(self) -> bool:
        self.busy_changed.emit(True)
        try:
            snapshot = self._load_snapshot()
        except Exception as exc:
            self.operation_failed.emit(str(exc))
            return False
        finally:
            self.busy_changed.emit(False)
        self._snapshot = snapshot
        self._page = snapshot.page
        self.snapshot_changed.emit(snapshot)
        return True

    def update_record(self, record_id: str, values: dict[str, str]) -> bool:
        row = self._find_row(record_id)
        if row is None:
            self.operation_failed.emit("Запись не найдена.")
            return False
        try:
            self._service.update_record(
                self._journal_key,
                record_id,
                values,
                dict(row.values),
            )
        except Exception as exc:
            self.operation_failed.emit(str(exc))
            return False
        if not self.refresh():
            return False
        self.operation_succeeded.emit("Запись обновлена.")
        return True

    def revoke(self, record_ids, reason: str) -> bool:
        ids = tuple(record_ids)
        if not ids:
            return False
        try:
            self._service.revoke(self._journal_key, ids, reason)
        except Exception as exc:
            self.operation_failed.emit(str(exc))
            return False
        if not self.refresh():
            return False
        self.operation_succeeded.emit("Записи аннулированы.")
        return True

    def history(self, record_id: str):
        try:
            return self._service.history(self._journal_key, record_id)
        except Exception as exc:
            self.operation_failed.emit(str(exc))
            return ()

    def export(self, path: str) -> bool:
        try:
            count = self._service.export(
                self._journal_key,
                self._snapshot.rows,
                path,
            )
        except Exception as exc:
            self.operation_failed.emit(str(exc))
            return False
        self.operation_succeeded.emit(f"Экспорт завершён. Записей: {count}.")
        return True

    def add_revoked_to_blacklist(self, record_ids, reason: str) -> bool:
        try:
            self._service.add_revoked_to_blacklist(
                self._journal_key,
                tuple(record_ids),
                reason,
            )
        except Exception as exc:
            self.operation_failed.emit(str(exc))
            return False
        return True

    def _load_snapshot(self):
        return self._service.snapshot(
            self._journal_key,
            self._filters,
            sort_key=self._sort_key,
            sort_reverse=self._sort_reverse,
            page=self._page,
            page_size=self._page_size,
        )

    def _find_row(self, record_id: str):
        return next(
            (row for row in self._snapshot.rows if row.id == record_id),
            None,
        )
