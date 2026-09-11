import json
import os
import threading
from types import SimpleNamespace

import pytest
from PIL import Image

from getpass_core import issuance


def _make_photo(path):
    Image.new("RGB", (64, 64), "white").save(path, "JPEG")


def test_prepare_does_not_mutate_input_and_cancel_removes_owned_photo(journal, data_dir, tmp_path):
    source = tmp_path / "employee.jpg"
    _make_photo(source)
    records = [{"num": "1", "plate": "A111AA78", "photo_path": str(source)}]
    original = [dict(records[0])]

    operation_id = issuance.prepare(journal, records, "printer")

    assert records == original
    job = issuance.pending(journal)[0]
    stored = json.loads(job["records_json"])[0]
    copied_photo = stored["photo_path"]
    assert copied_photo != str(source)
    assert os.path.isfile(copied_photo)

    issuance.cancel(journal, operation_id)

    assert not os.path.exists(copied_photo)
    assert issuance.pending(journal) == []


def test_prepare_failure_removes_copied_photo_and_keeps_input_unchanged(
    journal, data_dir, tmp_path, monkeypatch
):
    source = tmp_path / "employee.jpg"
    _make_photo(source)
    records = [{"num": "1", "plate": "A111AA78", "photo_path": str(source)}]
    original = [dict(records[0])]

    def fail_json(*_args, **_kwargs):
        raise RuntimeError("serialization failed")

    monkeypatch.setattr(issuance.json, "dumps", fail_json)

    with pytest.raises(RuntimeError, match="serialization failed"):
        issuance.prepare(journal, records, "printer")

    assert records == original
    photo_dir = data_dir / "photos"
    assert not photo_dir.exists() or list(photo_dir.iterdir()) == []


def test_prepare_cleans_previous_photo_when_later_photo_is_invalid(
    journal, data_dir, tmp_path
):
    good = tmp_path / "good.jpg"
    _make_photo(good)
    missing = tmp_path / "missing.jpg"
    records = [
        {"num": "1", "plate": "A111AA78", "photo_path": str(good)},
        {"num": "2", "plate": "B222BB78", "photo_path": str(missing)},
    ]
    original = [dict(record) for record in records]

    with pytest.raises(ValueError):
        issuance.prepare(journal, records, "printer")

    assert records == original
    photo_dir = data_dir / "photos"
    assert not photo_dir.exists() or list(photo_dir.iterdir()) == []


def test_confirm_rejects_non_prepared_unknown_state(journal):
    operation_id = issuance.prepare(
        journal, [{"num": "1", "plate": "A111AA78"}], "printer"
    )
    conn = journal._connect()
    try:
        with conn:
            conn.execute(
                "UPDATE issuance_jobs SET state='corrupt' WHERE id=?",
                (operation_id,),
            )
    finally:
        conn.close()

    with pytest.raises(ValueError, match="состояни"):
        issuance.confirm(journal, operation_id)

    assert journal.read() == []


def test_batch_pdf_failure_cancels_unusable_operation(journal, monkeypatch, tmp_path):
    import getpass_ui.batch as batch

    output = tmp_path / "batch.pdf"

    def fail_pdf(_pages, _path):
        raise OSError("disk full")

    monkeypatch.setattr(batch, "save_pdf_pages", fail_pdf)

    with pytest.raises(OSError, match="disk full"):
        batch._prepare_batch_pdf(
            journal,
            [{"num": "1", "plate": "A111AA78"}],
            str(output),
            lambda: iter([object()]),
            threading.Event(),
        )

    assert issuance.pending(journal) == []


def test_single_pass_save_failure_cancels_prepared_operation(
    journal, monkeypatch, tmp_path
):
    from tkinter import filedialog, messagebox
    import getpass_ui.app as app_module

    output = tmp_path / "pass.pdf"
    records = [{"num": "1", "plate": "A111AA78"}]
    fake = SimpleNamespace(
        _issuance_id=None,
        build_documents=lambda: (
            object(),
            None,
            "pass",
            records,
            SimpleNamespace(value="2"),
        ),
        _finish_pass=lambda *_args: True,
    )
    fake._save_pass_file = lambda document, back_document, path: (
        app_module.App._save_pass_file(fake, document, back_document, path)
    )
    fake._report_pass_save_failure = lambda operation_id, exc: (
        app_module.App._report_pass_save_failure(fake, operation_id, exc)
    )
    monkeypatch.setattr(app_module, "PASS_JOURNAL", journal)
    monkeypatch.setattr(
        filedialog, "asksaveasfilename", lambda *args, **kwargs: str(output)
    )
    monkeypatch.setattr(
        app_module.printing,
        "save_document",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)

    app_module.App.generate_pass(fake)

    assert issuance.pending(journal) == []
    assert fake._issuance_id is None


def test_badge_save_failure_cancels_prepared_operation(data_dir, monkeypatch, tmp_path):
    from tkinter import filedialog, messagebox
    from getpass_core import storage
    import getpass_ui.badge_tab as badge_module

    output = tmp_path / "badge.pdf"
    badge_journal = storage.Journal(storage.BADGE_SCHEMA)
    data = {"tab_num": "100", "surname": "ИВАНОВ", "name": "ИВАН"}
    fake = SimpleNamespace(
        _issuance_id=None,
        validated_data=lambda: data,
        build_document=lambda _data: (object(), "badge"),
        _finish=lambda _data: "101",
    )
    monkeypatch.setattr(badge_module, "BADGE_JOURNAL", badge_journal)
    monkeypatch.setattr(
        filedialog, "asksaveasfilename", lambda *args, **kwargs: str(output)
    )
    monkeypatch.setattr(
        badge_module.printing,
        "save_document",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)

    badge_module.BadgePanel.generate_pdf(fake)

    assert issuance.pending(badge_journal) == []
    assert fake._issuance_id is None
