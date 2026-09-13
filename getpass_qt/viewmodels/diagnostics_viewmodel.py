from __future__ import annotations

from PySide6.QtCore import QObject, QThreadPool, Signal

from getpass_qt.workers.task_worker import TaskWorker


class DiagnosticsViewModel(QObject):
    snapshot_changed = Signal(object)
    busy_changed = Signal(bool)
    operation_failed = Signal(str)

    def __init__(self, service, *, pool=None, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._pool = pool or QThreadPool.globalInstance()
        self._snapshot = None
        self._busy = False
        self._worker = None

    @property
    def snapshot(self):
        return self._snapshot

    @property
    def busy(self) -> bool:
        return self._busy

    def refresh(self) -> bool:
        if self._busy:
            return False

        def task(cancelled, _progress):
            if cancelled.is_set():
                raise RuntimeError("Операция отменена.")
            return self._service.snapshot()

        worker = TaskWorker(task)
        worker.signals.result.connect(self._on_snapshot)
        worker.signals.error.connect(self._on_worker_error)
        worker.signals.finished.connect(self._on_worker_finished)
        self._worker = worker
        self._set_busy(True)
        self._pool.start(worker)
        return True

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _on_snapshot(self, snapshot) -> None:
        self._snapshot = snapshot
        self.snapshot_changed.emit(snapshot)

    def _on_worker_error(self, exc) -> None:
        self.operation_failed.emit(str(exc))

    def _on_worker_finished(self) -> None:
        self._worker = None
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        if self._busy == busy:
            return
        self._busy = busy
        self.busy_changed.emit(busy)
