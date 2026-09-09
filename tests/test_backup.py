import zipfile
from datetime import datetime, timedelta

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
    assert "template.png" in names          # без бланка копия неработоспособна
    assert "photos/p.jpg" in names          # фотографии тоже входят


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
    import os
    os.utime(old, (old_time, old_time))
    created = backup.rotate_backups(14)
    assert created.endswith(".zip")
    assert not old.exists()
