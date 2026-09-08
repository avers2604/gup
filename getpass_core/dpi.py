"""Поддержка мониторов с высоким разрешением.

Без объявления DPI-осведомлённости Windows рисует окно в 96 dpi и потом
растягивает готовую картинку под масштаб экрана (125%, 150%, 200%).
Отсюда «мыльный», пиксельный интерфейс. Осведомлённое приложение получает
настоящие пиксели и рисует текст чётко.

Объявлять нужно ДО создания окна Tk — потом переключиться уже нельзя.
"""
from __future__ import annotations

import os

#: DPI, при котором масштаб равен 100%
BASE_DPI = 96.0

_awareness_result: str | None = None


def enable_dpi_awareness() -> str:
    """Объявить приложение DPI-осведомлённым. Вызывать до создания Tk."""
    global _awareness_result
    if _awareness_result is not None:
        return _awareness_result
    if os.name != "nt":
        _awareness_result = "не Windows"
        return _awareness_result
    import ctypes
    # Per-Monitor v2 — правильно ведёт себя при переносе окна между
    # мониторами с разным масштабом (Windows 10 1703 и новее)
    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(-4):
            _awareness_result = "per-monitor-v2"
            return _awareness_result
    except Exception:
        pass
    try:  # Windows 8.1+
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        _awareness_result = "per-monitor"
        return _awareness_result
    except Exception:
        pass
    try:  # Vista+
        ctypes.windll.user32.SetProcessDPIAware()
        _awareness_result = "system"
        return _awareness_result
    except Exception:
        _awareness_result = "недоступно"
    return _awareness_result


def screen_dpi(root) -> float:
    """Фактическое разрешение экрана в точках на дюйм."""
    if os.name == "nt":
        try:
            import ctypes
            hwnd = root.winfo_id()
            dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
            if dpi:
                return float(dpi)
        except Exception:
            pass
        try:
            import ctypes
            dc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX
            ctypes.windll.user32.ReleaseDC(0, dc)
            if dpi:
                return float(dpi)
        except Exception:
            pass
    try:
        # Tk сам умеет пересчитывать: winfo_fpixels('1i') = точек на дюйм
        return float(root.winfo_fpixels("1i"))
    except Exception:
        return BASE_DPI


def apply_scaling(root) -> float:
    """Согласовать масштаб Tk с экраном. Возвращает коэффициент (1.0 = 100%)."""
    dpi = screen_dpi(root)
    scale = dpi / BASE_DPI
    # разумные границы: за ними интерфейс перестаёт помещаться на экран
    scale = max(1.0, min(scale, 3.0))
    try:
        # Tk задаёт кегли в пунктах: 1 пункт = 1/72 дюйма
        root.tk.call("tk", "scaling", dpi / 72.0)
    except Exception:
        scale = 1.0
    return scale


def scaled(value: int, scale: float) -> int:
    return int(round(value * scale))


def scale_geometry(spec: str, scale: float) -> str:
    """Пересчитать строку вида «1500x920» под масштаб экрана."""
    try:
        width, _, height = spec.partition("x")
        return f"{scaled(int(width), scale)}x{scaled(int(height), scale)}"
    except Exception:
        return spec


def fit_to_screen(root, width: int, height: int, margin: int = 80) -> tuple[int, int]:
    """Ужать размеры под рабочую область экрана.

    Окно, которое выше экрана, уезжает нижним краем под панель задач вместе
    с кнопками — на ноутбуках это происходит почти всегда.
    """
    try:
        avail_w = root.winfo_screenwidth()
        avail_h = root.winfo_screenheight()
    except Exception:
        return width, height
    return min(width, max(320, avail_w - margin)), min(height, max(240, avail_h - margin))
