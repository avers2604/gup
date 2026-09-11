import hashlib
import json
import os
import sqlite3
import zipfile
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest

from getpass_core import backup


def test_rejects_paths_outside_data(tmp_path):
    archive = tmp_path / "mal.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("data/журнал_пропусков.csv", "a;b\n")
        z.writestr("photos/ivanov.jpg", "JPG")
        z.writestr("../../evil.dll", "MZ")
        z.writestr("/abs/evil.exe", "MZ")
        z.writestr("python311.dll", "MZ")
        z.writestr("sub/../../escape.txt", "x")
    accepted, skipped = backup.inspect_backup(str(archive))
    assert set(accepted) == {"data/журнал_пропусков.csv", "photos/ivanov.jpg"}
    assert "../../evil.dll" in skipped
    assert "python311.dll" in skipped
    assert "/abs/evil.exe" in skipped


def test_backup_roundtrip(tmp_path, data_dir, monkeypatch):
    from getpass_core import config

    monkeypatch.setattr(config, "LOG_CSV_FILE", str(data_dir / "j.csv"))
    monkeypatch.setattr(config, "LOG_XLSX_FILE", str(data_dir / "j.xlsx"))
    monkeypatch.setattr(config, "BADGE_LOG_CSV", str(data_dir / "b.csv"))
    monkeypatch.setattr(config, "BADGE_LOG_XLSX", str(data_dir / "b.xlsx"))
    monkeypatch.setattr(config, "TEMPLATE_FILE", str(tmp_path / "template.png"))
    monkeypatch.setattr(config, "ICON_FILE", str(tmp_path / "нет.ico"))
    monkeypatch.setattr(config, "FONTS_DIR", str(tmp_path / "fonts"))
    (data_dir / "j.csv").write_text("a;b\n", encoding="utf-8")
    (tmp_path / "template.png").write_bytes(b"PNG")
    (data_dir / "photos").mkdir(exist_ok=True)
    (data_dir / "photos" / "p.jpg").write_bytes(b"JPG")

    archive = tmp_path / "b.zip"
    count, size = backup.create_backup(str(archive))
    assert count >= 3 and size > 0
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
    assert backup.MANIFEST in names
    assert "template.png" in names
    assert "photos/p.jpg" in names


def test_manifest_warns_about_personal_data(tmp_path, data_dir, monkeypatch):
    from getpass_core import config

    monkeypatch.setattr(config, "TEMPLATE_FILE", str(tmp_path / "нет.png"))
    monkeypatch.setattr(config, "ICON_FILE", str(tmp_path / "нет.ico"))
    monkeypatch.setattr(config, "FONTS_DIR", str(tmp_path / "нет"))
    archive = tmp_path / "b.zip"
    backup.create_backup(str(archive))
    with zipfile.ZipFile(archive) as z:
        text = z.read(backup.MANIFEST).decode("utf-8")
    assert "персональные данные" in text
    assert "НЕ зашифрован" in text


def test_rotate_backups_removes_archives_older_than_retention(tmp_path, data_dir, monkeypatch):
    from getpass_core import config

    monkeypatch.setattr(config, "BACKUP_DIR", str(tmp_path / "backups"))
    old = tmp_path / "backups" / "backup_old.zip"
    old.parent.mkdir()
    old.write_bytes(b"old")
    old_time = (datetime.now() - timedelta(days=15)).timestamp()
    os.utime(old, (old_time, old_time))
    created = backup.rotate_backups(14)
    assert created.endswith(".zip")
    assert not old.exists()


def test_restore_rejects_checksum_mismatch(tmp_path, data_dir):
    from getpass_core import config

    target = data_dir / "settings.json"
    target.write_text("old", encoding="utf-8")
    archive = tmp_path / "bad-checksum.zip"
    payload = b"new"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("data/settings.json", payload)
        z.writestr("checksums.json", json.dumps({"data/settings.json": "0" * 64}))

    with pytest.raises(ValueError, match="Контрольная сумма"):
        backup.restore_backup(str(archive))

    assert target.read_text(encoding="utf-8") == "old"
    assert str(target) == config.CONFIG_FILE


def test_restore_remaps_badge_photo_path_inside_database(tmp_path, data_dir):
    from getpass_core import config

    source_db = tmp_path / "source.sqlite3"
    with sqlite3.connect(source_db) as conn:
        conn.execute("CREATE TABLE badge_journal (id TEXT PRIMARY KEY, photo_path TEXT)")
        conn.execute(
            "INSERT INTO badge_journal (id, photo_path) VALUES (?, ?)",
            ("badge-1", r"C:\\Old\\Photos\\ivanov.jpg"),
        )

    photo = b"JPG"
    archive = tmp_path / "db-restore.zip"
    db_arcname = "data/" + os.path.basename(config.DB_FILE)
    with zipfile.ZipFile(archive, "w") as z:
        z.write(source_db, db_arcname)
        z.writestr("photos/ivanov.jpg", photo)
        z.writestr(
            "checksums.json",
            json.dumps(
                {
                    db_arcname: hashlib.sha256(source_db.read_bytes()).hexdigest(),
                    "photos/ivanov.jpg": hashlib.sha256(photo).hexdigest(),
                }
            ),
        )

    restored, skipped = backup.restore_backup(str(archive))

    assert restored == 2
    assert "checksums.json" in skipped
    with sqlite3.connect(config.DB_FILE) as conn:
        stored = conn.execute(
            "SELECT photo_path FROM badge_journal WHERE id='badge-1'"
        ).fetchone()[0]
    assert stored == os.path.join(config.PHOTO_DIR, "ivanov.jpg")
    assert (data_dir / "photos" / "ivanov.jpg").read_bytes() == photo


def test_restore_rolls_back_files_when_later_apply_fails(tmp_path, data_dir, monkeypatch):
    from getpass_core import config

    template = tmp_path / "template.png"
    monkeypatch.setattr(config, "TEMPLATE_FILE", str(template))
    settings = data_dir / "settings.json"
    settings.write_text("old-settings", encoding="utf-8")
    template.write_bytes(b"old-template")

    archive = tmp_path / "rollback.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("data/settings.json", "new-settings")
        z.writestr("template.png", b"new-template")

    original_atomic_output = backup.atomic_output

    @contextmanager
    def fail_on_template(path):
        if path == str(template):
            raise OSError("simulated apply failure")
        with original_atomic_output(path) as temporary:
            yield temporary

    monkeypatch.setattr(backup, "atomic_output", fail_on_template)

    with pytest.raises(OSError, match="simulated apply failure"):
        backup.restore_backup(str(archive))

    assert settings.read_text(encoding="utf-8") == "old-settings"
    assert template.read_bytes() == b"old-template"
