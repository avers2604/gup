"""Отрисовка бланков. Хеши не фиксируем: набор шрифтов зависит от машины —
проверяем геометрию, детерминизм и отсутствие переполнения колонок."""
import pytest
from PIL import Image, ImageDraw

from getpass_core import render as R
from getpass_core.fonts import get_echoes_font
from getpass_core.registry import (BADGE_REGISTRY, PASS_REGISTRY,
                                   build_registry_pages)

PASS = {"num": "017-26", "plate": "О777ТВ198", "brand": "ГАЗ", "model": "Газель NEXT",
        "type": "Служебный", "color": "Белый", "d_pos": "Водитель",
        "d_fio": "Смирнов А.В.", "phone": "+7 (921) 111-22-33",
        "driver_full": "Водитель Смирнов А.В.", "territory": 'ПТО "Шаврова"'}
COMMON = {"issue_date": "08.09.2026", "valid_until": "31.12.2026",
          "otb_post": "Начальник ОТБ", "otb_name": "Петров И.С.", "is_temporary": False}
BADGE = {"tab_num": "01035", "park": "ОСП «Трамвайный парк № 8»", "role": "Водитель",
         "surname": "ИВАНОВ", "name": "ИВАН", "patronymic": "ИВАНОВИЧ",
         "phone": "", "issue_date": "08.09.2026", "valid_until": "08.09.2031",
         "photo_path": None}


class TestGeometry:
    def test_pass_size(self, template):
        assert R.render_pass(PASS, COMMON).size == (R.PASS_W, R.PASS_H)

    def test_badge_size(self, template):
        assert R.render_single_badge_image(BADGE).size == (R.CARD_W, R.CARD_H)

    def test_a4_sheet_size(self, template):
        img = R.render_pass(PASS, COMMON)
        assert R.build_pass_a4_sheet(img, img).size == (R.A4_W, R.A4_H)

    def test_a4_single_pass_leaves_bottom_empty(self, template):
        """Нечётный остаток печатается один раз, а не дублируется."""
        img = R.render_pass(PASS, COMMON)
        sheet = R.build_pass_a4_sheet(img, None)
        bottom = sheet.crop((0, R.A4_H // 2 + 200, R.A4_W, R.A4_H - 100))
        assert bottom.convert("L").getextrema()[0] > 240, "низ листа не пустой"

    def test_badge_grid_size(self, template):
        badge = R.render_single_badge_image(BADGE)
        assert R.build_badge_a4_grid([badge] * 9).size == (R.A4_W, R.A4_H)


class TestDeterminism:
    def test_pass_render_is_stable(self, template):
        a = R.render_pass(PASS, COMMON).tobytes()
        b = R.render_pass(PASS, COMMON).tobytes()
        assert a == b

    def test_badge_render_is_stable(self, template):
        assert (R.render_single_badge_image(BADGE).tobytes()
                == R.render_single_badge_image(BADGE).tobytes())


class TestBlankIsDrawnInCode:
    def test_no_external_template_needed(self, tmp_path, monkeypatch):
        """Бланк строится кодом: отсутствие template.png ничего не ломает."""
        from getpass_core import config
        monkeypatch.setattr(config, "TEMPLATE_FILE", str(tmp_path / "нет.png"))
        R.reset_template_cache()
        img = R.render_pass(PASS, COMMON)
        assert img.size == (R.PASS_W, R.PASS_H)
        assert R.template_exists() is True

    def test_blank_has_field_frames(self):
        """На пустом бланке должны быть рамки блоков и подписи полей."""
        from getpass_core.blank import BOX_PLATE, build_pass_blank
        blank = build_pass_blank()
        assert blank.size == (R.PASS_W, R.PASS_H)
        left, top, right, _bottom = BOX_PLATE
        mid_x = (left + right) // 2
        # верхняя граница блока госномера прорисована
        assert blank.getpixel((mid_x, top))[0] < 120

    def test_blank_is_cached_and_stable(self):
        from getpass_core.blank import build_pass_blank
        assert build_pass_blank().tobytes() == build_pass_blank().tobytes()

    def test_number_is_printed_next_to_title(self):
        """Заголовок «ПРОПУСК №» теперь печатается кодом вместе с номером."""
        from getpass_core.blank import build_pass_blank
        blank = build_pass_blank()
        filled = R.render_pass(PASS, COMMON)
        band_blank = blank.crop((820, 350, 1700, 420)).convert("L")
        band_filled = filled.crop((820, 350, 1700, 420)).convert("L")
        assert band_blank.getextrema()[0] > 200, "на пустом бланке заголовка быть не должно"
        assert band_filled.getextrema()[0] < 120, "заголовок с номером не напечатан"


LONG = "Заместитель начальника отдела транспортной безопасности Смирнов А.В."


def _column_bounds(spec):
    x, bounds = 140, {}
    for c in spec.columns:
        bounds[c.key] = (x, x + c.width)
        x += c.width
    return bounds


def _ink_right_of(page, border, width=300, y0=442, y1=524):
    return sum(1 for yy in range(y0, y1) for xx in range(border + 3, border + width)
               if page.getpixel((xx, yy))[0] < 190)


class TestRegistryOverflow:
    @pytest.mark.parametrize("spec,key,record", [
        (PASS_REGISTRY, "driver", {"driver": LONG}),
        (BADGE_REGISTRY, "role", {"role": LONG}),
        (BADGE_REGISTRY, "fio", {"fio": "ПЕТРОВ-ВОДОПЬЯНОВ-СЕРЕБРЯКОВ ПЁТР АЛЕКСАНДРОВИЧ"}),
    ])
    def test_long_text_stays_in_column(self, spec, key, record):
        page = next(build_registry_pages([record], spec, 1))
        _, right = _column_bounds(spec)[key]
        assert _ink_right_of(page, right) == 0

    def test_old_behaviour_did_overflow(self):
        """Контроль: прежняя логика действительно выходила за границу."""
        im = Image.new("RGB", (1400, 120), "white")
        d = ImageDraw.Draw(im)
        size, font = 32, get_echoes_font(32)
        while size > 16:
            f = get_echoes_font(size)
            if d.textbbox((0, 0), LONG, font=f)[2] <= 455:
                font = f
                break
            size -= 2
        d.text((20, 60), LONG, fill="#000", font=font, anchor="lm")
        leaked = sum(1 for yy in range(120) for xx in range(475, 1400)
                     if im.getpixel((xx, yy))[0] < 190)
        assert leaked > 0


def test_registry_paginates(template):
    records = [{"num": str(i), "plate": "А111АА78", "valid_until": "31.12.2030"}
               for i in range(50)]
    pages = list(build_registry_pages(records, PASS_REGISTRY, 50))
    assert len(pages) == 3          # 23 строки на лист
    assert all(p.size == (2480, 3508) for p in pages)
