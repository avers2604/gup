"""Поддержка мониторов с высоким разрешением."""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

BASE_DPI = 96.0
_awareness_result: str | None = None


def enable_dpi_awareness() -> str:
    global _awareness_result
    if _awareness_result is not None:
        return _awareness_result
    if os.name != "nt":
        _awareness_result = "не Windows"
        return _awareness_result

    # 1. Per-Monitor v2 (Windows 10 1703+)
    try:
        u32 = ctypes.windll.user32
        u32.SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
        u32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        if u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            _awareness_result = "per-monitor-v2"
            return _awareness_result
    except Exception:
        pass

    # 2. Per-Monitor (Windows 8.1+)
    try:
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        shcore.SetProcessDpiAwareness.restype = ctypes.HRESULT
        if shcore.SetProcessDpiAwareness(2) == 0:
            _awareness_result = "per-monitor"
            return _awareness_result
    except Exception:
        pass

    # 3. System DPI (Vista+)
    try:
        u32 = ctypes.windll.user32
        u32.SetProcessDPIAware.argtypes = []
        u32.SetProcessDPIAware.restype = wintypes.BOOL
        if u32.SetProcessDPIAware():
            _awareness_result = "system"
            return _awareness_result
    except Exception:
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


def fit_to_screen(root, width: int, height: int, margin: int = 80) -> tuple[int, int]:
    try:
        avail_w = root.winfo_screenwidth()
        avail_h = root.winfo_screenheight()
    except Exception:
        return width, height
    return min(width, max(320, avail_w - margin)), min(height, max(240, avail_h - margin))