"""Изоляция: каждый тест работает в своём каталоге данных."""
import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    from getpass_core import config
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", str(d))
    monkeypatch.setattr(config, "PHOTO_DIR", str(d / "photos"))
    monkeypatch.setattr(config, "CONFIG_FILE", str(d / "settings.json"))
    monkeypatch.setattr(config, "CARS_CACHE_FILE", str(d / "cars.json"))
    monkeypatch.setattr(config, "CRASH_LOG_FILE", str(d / "crash.log"))
    monkeypatch.setattr(config, "DB_FILE", str(d / "test.sqlite3"))
    monkeypatch.setattr(config, "BLACKLIST_FILE", str(d / "blacklist.json"))
    monkeypatch.setattr(config, "BACKUP_DIR", str(d / "backups"))
    return d


@pytest.fixture
def journal(data_dir):
    """Чистый журнал пропусков ТС во временном каталоге."""
    from getpass_core import storage
    schema = storage.JournalSchema(
        name="Тест", csv_path=str(data_dir / "j.csv"), xlsx_path=str(data_dir / "j.xlsx"),
        table="test_journal",
        fields=storage.PASS_SCHEMA.fields, dup_key="plate",
        legacy_layouts=storage.PASS_SCHEMA.legacy_layouts)
    return storage.Journal(schema)


@pytest.fixture
def template():
    """Бланк строится кодом; фикстура лишь сбрасывает кэш подложки."""
    from getpass_core import render
    render.reset_template_cache()
    yield None
    render.reset_template_cache()
