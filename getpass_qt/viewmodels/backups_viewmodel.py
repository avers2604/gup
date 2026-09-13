from __future__ import annotations

from PySide6.QtCore import QObject, QThreadPool, Signal

from getpass_qt.workers.task_worker import TaskWorker


class BackupsViewModel(QObject):
    inspection_ready = Signal(object)
    backup_created = Signal(object)
    backup_restored = Signal(object)
    busy_changed = Signal(bool)
    operation_failed = Signal(str)

    def __init__(self, service, *, pool=None, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._pool = pool or QThreadPool.globalInstance()
        self._busy = False
        self._worker = None
        self._inspection = None
        self._inspection_key = None

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def inspection(self):
        return self._inspection

    def create(self, path: str, password: str | None) -> bool:
        self._invalidate_if_changed(path, password)
        return self._dispatch(
            lambda: self._service.create(path, password),
            self.backup_created.emit,
        )

    def inspect(self, path: str, password: str | None) -> bool:
        if self._busy:
            return False
        self._invalidate_inspection()
        key = (path, password)

        def accept(result):
            self._inspection = result
            self._inspection_key = key
            self.inspection_ready.emit(result)

        return self._dispatch(
            lambda: self._service.inspect(path, password),
            accept,
        )

    def restore(self, path: str, password: str | None) -> bool:
        key = (path, password)
        if self._inspection_key != key or self._inspection is None:
            self._invalidate_inspection()
            self.operation_failed.emit(
                "Сначала проверьте выбранную резервную копию."
            )
            return False
        if not self._inspection.can_restore:
            self.operation_failed.emit(
                "В резервной копии нет данных для восстановления."
            )
            return False

        def accept(result):
            self._invalidate_inspection()
            self.backup_restored.emit(result)

        return self._dispatch(
            lambda: self._service.restore(path, password),
            accept,
        )

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _dispatch(self, operation, accept) -> bool:
        if self._busy:
            return False

        def task(cancelled, _progress):
            if cancelled.is_set():
                raise RuntimeError("Операция отменена.")
            return operation()

        worker = TaskWorker(task)
        worker.signals.result.connect(accept)
        worker.signals.error.connect(self._on_worker_error)
        worker.signals.finished.connect(self._on_worker_finished)
        self._worker = worker
        self._set_busy(True)
        self._pool.start(worker)
        return True

    def _invalidate_if_changed(self, path: str, password: str | None) -> None:
        if self._inspection_key is not None and self._inspection_key != (path, password):
            self._invalidate_inspection()

    def _invalidate_inspection(self) -> None:
        self._inspection = None
        self._inspection_key = None

    def _on_worker_error(self, exc) -> None:
        self._invalidate_inspection()
        self.operation_failed.emit(str(exc))

    def _on_worker_finished(self) -> None:
        self._worker = None
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        if self._busy == busy:
            return
        self._busy = busy
        self.busy_changed.emit(busy)
