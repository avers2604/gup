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


class TestSettings:
    def test_defaults_when_no_file(self, data_dir):
        s = config.load_settings()
        assert s["last_pass_num"] == "001-26"
        assert "issue_date" in s

    def test_roundtrip(self, data_dir):
        config.save_settings({"last_pass_num": "042-26", "operator_name": "Петров"})
        s = config.load_settings()
        assert s["last_pass_num"] == "042-26"
        assert s["operator_name"] == "Петров"

    def test_ignores_unknown_and_null_keys(self, data_dir):
        import json
        config.CONFIG_FILE  # noqa
        with open(config.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_pass_num": None, "мусор": 1, "print_mode": "a5"}, f)
        s = config.load_settings()
        assert s["last_pass_num"] == "001-26"     # null не затирает значение
        assert s["print_mode"] == "a5"
        assert "мусор" not in s

    def test_corrupt_file_falls_back_to_defaults(self, data_dir):
        with open(config.CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write("{это не json")
        assert config.load_settings()["last_pass_num"] == "001-26"
