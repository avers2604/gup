from datetime import datetime

import pytest

from getpass_core.domain import (add_months_safe, add_years_safe, format_plate_visual,
                                 format_phone,
                                 get_excel_col_letter, is_active_on, next_number,
                                 normalize_plate, parse_date)


class TestDates:
    def test_add_months_clamps_day(self):
        assert add_months_safe(datetime(2026, 1, 31), 1) == datetime(2026, 2, 28)
        assert add_months_safe(datetime(2024, 1, 31), 1) == datetime(2024, 2, 29)

    def test_add_months_crosses_year(self):
        assert add_months_safe(datetime(2026, 11, 15), 3) == datetime(2027, 2, 15)

    def test_add_years_handles_leap_day(self):
        assert add_years_safe(datetime(2024, 2, 29), 1) == datetime(2025, 2, 28)

    @pytest.mark.parametrize("raw", ["", "   ", None, "31.02.2026", "2026-01-01", "мусор"])
    def test_parse_date_rejects_bad_input(self, raw):
        assert parse_date(raw) is None

    def test_parse_date_accepts_valid(self):
        assert parse_date(" 08.09.2026 ") == datetime(2026, 9, 8)

    def test_is_active_returns_none_for_unparseable(self):
        # запись без срока не должна молча считаться действующей
        assert is_active_on("", datetime(2026, 9, 8).date()) is None
        assert is_active_on("31.12.2026", datetime(2026, 9, 8).date()) is True
        assert is_active_on("01.01.2020", datetime(2026, 9, 8).date()) is False


class TestNumbers:
    @pytest.mark.parametrize("src,expected", [
        ("001-26", "002-26"), ("099-26", "100-26"), ("01035", "01036"),
        ("А-15/26", "А-16/26"), ("б/н", "б/н"), ("", "001-26"),
    ])
    def test_increments_first_group(self, src, expected):
        assert next_number(src).value == expected

    def test_flags_overflow(self):
        assert next_number("999-26").overflowed is True
        assert next_number("099-26").overflowed is False

    def test_no_digits_is_unchanged(self):
        r = next_number("б/н")
        assert r.value == "б/н" and r.incremented is False


class TestPlates:
    def test_latin_lookalikes_normalize_to_cyrillic(self):
        assert normalize_plate("O777TB198") == normalize_plate("О 777 ТВ 198")

    def test_normalize_strips_spaces_and_case(self):
        assert normalize_plate(" о777тв198 ") == "О777ТВ198"

    @pytest.mark.parametrize("raw,expected", [
        ("О777ТВ198", "О  777  ТВ   198"),
        ("O777TB198", "О  777  ТВ   198"),
        ("1234АВ78", "1234  АВ   78"),
        ("АА123777", "АА  1237   77"),
    ])
    def test_visual_formats(self, raw, expected):
        assert format_plate_visual(raw) == expected

    def test_unknown_format_passes_through(self):
        assert format_plate_visual("нестандарт") == "НЕСТАНДАРТ"


class TestPhones:
    def test_phone_is_limited_and_formatted(self):
        assert format_phone("8 (921) 111-22-33 extra") == "+7 (921) 111-22-33"
        assert format_phone("+79211112233") == "+7 (921) 111-22-33"


def test_excel_columns():
    assert get_excel_col_letter(1) == "A"
    assert get_excel_col_letter(26) == "Z"
    assert get_excel_col_letter(27) == "AA"
