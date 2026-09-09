from getpass_core import blacklist


def test_blacklist_matches_plate_and_fio(data_dir, monkeypatch):
    from getpass_core import config
    monkeypatch.setattr(config, "BLACKLIST_FILE", str(data_dir / "blacklist.json"))
    blacklist.add(plate="о 777 тв 198", fio="Иванов Иван Иванович", incident="ДТП в парке")
    assert blacklist.find(plate="О777ТВ198")[0]["incident"] == "ДТП в парке"
    assert blacklist.find(fio="иванов   иван иванович")
    assert blacklist.find(plate="А111АА78") == []