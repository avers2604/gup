"""Обнаружение ресурсов: брендбук-шрифт, пиктограммы, каталог шрифтов."""
import os

from PIL import Image, ImageDraw

from getpass_core import config, fonts


def _reset():
    fonts._ECHOES_REGULAR = None
    fonts._ECHOES_BOLD = None
    fonts._ECHOES_FOUND = False
    fonts._DOT_ICON_PATH = None
    fonts._DOT_ICON_PATH_SEARCHED = False
    fonts._DOT_FONT_CACHE.clear()


class TestFontsDirectory:
    def test_accepts_misspelled_directory(self, tmp_path, monkeypatch):
        """Каталог, названный «fronts» вместо «fonts», тоже должен находиться."""
        (tmp_path / "fronts").mkdir()
        monkeypatch.setattr(config, "SCRIPT_DIR", str(tmp_path))
        assert config._resolve_fonts_dir() == str(tmp_path / "fronts")

    def test_prefers_correct_spelling(self, tmp_path, monkeypatch):
        (tmp_path / "fonts").mkdir()
        (tmp_path / "fronts").mkdir()
        monkeypatch.setattr(config, "SCRIPT_DIR", str(tmp_path))
        assert config._resolve_fonts_dir() == str(tmp_path / "fonts")

    def test_defaults_when_nothing_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "SCRIPT_DIR", str(tmp_path))
        assert config._resolve_fonts_dir().endswith("fonts")


class TestBrandFont:
    def test_recognises_moscow_sans(self, tmp_path, monkeypatch):
        d = tmp_path / "fonts"
        d.mkdir()
        (d / "MoscowSans-Regular.otf").write_bytes(b"")
        (d / "MoscowSansExtraBold.otf").write_bytes(b"")
        monkeypatch.setattr(config, "FONTS_DIR", str(d))
        monkeypatch.setattr(config, "SCRIPT_DIR", str(tmp_path / "нет"))
        _reset()
        fonts.find_echoes_font()
        assert fonts._ECHOES_REGULAR.endswith("MoscowSans-Regular.otf")
        assert fonts._ECHOES_BOLD.endswith("MoscowSansExtraBold.otf")
        _reset()

    def test_echoes_wins_over_moscow_sans(self, tmp_path, monkeypatch):
        d = tmp_path / "fonts"
        d.mkdir()
        (d / "MoscowSans-Regular.otf").write_bytes(b"")
        (d / "echoes sans.ttf").write_bytes(b"")
        monkeypatch.setattr(config, "FONTS_DIR", str(d))
        monkeypatch.setattr(config, "SCRIPT_DIR", str(tmp_path / "нет"))
        _reset()
        fonts.find_echoes_font()
        assert "echoes" in os.path.basename(fonts._ECHOES_REGULAR).lower()
        _reset()


class TestDotIcons:
    def test_raqm_constant_resolves_on_modern_pillow(self):
        """LAYOUT_RAQM убран в Pillow 10 — обращение к нему роняло реестры."""
        engine = fonts._raqm_layout()
        if fonts.raqm_ok():
            assert engine is not None

    def test_selection_is_deterministic(self, tmp_path, monkeypatch):
        d = tmp_path / "fonts"
        d.mkdir()
        for name in ("DoTIcons-Regular_2021-05-25-2.otf", "DoTIcons-Regular.otf",
                     "zz-doticons.otf"):
            (d / name).write_bytes(b"")
        monkeypatch.setattr(config, "FONTS_DIR", str(d))
        monkeypatch.setattr(config, "SCRIPT_DIR", str(tmp_path / "нет"))
        picked = []
        for _ in range(3):
            _reset()
            picked.append(os.path.basename(fonts.find_dot_icons_font()))
        assert len(set(picked)) == 1
        assert picked[0] == "DoTIcons-Regular.otf"
        _reset()

    def test_font_loads_without_error_when_present(self):
        """Регрессия: получение шрифта пиктограмм не должно бросать исключение."""
        assert fonts.get_dot_icons_font(48) is not None or fonts.find_dot_icons_font() is None


def test_icons_draw_when_font_available():
    if not fonts.find_dot_icons_font():
        return
    im = Image.new("RGB", (120, 120), "white")
    draw = ImageDraw.Draw(im)
    from getpass_core.render import draw_dot_icon
    assert draw_dot_icon(draw, "tram", 60, 60, "#C62828", size=80) is True
    ink = sum(1 for y in range(0, 120, 2) for x in range(0, 120, 2)
              if im.getpixel((x, y))[0] < 200)
    assert ink > 50, "пиктограмма не отрисовалась"
