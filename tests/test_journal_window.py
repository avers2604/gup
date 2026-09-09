"""Окно журнала: расширенные фильтры (дата, зона, водитель)."""
import os

import pytest

tkinter = pytest.importorskip("tkinter")

needs_display = pytest.mark.skipif(not os.environ.get("DISPLAY"),
                                   reason="нужен X-сервер")


@needs_display
class TestJournalFilters:
    @pytest.fixture
    def win(self, journal, monkeypatch):
        from getpass_ui.journal import JournalWindow
        from getpass_ui.theme import Theme
        root = tkinter.Tk()
        th = Theme(root, "light")
        journal.append_many([
            {"num": "1", "plate": "А1АА78", "zone": "Парковка", "driver": "Иванов И.И.",
             "issue_date": "01.01.2026", "valid_until": "31.12.2030"},
            {"num": "2", "plate": "А2АА78", "zone": 'ПТО "Шаврова"', "driver": "Петров П.П.",
             "issue_date": "01.06.2026", "valid_until": "31.12.2030"},
            {"num": "3", "plate": "А3АА78", "zone": "Парковка", "driver": "Сидоров-Иванов",
             "issue_date": "01.09.2026", "valid_until": "31.12.2030"},
        ])
        jw = JournalWindow(root, journal, "Тест", th)
        jw.filter_var.set("all")
        root.update()
        yield jw
        root.destroy()

    def _shown_nums(self, jw):
        return {jw.tree.item(iid, "values")[0] for iid in jw.tree.get_children()}

    def test_zone_filter_is_populated_from_data(self, win):
        assert "zone" in win._extra_widgets
        values = list(win._extra_widgets["zone"].widget.cget("values"))
        assert "Парковка" in values and 'ПТО "Шаврова"' in values

    def test_zone_filter_narrows_results(self, win):
        win._extra_widgets["zone"].set("Парковка")
        win.apply_filter()
        assert self._shown_nums(win) == {"1", "3"}

    def test_driver_filter_is_substring_case_insensitive(self, win):
        win._extra_widgets["driver"].set("иванов")
        win.apply_filter()
        assert self._shown_nums(win) == {"1", "3"}

    def test_date_range_filters_by_issue_date(self, win):
        win.date_from.set("01.05.2026")
        win.date_to.set("01.08.2026")
        win.apply_filter()
        assert self._shown_nums(win) == {"2"}

    def test_date_range_blank_means_unbounded(self, win):
        win.apply_filter()
        assert self._shown_nums(win) == {"1", "2", "3"}

    def test_combined_filters(self, win):
        win._extra_widgets["zone"].set("Парковка")
        win.date_from.set("01.08.2026")
        win.apply_filter()
        assert self._shown_nums(win) == {"3"}

    def test_status_column_shows_computed_state_not_raw_value(self, win):
        rec = next(r for r in win.records if r["num"] == "2")
        rec["valid_until"] = "01.01.2020"     # просрочен относительно «сегодня»
        win.apply_filter()
        target_id = rec["id"]
        values = win.tree.item(target_id, "values")
        status_idx = [f.key for f in win.visible_fields].index("status")
        assert values[status_idx] == "просрочен"
