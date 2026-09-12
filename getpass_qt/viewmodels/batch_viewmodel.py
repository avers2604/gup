from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThreadPool, Signal

from getpass_app.services.batch_service import BatchCancelled
from getpass_qt.workers.task_worker import TaskWorker


class BatchViewModel(QObject):
    kind_changed = Signal(str)
    review_changed = Signal(object)
    busy_changed = Signal(bool)
    progress_changed = Signal(int, int)
    output_succeeded = Signal(object)
    operation_failed = Signal(str)

    def __init__(self, service, *, pool=None, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._pool = pool or QThreadPool.globalInstance()
        self._kind = "pass"
        self._source_path = ""
        self._items = ()
        self._review = None
        self._busy = False
        self._worker = None
        self._pass_defaults = {
            "issue_date": "",
            "valid_until": "",
            "otb_post": "",
            "otb_name": "",
            "is_temporary": False,
        }
        self._badge_defaults = {
            "park": "",
            "issue_date": "",
            "valid_until": "",
        }

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def source_path(self) -> str:
        return self._source_path

    @property
    def items(self):
        return self._items

    @property
    def review(self):
        return self._review

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def can_generate(self) -> bool:
        return self._review is not None and self._review.can_generate and not self._busy

    def set_kind(self, kind: str) -> None:
        if kind not in {"pass", "badge"}:
            raise ValueError(f"Unknown batch kind: {kind}")
        if kind == self._kind:
            return
        self._kind = kind
        self._clear_import()
        self.kind_changed.emit(kind)

    def set_pass_defaults(self, **values) -> None:
        self._pass_defaults.update(values)

    def set_badge_defaults(self, **values) -> None:
        self._badge_defaults.update(values)

    def load_csv(self, path: str) -> bool:
        try:
            rows = self._service.read_csv(path)
            items = self._parse_rows(rows, path)
            review = self._service.review(self._kind, items)
        except Exception as exc:
            self.operation_failed.emit(str(exc))
            return False
        self._source_path = path
        self._items = tuple(items)
        self._review = review
        self.review_changed.emit(review)
        return True

    def export_template(self, path: str) -> bool:
        try:
            self._service.export_template(self._kind, path)
        except Exception as exc:
            self.operation_failed.emit(str(exc))
            return False
        return True

    def generate_pdf(self, path: str) -> bool:
        if not self.can_generate:
            self.operation_failed.emit(
                "Исправьте ошибки импорта перед формированием PDF."
            )
            return False

        kind = self._kind
        items = self._items

        def task(cancelled, progress):
            return self._service.generate_pdf(
                kind,
                items,
                path,
                cancelled=cancelled,
                progress=progress,
            )

        worker = TaskWorker(task)
        worker.signals.progress.connect(self.progress_changed.emit)
        worker.signals.result.connect(self.output_succeeded.emit)
        worker.signals.error.connect(self._on_worker_error)
        worker.signals.finished.connect(self._on_worker_finished)
        self._worker = worker
        self._set_busy(True)
        self._pool.start(worker)
        return True

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _parse_rows(self, rows, path: str):
        if self._kind == "pass":
            return self._service.parse_pass_rows(rows, self._pass_defaults)
        return self._service.parse_badge_rows(
            rows,
            str(Path(path).parent),
            self._badge_defaults,
        )

    def _clear_import(self) -> None:
        self._source_path = ""
        self._items = ()
        self._review = None
        self.review_changed.emit(None)

    def _set_busy(self, busy: bool) -> None:
        if busy == self._busy:
            return
        self._busy = busy
        self.busy_changed.emit(busy)

    def _on_worker_error(self, exc) -> None:
        if isinstance(exc, BatchCancelled):
            self.operation_failed.emit("Массовая печать отменена.")
            return
        self.operation_failed.emit(str(exc))

    def _on_worker_finished(self) -> None:
        self._worker = None
        self._set_busy(False)
