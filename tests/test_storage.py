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

    def test_second_update_does_not_erase_missing_fields(self, data_dir):
        """Повторная выдача пропуска без цвета/модели не должна стирать
        ранее сохранённые значения — иначе данные о машине постепенно
        обнуляются на каждой перевыдаче."""
        from getpass_core.storage import lookup_car, update_cars_cache
        update_cars_cache([{"plate": "О777ТВ198", "brand": "ГАЗ", "model": "Газель",
                            "color": "белый"}])
        update_cars_cache([{"plate": "О777ТВ198", "brand": "ГАЗ", "model": "", "color": ""}])
        car = lookup_car("О777ТВ198")
        assert car["model"] == "Газель"
        assert car["color"] == "белый"

    def test_second_update_still_overwrites_provided_fields(self, data_dir):
        from getpass_core.storage import lookup_car, update_cars_cache
        update_cars_cache([{"plate": "О777ТВ198", "brand": "ГАЗ", "color": "белый"}])
        update_cars_cache([{"plate": "О777ТВ198", "brand": "ГАЗ", "color": "синий"}])
        assert lookup_car("О777ТВ198")["color"] == "синий"


class TestExport:
    def test_exports_csv(self, journal, tmp_path):
        from getpass_core.storage import export_journal
        journal.append_many([{"num": "001-26", "plate": "О777ТВ198",
                              "driver": "Смирнов А.В.", "valid_until": "31.12.2026"}])
        out = tmp_path / "выгрузка.csv"
        assert export_journal(journal, str(out)) == 1
        text = out.read_text(encoding="utf-8-sig")
        assert "Номер пропуска" in text
        assert "О777ТВ198" in text

    def test_exports_xlsx(self, journal, tmp_path):
        import zipfile

        from getpass_core.storage import export_journal
        journal.append_many([{"num": "001-26", "plate": "А111АА78"}])
        out = tmp_path / "выгрузка.xlsx"
        assert export_journal(journal, str(out)) == 1
        with zipfile.ZipFile(out) as z:
            assert "xl/worksheets/sheet1.xml" in z.namelist()
            assert b"\xd0\x90111\xd0\x90\xd0\x9078" in z.read("xl/worksheets/sheet1.xml")

    def test_export_of_empty_journal(self, journal, tmp_path):
        from getpass_core.storage import export_journal
        assert export_journal(journal, str(tmp_path / "пусто.csv")) == 0


class TestBadgePhotoReference:
    def test_photo_path_round_trips_through_journal(self, data_dir):
        """Ссылка на фото должна сохраняться в журнале бейджей, иначе бейдж
        нельзя перевыпустить без повторной загрузки и обрезки фотографии."""
        from getpass_core.storage import BADGE_SCHEMA, Journal
        schema = BADGE_SCHEMA.__class__(
            name="Тест", csv_path=str(data_dir / "b.csv"), xlsx_path=str(data_dir / "b.xlsx"),
            fields=BADGE_SCHEMA.fields, dup_key="tab_num",
            legacy_layouts=BADGE_SCHEMA.legacy_layouts)
        badge_journal = Journal(schema)
        badge_journal.append_many([{"tab_num": "00001", "fio": "Иванов И.И.",
                                    "photo_path": "/data/photos/00001.jpg"}])
        assert badge_journal.read()[0]["photo_path"] == "/data/photos/00001.jpg"

    def test_old_badge_csv_without_photo_column_still_reads(self, data_dir):
        """Файлы, созданные до появления колонки «Фото», не должны падать —
        photo_path просто остаётся пустым."""
        from getpass_core.storage import BADGE_SCHEMA, Journal
        schema = BADGE_SCHEMA.__class__(
            name="Тест", csv_path=str(data_dir / "b.csv"), xlsx_path=str(data_dir / "b.xlsx"),
            fields=BADGE_SCHEMA.fields, dup_key="tab_num",
            legacy_layouts=BADGE_SCHEMA.legacy_layouts)
        badge_journal = Journal(schema)
        write_legacy(schema.csv_path,
                     ["Табельный номер", "ФИО сотрудника", "Должность", "Подразделение",
                      "Телефон", "Дата выдачи", "Действителен до"],
                     [["00001", "Иванов И.И.", "Слесарь", "Парк №1",
                       "+7 (921) 111-22-33", "01.01.2026", "31.12.2026"]])
        rec = badge_journal.read()[0]
        assert rec["photo_path"] == ""
        assert rec["fio"] == "Иванов И.И."


class TestDistinctAndBrands:
    def test_distinct_returns_sorted_unique_nonempty(self, journal):
        journal.append_many([
            {"num": "1", "plate": "А1АА78", "zone": "Парковка"},
            {"num": "2", "plate": "А2АА78", "zone": 'ПТО "Шаврова"'},
            {"num": "3", "plate": "А3АА78", "zone": "Парковка"},
            {"num": "4", "plate": "А4АА78", "zone": ""},
        ])
        assert journal.distinct("zone") == ["Парковка", 'ПТО "Шаврова"']

    def test_distinct_on_empty_journal(self, journal):
        assert journal.distinct("zone") == []

    def test_known_car_brands_sorted_and_deduped(self, data_dir):
        from getpass_core.storage import known_car_brands, update_cars_cache
        update_cars_cache([
            {"plate": "А1АА78", "brand": "ГАЗ"},
            {"plate": "А2АА78", "brand": "ПАЗ"},
            {"plate": "А3АА78", "brand": "ГАЗ"},
        ])
        assert known_car_brands() == ["ГАЗ", "ПАЗ"]

    def test_known_car_brands_empty_when_no_cache(self, data_dir):
        from getpass_core.storage import known_car_brands
        assert known_car_brands() == []
