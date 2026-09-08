"""Дизайн-система: токены брендбука и движок оформления."""
import pytest

from getpass_ui import tokens as T

tkinter = pytest.importorskip("tkinter")
import os  # noqa: E402

needs_display = pytest.mark.skipif(not os.environ.get("DISPLAY"),
                                   reason="нужен X-сервер")


class TestBrandPalette:
    def test_official_values(self):
        """Значения зафиксированы по брендбуку — менять только по гайдлайну."""
        assert T.BRAND["navy"] == "#24305E"     # C100 M90 Y35 K20
        assert T.BRAND["teal"] == "#009CBC"     # C100 M0 Y25 K0
        assert T.BRAND["red"] == "#E4032E"      # C0 M100 Y80 K0
        assert T.BRAND["yellow"] == "#FBBA00"
        assert T.BRAND["lime"] == "#AFCB37"
        assert T.BRAND["mint"] == "#8ACBC1"

    def test_transport_colours(self):
        """Брендбук закрепляет цвет за видом транспорта."""
        assert T.TRANSPORT["tram"] == T.BRAND["red"]
        assert T.TRANSPORT["trolleybus"] == T.BRAND["teal"]


class TestColourMath:
    def test_mix_endpoints(self):
        assert T.mix("#000000", "#FFFFFF", 0) == "#000000"
        assert T.mix("#000000", "#FFFFFF", 1) == "#FFFFFF"
        assert T.mix("#000000", "#FFFFFF", 0.5) == "#808080"

    def test_contrast_extremes(self):
        assert T.contrast_ratio("#FFFFFF", "#000000") == pytest.approx(21, abs=0.01)
        assert T.contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1, abs=0.01)

    def test_readable_on_picks_legible_ink(self):
        assert T.readable_on("#FFFFFF") == "#151A2B"
        assert T.readable_on("#000000") == "#FFFFFF"


@pytest.mark.parametrize("palette", [T.LIGHT, T.DARK], ids=["light", "dark"])
class TestContrastCompliance:
    """Текст обязан читаться: минимум WCAG AA — 4.5."""

    def test_body_text_on_surfaces(self, palette):
        for bg in (palette.surface, palette.surface_alt, palette.ground):
            assert T.contrast_ratio(palette.ink, bg) >= 4.5

    def test_muted_text_readable(self, palette):
        assert T.contrast_ratio(palette.ink_muted, palette.surface) >= 4.5

    def test_button_labels_readable(self, palette):
        assert T.contrast_ratio(palette.on_primary, palette.primary) >= 4.5
        label = palette.on_accent if palette.name == "dark" else "#FFFFFF"
        assert T.contrast_ratio(label, palette.accent_fill) >= 4.5

    def test_pure_brand_teal_is_kept_for_indicators(self, palette):
        """Чистый фирменный цвет не подменяется: он остаётся в accent."""
        if palette.name == "light":
            assert palette.accent == T.BRAND["teal"]
            # а заливка кнопок — затемнённая производная ради контраста
            assert palette.accent_fill != palette.accent


class TestScale:
    def test_spacing_is_multiple_of_four(self):
        assert all(v % 4 == 0 for v in T.SPACE)

    def test_type_roles_present(self):
        for role in ("display", "title", "heading", "body", "label", "caption", "data"):
            assert role in T.TYPE


@needs_display
class TestThemeEngine:
    @pytest.fixture
    def root(self):
        r = tkinter.Tk()
        yield r
        try:
            r.destroy()
        except Exception:
            pass

    @pytest.mark.parametrize("mode", ["light", "dark"])
    def test_builds_all_styles(self, root, mode):
        from getpass_ui.theme import Theme
        th = Theme(root, mode)
        names = ("Accent.TButton", "Primary.TButton", "Ghost.TButton",
                 "Danger.TButton", "Field.TEntry", "Field.TCombobox")
        for name in names:
            assert th.style.layout(name), f"стиль {name} не собран"

    def test_scaling_applies_to_spacing(self, root):
        from getpass_ui.theme import Theme
        base = Theme(root, "light", scale=1.0)
        assert base.sp(4) == 16
        big = Theme(root, "light", scale=1.5)
        assert big.sp(4) == 24

    def test_disabled_button_keeps_size_and_label(self, root):
        """Регрессия: недоступная кнопка не должна схлопываться."""
        from tkinter import ttk

        from getpass_ui.theme import Theme
        th = Theme(root, "light")
        frame = tkinter.Frame(root, bg=th.c("ground"))
        frame.pack()
        normal = ttk.Button(frame, text="Обычная", style="Ghost.TButton")
        normal.pack()
        off = ttk.Button(frame, text="Обычная", style="Ghost.TButton", state="disabled")
        off.pack()
        root.update()
        assert off.winfo_width() == normal.winfo_width()
        assert off.winfo_height() == normal.winfo_height()

    def test_second_theme_on_same_root_does_not_crash(self, root):
        """Элементы ttk создаются один раз на интерпретатор."""
        from getpass_ui.theme import Theme
        Theme(root, "light")
        Theme(root, "dark")          # не должно бросать TclError

    def test_card_fits_content(self, root):
        from getpass_ui.theme import Card, Theme
        th = Theme(root, "light")
        ground = tkinter.Frame(root, bg=th.c("ground"))
        ground.pack(fill="both", expand=True)
        card = Card(ground, th)
        card.pack(fill="x")
        for i in range(3):
            tkinter.Label(card.body, text=f"строка {i}", bg=th.c("surface")).pack()
        card.fit()
        root.update()
        assert card.winfo_reqheight() > card.body.winfo_reqheight()
