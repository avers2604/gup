from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading
import time

import pytest

from getpass_core import issuance


def test_cancelled_issuance_is_not_pending_and_cannot_be_confirmed(journal):
    operation_id = issuance.prepare(
        journal, [{"num": "1", "plate": "A111AA78"}], "printer"
    )

    issuance.cancel(journal, operation_id)

    assert issuance.pending(journal) == []
    with pytest.raises(ValueError, match="отмен"):
        issuance.confirm(journal, operation_id)
    assert journal.read() == []


def test_delete_ids_preserves_record_added_during_delete(journal, monkeypatch):
    journal.append_many([
        {"num": "1", "plate": "A111AA78"},
        {"num": "2", "plate": "B222BB78"},
    ])
    victim = journal.read()[0]["id"]
    original_write = journal.write
    replacement_started = threading.Event()
    allow_replacement = threading.Event()

    def delayed_write(records):
        replacement_started.set()
        assert allow_replacement.wait(3)
        return original_write(records)

    monkeypatch.setattr(journal, "write", delayed_write)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(journal.delete_ids, [victim])
        if replacement_started.wait(0.5):
            journal.append_many([{"id": "concurrent", "num": "3", "plate": "C333CC78"}])
            allow_replacement.set()
        else:
            # Atomic implementations do not enter the legacy table-replacement path.
            journal.append_many([{"id": "concurrent", "num": "3", "plate": "C333CC78"}])
        future.result(timeout=5)

    ids = {record["id"] for record in journal.read()}
    assert victim not in ids
    assert "concurrent" in ids


def test_restore_database_runs_archive_work_outside_ui_thread(monkeypatch, tmp_path):
    from tkinter import filedialog, messagebox
    from getpass_core import backup
    import getpass_ui.app as app_module

    ui_thread = threading.get_ident()
    calls = []
    archive = tmp_path / "backup.zip"

    def inspect_backup(_path, password=None):
        calls.append(("inspect", threading.get_ident()))
        return ["data/settings.json"], []

    def restore_backup(_path, password=None):
        calls.append(("restore", threading.get_ident()))
        return 1, []

    def threaded_run_task(_parent, work, title="Выполнение операции", **_kwargs):
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(work).result(timeout=5)

    monkeypatch.setattr(filedialog, "askopenfilename", lambda *args, **kwargs: str(archive))
    monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)
    monkeypatch.setattr(messagebox, "showwarning", lambda *args, **kwargs: None)
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(backup, "inspect_backup", inspect_backup)
    monkeypatch.setattr(backup, "restore_backup", restore_backup)
    monkeypatch.setattr(app_module, "run_task", threaded_run_task)

    fake_app = SimpleNamespace(
        root=SimpleNamespace(destroy=lambda: None),
        preview=SimpleNamespace(cancel=lambda: None),
        badge=SimpleNamespace(preview=SimpleNamespace(cancel=lambda: None)),
    )

    app_module.App.restore_database(fake_app)

    assert [name for name, _thread in calls] == ["inspect", "restore"]
    assert all(thread_id != ui_thread for _name, thread_id in calls)
