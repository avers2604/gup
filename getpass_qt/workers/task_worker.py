from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class TaskWorkerSignals(QObject):
    result = Signal(object)
    error = Signal(object)
    progress = Signal(int, int)
    finished = Signal()


class TaskWorker(QRunnable):
    def __init__(self, task) -> None:
        super().__init__()
        self._task = task
        self.cancelled = threading.Event()
        self.signals = TaskWorkerSignals()

    def cancel(self) -> None:
        self.cancelled.set()

    @Slot()
    def run(self) -> None:
        try:
            result = self._task(self.cancelled, self.signals.progress.emit)
        except Exception as exc:
            self.signals.error.emit(exc)
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()
