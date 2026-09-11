"""Поддержка мониторов с высоким разрешением."""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

BASE_DPI = 96.0
_awareness_result: str | None = None


def _try_per_monitor_v2() -> bool:
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
        user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
        return bool(user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)))
    except Exception:
        return False


def _try_per_monitor() -> bool:
    try:
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        shcore.SetProcessDpiAwareness.restype = ctypes.HRESULT
        return shcore.SetProcessDpiAwareness(2) == 0
    except Exception:
        return False


def _try_system_dpi() -> bool:
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware.argtypes = []
        user32.SetProcessDPIAware.restype = wintypes.BOOL
        return bool(user32.SetProcessDPIAware())
    except Exception:
        return False


def enable_dpi_awareness() -> str:
    global _awareness_result
    if _awareness_result is not None:
        return _awareness_result
    if os.name != "nt":
        _awareness_result = "не Windows"
        return _awareness_result

    strategies = (
        ("per-monitor-v2", _try_per_monitor_v2),
        ("per-monitor", _try_per_monitor),
        ("system", _try_system_dpi),
    )
    for result, strategy in strategies:
        if strategy():
            _awareness_result = result
            return _awareness_result
    _awareness_result = "недоступно"
    return _awareness_result


def screen_dpi(root) -> float:
    if os.name == "nt":
        try:
            hwnd = root.winfo_id()
            u32 = ctypes.windll.user32
            u32.GetDpiForWindow.argtypes = [wintypes.HWND]
            u32.GetDpiForWindow.restype = wintypes.UINT
            dpi = u32.GetDpiForWindow(hwnd)
            if dpi:
                return float(dpi)
        except Exception:
            pass
        try:
            u32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            u32.GetDC.argtypes = [wintypes.HWND]
            u32.GetDC.restype = wintypes.HDC
            gdi32.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
            gdi32.GetDeviceCaps.restype = ctypes.c_int
            u32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]

            dc = u32.GetDC(0)
            dpi = gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX
            u32.ReleaseDC(0, dc)
            if dpi:
                return float(dpi)
        except Exception:
            pass
    try:
        return float(root.winfo_fpixels("1i"))
    except Exception:
        return BASE_DPI


def apply_scaling(root) -> float:
    dpi = screen_dpi(root)
    scale = dpi / BASE_DPI
    scale = max(1.0, min(scale, 3.0))
    try:
        root.tk.call("tk", "scaling", dpi / 72.0)
    except Exception:
        scale = 1.0
    return scale


def scaled(value: int, scale: float) -> int:
    return int(round(value * scale))


def scale_geometry(spec: str, scale: float) -> str:
    try:
        width, _, height = spec.partition("x")
        return f"{scaled(int(width), scale)}x{scaled(int(height), scale)}"
    except Exception:
        return spec


def set_titlebar_theme(window, dark: bool) -> None:
    """Тёмный/светлый системный заголовок окна (Windows 10 20H1+/11).

    Без этого вызова рамка окна остаётся светлой независимо от темы
    содержимого: Windows 11 скругляет углы окна средствами самой системы,
    и за этими скруглениями виден светлый (системный) заголовок, даже
    когда всё содержимое окна оформлено в тёмной теме.
    """
    if os.name != "nt":
        return
    try:
        window.update_idletasks()
        u32 = ctypes.windll.user32
        u32.GetParent.argtypes = [wintypes.HWND]
        u32.GetParent.restype = wintypes.HWND
        hwnd = u32.GetParent(wintypes.HWND(window.winfo_id())) or window.winfo_id()
        dwmapi = ctypes.windll.dwmapi
        value = wintypes.BOOL(1 if dark else 0)
        # DWMWA_USE_IMMERSIVE_DARK_MODE: 20 — Windows 10 20H1+/11,
        # 19 — более ранние сборки Windows 10 с тем же API.
        for attr in (20, 19):
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd), wintypes.DWORD(attr),
                ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass


def fit_to_screen(root, width: int, height: int, margin: int = 80) -> tuple[int, int]:
    try:
        avail_w = root.winfo_screenwidth()
        avail_h = root.winfo_screenheight()
    except Exception:
        return width, height
    return min(width, max(320, avail_w - margin)), min(height, max(240, avail_h - margin))
