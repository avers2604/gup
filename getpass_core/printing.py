"""Печать через системный диспетчер печати Windows."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from .pdfwriter import write_pdf

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
DEFAULT_PRINTER = "По умолчанию"


def _ps(args, timeout):
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", *args],
        creationflags=_NO_WINDOW, capture_output=True, text=True, timeout=timeout,
    )


def get_available_printers() -> list[str]:
    """Список принтеров. Вызывать в фоне: PowerShell стартует до нескольких секунд."""
    try:
        cmd = ("Add-Type -AssemblyName System.Drawing; "
               "[System.Drawing.Printing.PrinterSettings]::InstalledPrinters")
        res = _ps([cmd], timeout=15)
        if res.returncode == 0:
            names = [p.strip() for p in res.stdout.split("\n") if p.strip()]
            return [DEFAULT_PRINTER] + names
    except Exception:
        pass
    return [DEFAULT_PRINTER]


def _ps_quote(value: str) -> str:
    return value.replace("'", "''")


def send_image_to_printer(pil_image, printer_name: str | None = None) -> tuple[bool, str]:
    """Отправить изображение на принтер.

    Возвращает (успех, текст ошибки). Временный файл удаляется всегда.
    """
    fd, temp_img = tempfile.mkstemp(prefix="get_print_", suffix=".png")
    os.close(fd)
    try:
        pil_image.save(temp_img, "PNG")
        is_landscape = "$true" if pil_image.width > pil_image.height else "$false"
        printer_cmd = ""
        if printer_name and printer_name != DEFAULT_PRINTER:
            printer_cmd = f"$doc.PrinterSettings.PrinterName = '{_ps_quote(printer_name)}'; "
        ps_cmd = (
            "$ErrorActionPreference = 'Stop'; "
            "Add-Type -AssemblyName System.Drawing; "
            "$doc = New-Object System.Drawing.Printing.PrintDocument; "
            f"{printer_cmd}"
            f"$doc.DefaultPageSettings.Landscape = {is_landscape}; "
            "$doc.OriginAtMargins = $false; "
            f"$img = [System.Drawing.Image]::FromFile('{_ps_quote(temp_img)}'); "
            "$doc.add_PrintPage({ "
            "  param($s, $e) "
            "  $e.Graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic; "
            "  $pb = $e.MarginBounds; "
            "  $ratio = $img.Width / $img.Height; "
            "  if ($pb.Width / $pb.Height -gt $ratio) { "
            "    $w = $pb.Height * $ratio; $h = $pb.Height; "
            "    $x = $pb.X + ($pb.Width - $w) / 2; $y = $pb.Y; "
            "  } else { "
            "    $w = $pb.Width; $h = $pb.Width / $ratio; "
            "    $x = $pb.X; $y = $pb.Y + ($pb.Height - $h) / 2; "
            "  } "
            "  $destRect = New-Object System.Drawing.RectangleF($x, $y, $w, $h); "
            "  $e.Graphics.DrawImage($img, $destRect); "
            "}); "
            "try { $doc.Print() } finally { $img.Dispose(); $doc.Dispose() }"
        )
        res = _ps([ps_cmd], timeout=60)
        if res.returncode == 0 and not (res.stderr or "").strip():
            return True, ""
        return False, (res.stderr or res.stdout or "").strip()[:400]
    except subprocess.TimeoutExpired:
        return False, "Принтер не ответил за 60 секунд."
    except Exception as exc:
        return False, str(exc)
    finally:
        try:
            os.remove(temp_img)
        except Exception:
            pass


def save_document(image, filepath: str) -> None:
    """Сохранить документ, проставив разрешение и для PDF, и для JPEG.

    Для JPEG параметр `resolution=` игнорируется Pillow, и файл уходил без DPI —
    печать такого файла давала произвольный масштаб.
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".jpg", ".jpeg"):
        image.save(filepath, "JPEG", quality=95, dpi=(300, 300))
    elif ext == ".png":
        image.save(filepath, "PNG", dpi=(300, 300))
    else:
        image.save(filepath, "PDF", resolution=300.0)


def save_pdf_pages(pages, filepath: str) -> int:
    """Многостраничный PDF из итератора страниц.

    Использует собственный потоковый писатель: Pillow при save_all собирает
    список всех страниц до кодирования, и 25 листов А4 300 dpi занимали
    около 840 МБ вне зависимости от того, передан список или генератор.
    """
    return write_pdf(pages, filepath, dpi=300)
