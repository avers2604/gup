from __future__ import annotations

import os
from collections.abc import Iterable

from getpass_app.models.operation import PendingOperation
from getpass_core import issuance
from getpass_core.storage import BADGE_JOURNAL, PASS_JOURNAL

_SUPPORTED_DOCUMENT_EXTENSIONS = (".pdf", ".jpg", ".png")


class OperationsService:
    def __init__(
        self,
        *,
        pass_journal=PASS_JOURNAL,
        badge_journal=BADGE_JOURNAL,
        pending=issuance.pending,
        confirm=issuance.confirm,
        cancel=issuance.cancel,
        file_exists=os.path.isfile,
    ) -> None:
        self._journals = {
            "pass": pass_journal,
            "badge": badge_journal,
        }
        self._pending = pending
        self._confirm = confirm
        self._cancel = cancel
        self._file_exists = file_exists

    def pending(self) -> tuple[PendingOperation, ...]:
        operations = [
            self._project(journal_key, journal, job)
            for journal_key, journal, job in self._pending_pairs()
        ]
        return tuple(sorted(operations, key=lambda item: item.created_at))

    def confirm(self, ids: Iterable[str]) -> None:
        self._apply(ids, self._confirm)

    def cancel(self, ids: Iterable[str]) -> None:
        self._apply(ids, self._cancel)

    def _apply(self, ids: Iterable[str], action) -> None:
        index = {
            job["id"]: journal
            for _, journal, job in self._pending_pairs()
        }
        requested = tuple(ids)
        missing = next((operation_id for operation_id in requested if operation_id not in index), None)
        if missing is not None:
            raise ValueError("Операция не найдена")
        for operation_id in requested:
            action(index[operation_id], operation_id)

    def _pending_pairs(self):
        for journal_key, journal in self._journals.items():
            for job in self._pending(journal):
                yield journal_key, journal, job

    def _project(self, journal_key, journal, job) -> PendingOperation:
        destination = str(job.get("destination", "") or "")
        document_path, status = self._document_state(destination)
        return PendingOperation(
            id=job["id"],
            journal_key=journal_key,
            journal_name=journal.schema.name,
            created_at=job.get("created_at", ""),
            destination=destination,
            document_status=status,
            document_path=document_path,
        )

    def _document_state(self, destination: str) -> tuple[str, str]:
        if not self._is_document_path(destination):
            return "", "Прямая печать"
        if self._file_exists(destination):
            return destination, "Файл готов"
        return destination, "Файл не найден"

    @staticmethod
    def _is_document_path(path: str) -> bool:
        return bool(path) and path.lower().endswith(_SUPPORTED_DOCUMENT_EXTENSIONS)
