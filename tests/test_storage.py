import csv

from getpass_core.storage import STATUS_ACTIVE, STATUS_REVOKED


def write_legacy(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(header)
        w.writerows(rows)


class TestMigration:
    def test_reads_six_column_legacy(self, journal):
        write_legacy(journal.schema.csv_path,
                     ["Номер пропуска", "Номер машины", "Зона допуска", "Водитель",
                      "Дата выдачи", "Действителен до"],
                     [["001-26", "О777ТВ198", "Парковка", "Смирнов А.В.",
                       "01.01.2026", "31.12.2026"]])
        rec = journal.read()[0]
        assert rec["valid_until"] == "31.12.2026"
        assert rec["phone"] == ""            # телефона в старом формате не было
        assert rec["status"] == STATUS_ACTIVE
        assert rec["id"]

    def test_reads_seven_column_legacy(self, journal):
        write_legacy(journal.schema.csv_path,
                     ["Номер пропуска", "Номер машины", "Зона допуска", "Водитель",
                      "Телефон", "Дата выдачи", "Действителен до"],
                     [["001-26", "О777ТВ198", "Парковка", "Смирнов А.В.",
                       "+7 (921) 111-22-33", "01.01.2026", "31.12.2026"]])
        rec = journal.read()[0]
        assert rec["phone"] == "+7 (921) 111-22-33"
        assert rec["valid_until"] == "31.12.2026"

    def test_id_is_stable_across_rewrites(self, journal):
        journal.append_many([{"num": "001-26", "plate": "О777ТВ198"}])
        first = journal.read()[0]["id"]
        journal.write(journal.read())
        assert journal.read()[0]["id"] == first

    def test_skips_blank_rows(self, journal):
        journal.append_many([{"num": "001-26", "plate": "А111АА78"}])
        with open(journal.schema.csv_path, "a", encoding="utf-8-sig") as f:
            f.write(";;;;;;;;;;;\n")
        assert len(journal.read()) == 1


class TestOperations:
    def test_append_many_writes_once(self, journal, monkeypatch):
        calls = []
        original = journal.write
        monkeypatch.setattr(journal, "write", lambda recs: (calls.append(1), original(recs))[1])
        journal.append_many([{"num": f"{i:03d}-26", "plate": f"А{i:03d}АА78"}
                             for i in range(50)])
        assert len(calls) == 1               # раньше здесь было 50 перезаписей
        assert len(journal.read()) == 50

    def test_delete_by_id_survives_external_edit(self, journal):
        journal.append_many([{"num": f"{i:03d}-26", "plate": f"А{i:03d}АА78"}
                             for i in range(10)])
        recs = journal.read()
        victim = recs[5]["id"]
        # кто-то вставил строку в Excel: индексы сдвинулись
        recs.insert(0, dict(recs[0], id="вставка", num="ВСТАВКА"))
        journal.write(recs)
        journal.delete_ids([victim])
        left = [r["id"] for r in journal.read()]
        assert victim not in left
        assert "вставка" in left             # удалили ровно то, что просили

    def test_revoke_keeps_record(self, journal):
        journal.append_many([{"num": "001-26", "plate": "А111АА78",
                              "valid_until": "31.12.2030"}])
        rec_id = journal.read()[0]["id"]
        journal.revoke_ids([rec_id], "утеря бланка", when="08.09.2026")
        rec = journal.read()[0]
        assert rec["status"] == STATUS_REVOKED
        assert rec["revoke_reason"] == "утеря бланка"
        assert rec["revoked_at"] == "08.09.2026"

    def test_update_record_by_id(self, journal):
        journal.append_many([{"num": "001-26", "plate": "А111АА78"}])
        rec_id = journal.read()[0]["id"]
        journal.update_record(rec_id, {"driver": "Иванов И.И."})
        assert journal.read()[0]["driver"] == "Иванов И.И."


class TestSelection:
    def test_splits_active_expired_unknown(self, journal):
        from datetime import date
        journal.append_many([
            {"num": "1", "plate": "А1АА78", "valid_until": "31.12.2030"},
            {"num": "2", "plate": "А2АА78", "valid_until": "01.01.2020"},
            {"num": "3", "plate": "А3АА78", "valid_until": ""},
            {"num": "4", "plate": "А4АА78", "valid_until": "мусор"},
        ])
        live, expired, unknown = journal.active(today=date(2026, 9, 8))
        assert [r["num"] for r in live] == ["1"]
        assert [r["num"] for r in expired] == ["2"]
        assert {r["num"] for r in unknown} == {"3", "4"}

    def test_revoked_not_counted_active(self, journal):
        journal.append_many([{"num": "1", "plate": "А1АА78", "valid_until": "31.12.2030"}])
        journal.revoke_ids([journal.read()[0]["id"]], "тест")
        live, _, _ = journal.active()
        assert live == []

    def test_duplicates_match_across_layouts(self, journal):
        journal.append_many([{"num": "1", "plate": "О777ТВ198", "valid_until": "31.12.2030"}])
        assert len(journal.find_duplicates("O777TB198")) == 1     # латиница
        assert len(journal.find_duplicates("о 777 тв 198")) == 1  # пробелы, регистр
        assert journal.find_duplicates("А111АА78") == []

    def test_duplicates_ignore_revoked(self, journal):
        journal.append_many([{"num": "1", "plate": "О777ТВ198", "valid_until": "31.12.2030"}])
        journal.revoke_ids([journal.read()[0]["id"]], "тест")
        assert journal.find_duplicates("О777ТВ198") == []


class TestCarsCache:
    def test_latin_and_cyrillic_are_one_car(self, data_dir):
        from getpass_core.storage import lookup_car, update_cars_cache
        update_cars_cache([{"plate": "О777ТВ198", "brand": "ГАЗ", "model": "Газель"}])
        assert lookup_car("O777TB198")["brand"] == "ГАЗ"

    def test_batch_update(self, data_dir):
        from getpass_core.storage import load_cars_cache, update_cars_cache
        update_cars_cache([{"plate": f"А{i:03d}АА78", "brand": "ГАЗ"} for i in range(20)])
        assert len(load_cars_cache()) == 20
