from getpass_core import config


class TestRedaction:
    def test_removes_phone_fio_and_plate(self):
        text = "Водитель Смирнов А.В. тел +7 (921) 111-22-33 на О777ТВ198"
        out = config.redact_pii(text)
        assert "Смирнов" not in out
        assert "111-22-33" not in out
        assert "О777ТВ198" not in out

    def test_keeps_technical_text(self):
        text = 'File "pass_generator.py", line 42, in render_pass'
        assert config.redact_pii(text) == text


class TestDataDirResolution:
    def test_honors_environment_override(self, tmp_path, monkeypatch):
        target = tmp_path / "override"
        monkeypatch.setenv("GET_PASSES_DATA_DIR", str(target))

        assert config.resolve_data_dir() == str(target.resolve())
        assert target.is_dir()

    def test_prefers_writable_script_dir_when_legacy_data_exists(self, tmp_path, monkeypatch):
        script_dir = tmp_path / "app"
        script_dir.mkdir()
        (script_dir / "settings.json").write_text("{}", encoding="utf-8")
        monkeypatch.delenv("GET_PASSES_DATA_DIR", raising=False)
        monkeypatch.setattr(config, "SCRIPT_DIR", str(script_dir))
        monkeypatch.setattr(config, "_is_writable", lambda path: path == str(script_dir))

        assert config.resolve_data_dir() == str(script_dir)

    def test_migrates_legacy_data_to_user_dir_when_script_is_read_only(
        self, tmp_path, monkeypatch
    ):
        script_dir = tmp_path / "app"
        user_dir = tmp_path / "user-data"
        script_dir.mkdir()
        (script_dir / "settings.json").write_text('{"theme":"dark"}', encoding="utf-8")
        monkeypatch.delenv("GET_PASSES_DATA_DIR", raising=False)
        monkeypatch.setattr(config, "SCRIPT_DIR", str(script_dir))
        monkeypatch.setattr(config, "_is_writable", lambda _path: False)
        monkeypatch.setattr(config, "_user_data_dir", lambda: str(user_dir))

        assert config.resolve_data_dir() == str(user_dir)
        assert (user_dir / "settings.json").read_text(encoding="utf-8") == '{"theme":"dark"}'


class TestSettings:
    def test_defaults_when_no_file(self, data_dir):
        s = config.load_settings()
        assert s["last_pass_num"] == "001-26"
        assert "issue_date" in s

    def test_roundtrip(self, data_dir):
        config.save_settings({"last_pass_num": "042-26", "print_mode": "a5"})
        s = config.load_settings()
        assert s["last_pass_num"] == "042-26"
        assert s["print_mode"] == "a5"

    def test_ignores_unknown_and_null_keys(self, data_dir):
        import json

        config.CONFIG_FILE  # noqa
        with open(config.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_pass_num": None, "мусор": 1, "print_mode": "a5"}, f)
        s = config.load_settings()
        assert s["last_pass_num"] == "001-26"
        assert s["print_mode"] == "a5"
        assert "мусор" not in s

    def test_corrupt_file_falls_back_to_defaults(self, data_dir):
        with open(config.CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write("{это не json")
        assert config.load_settings()["last_pass_num"] == "001-26"
