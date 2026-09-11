from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import sqlite3
import zipfile
from contextlib import closing
import pytest
from PIL import Image
from getpass_core import config, backup, issuance
from getpass_core.pdfwriter import write_pdf
from getpass_core.importing import photo_in_folder, validate_items


def test_parallel_append_preserves_every_record(journal):
    journal.read()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda n: journal.append_many([{"num": str(n)}]), range(24)))
    assert {r["num"] for r in journal.read()} == {str(n) for n in range(24)}


def test_stale_edit_rejected(journal):
    before = journal.append_many([{"num": "1"}])[0]
    journal.update_record(before["id"], {"driver": "First"})
    with pytest.raises(ValueError, match="другом"):
        journal.update_record(before["id"], {"driver": "Second"}, expected=before)
    assert journal.read()[0]["driver"] == "First"


def test_audit_is_immutable(journal):
    journal.append_many([{"num": "1"}])
    with closing(sqlite3.connect(config.DB_FILE)) as conn:
        assert conn.execute("SELECT action FROM journal_events").fetchone()[0] == "created"
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM journal_events")


def test_confirm_is_idempotent(journal):
    key = issuance.prepare(journal, [{"num": "1", "plate": "A111AA78"}], "printer")
    assert journal.read() == []
    assert len(issuance.pending(journal)) == 1
    issuance.confirm(journal, key)
    issuance.confirm(journal, key)
    assert len(journal.read()) == 1
    assert issuance.pending(journal) == []


def test_failed_pdf_preserves_existing_file(tmp_path):
    target = tmp_path / "report.pdf"
    target.write_bytes(b"original")
    def pages():
        yield Image.new("RGB", (10, 10))
        raise RuntimeError("cancel")
    with pytest.raises(RuntimeError):
        write_pdf(pages(), str(target))
    assert target.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [target]


def test_empty_pdf_does_not_create_output(tmp_path):
    target = tmp_path / "report.pdf"
    with pytest.raises(ValueError):
        write_pdf([], str(target))
    assert not target.exists()


@pytest.mark.parametrize("name", ["../outside.jpg", "/outside.jpg", "sub/../../outside.jpg"])
def test_import_rejects_escape(tmp_path, name):
    with pytest.raises(ValueError):
        photo_in_folder(tmp_path, name)


def test_import_reports_invalid_dates_and_missing_photo(journal):
    result = validate_items([{"tab_num": "1", "surname": "Test", "name": "Name",
                              "issue_date": "bad", "valid_until": "bad"}], journal, badge=True)
    assert len(result[0][1]) >= 2


def test_backup_includes_blacklist_and_checksums(data_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BLACKLIST_FILE", str(data_dir / "blacklist.json"))
    Path(config.BLACKLIST_FILE).write_text("[]")
    target = tmp_path / "backup.zip"
    backup.create_backup(str(target))
    with zipfile.ZipFile(target) as archive:
        assert "data/blacklist.json" in archive.namelist()
        hashes = json.loads(archive.read("checksums.json"))
        assert len(hashes["data/blacklist.json"]) == 64


def test_corrupt_backup_does_not_replace_data(data_dir, tmp_path):
    Path(config.CONFIG_FILE).write_text("original")
    target = tmp_path / "bad.zip"
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("data/settings.json", "{}")
        archive.writestr("checksums.json", json.dumps({"data/settings.json": "bad"}))
    with pytest.raises(ValueError, match="сумма"):
        backup.restore_backup(str(target))
    assert Path(config.CONFIG_FILE).read_text() == "original"


def test_encrypted_backup_roundtrip(data_dir, tmp_path):
    Path(config.CONFIG_FILE).write_text('{"theme":"dark"}')
    target = tmp_path / "backup.gupbak"
    backup.create_backup(str(target), password="test-password-123")
    assert not zipfile.is_zipfile(target)
    with pytest.raises(ValueError, match="пароль"):
        backup.restore_backup(str(target), password="wrong-password")
    Path(config.CONFIG_FILE).write_text("{}")
    backup.restore_backup(str(target), password="test-password-123")
    assert json.loads(Path(config.CONFIG_FILE).read_text())["theme"] == "dark"


def test_database_snapshot_restores(journal, tmp_path):
    journal.append_many([{"num": "1"}])
    target = tmp_path / "backup.zip"
    backup.create_backup(str(target))
    journal.append_many([{"num": "2"}])
    backup.restore_backup(str(target))
    assert [r["num"] for r in journal.read()] == ["1"]


def test_snapshot_failure_preserves_existing_archive(data_dir, tmp_path):
    Path(config.DB_FILE).write_bytes(b"not a database")
    target = tmp_path / "backup.zip"
    target.write_bytes(b"previous")
    with pytest.raises(sqlite3.DatabaseError):
        backup.create_backup(str(target))
    assert target.read_bytes() == b"previous"
