"""Масштабирование под мониторы с высоким разрешением."""
import pytest

from getpass_core import dpi


class TestScaling:
    @pytest.mark.parametrize("spec,scale,expected", [
        ("1500x920", 1.0, "1500x920"),
        ("1500x920", 1.25, "1875x1150"),
        ("1500x920", 1.5, "2250x1380"),
    ])
    def test_geometry_scales(self, spec, scale, expected):
        assert dpi.scale_geometry(spec, scale) == expected

    def test_geometry_survives_garbage(self):
        assert dpi.scale_geometry("не размер", 1.5) == "не размер"

    def test_scaled_rounds(self):
        assert dpi.scaled(420, 1.5) == 630
        assert dpi.scaled(331, 1.25) == 414


class TestAwareness:
    def test_reports_platform(self):
        assert dpi.enable_dpi_awareness() in {
            "не Windows", "per-monitor-v2", "per-monitor", "system", "недоступно"}

    def test_is_idempotent(self):
        assert dpi.enable_dpi_awareness() == dpi.enable_dpi_awareness()


class TestFitToScreen:
    def test_clamps_to_screen(self):
        class FakeRoot:
            def winfo_screenwidth(self):
                return 1366

            def winfo_screenheight(self):
                return 768

        w, h = dpi.fit_to_screen(FakeRoot(), 760, 920, margin=100)
        assert w == 760           # по ширине помещается
        assert h == 668           # по высоте ужато под экран ноутбука
        assert h < 768, "окно обязано влезать в экран целиком"

    def test_keeps_size_on_large_screen(self):
        class FakeRoot:
            def winfo_screenwidth(self):
                return 2560

            def winfo_screenheight(self):
                return 1440

        assert dpi.fit_to_screen(FakeRoot(), 760, 920) == (760, 920)

    def test_survives_missing_screen_info(self):
        class Broken:
            def winfo_screenwidth(self):
                raise RuntimeError

            def winfo_screenheight(self):
                raise RuntimeError

        assert dpi.fit_to_screen(Broken(), 760, 920) == (760, 920)
