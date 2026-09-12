import threading

from getpass_qt.workers.task_worker import TaskWorker


def test_worker_emits_progress_result_and_finished(qtbot):
    progress = []
    results = []
    finished = []

    def task(cancelled, report_progress):
        assert isinstance(cancelled, threading.Event)
        report_progress(1, 2)
        report_progress(2, 2)
        return "done"

    worker = TaskWorker(task)
    worker.signals.progress.connect(lambda current, total: progress.append((current, total)))
    worker.signals.result.connect(results.append)
    worker.signals.finished.connect(lambda: finished.append(True))

    worker.run()

    assert progress == [(1, 2), (2, 2)]
    assert results == ["done"]
    assert finished == [True]


def test_worker_emits_exception_object_and_still_finishes(qtbot):
    errors = []
    finished = []

    def task(_cancelled, _progress):
        raise RuntimeError("boom")

    worker = TaskWorker(task)
    worker.signals.error.connect(errors.append)
    worker.signals.finished.connect(lambda: finished.append(True))

    worker.run()

    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)
    assert str(errors[0]) == "boom"
    assert finished == [True]


def test_worker_cancel_sets_shared_event():
    worker = TaskWorker(lambda cancelled, _progress: cancelled.is_set())

    worker.cancel()

    assert worker.cancelled.is_set()
