"""Печать через системный диспетчер печати Windows."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from PIL import Image

from .pdfwriter import write_pdf
from .atomic import atomic_output

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
DEFAULT_PRINTER = "По умолчанию"


def _ps(args, timeout):
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", *args],
        creationflags=_NO_WINDOW, capture_output=True, text=True, timeout=timeout,
    )


def get_available_printers() -> list[str]:
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
            "  $pb = $e.PageBounds; "
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


def printer_can_duplex(printer_name: str | None = None) -> bool:
    printer_cmd = ""
    if printer_name and printer_name != DEFAULT_PRINTER:
        printer_cmd = f"$s.PrinterName = '{_ps_quote(printer_name)}'; "
    cmd = (
        "Add-Type -AssemblyName System.Drawing; "
        "$s = New-Object System.Drawing.Printing.PrinterSettings; "
        f"{printer_cmd}"
        "$s.CanDuplex"
    )
    try:
        res = _ps([cmd], timeout=15)
        return res.returncode == 0 and res.stdout.strip().lower() == "true"
    except Exception:
        return False


def _send_duplex_job(front_image, back_image, printer_name=None) -> tuple[bool, str]:
    fd1, temp_front = tempfile.mkstemp(prefix="get_print_front_", suffix=".png")
    os.close(fd1)
    fd2, temp_back = tempfile.mkstemp(prefix="get_print_back_", suffix=".png")
    os.close(fd2)
    try:
        front_image.save(temp_front, "PNG")
        back_image.save(temp_back, "PNG")
        is_landscape = front_image.width > front_image.height
        is_landscape_ps = "$true" if is_landscape else "$false"
        # Для Landscape переворот по короткому краю листа (Horizontal), чтобы не было "вверх ногами"
        duplex_mode = "Horizontal" if is_landscape else "Vertical"

        printer_cmd = ""
        if printer_name and printer_name != DEFAULT_PRINTER:
            printer_cmd = f"$doc.PrinterSettings.PrinterName = '{_ps_quote(printer_name)}'; "
        ps_cmd = (
            "$ErrorActionPreference = 'Stop'; "
            "Add-Type -AssemblyName System.Drawing; "
            "$doc = New-Object System.Drawing.Printing.PrintDocument; "
            f"{printer_cmd}"
            f"$doc.DefaultPageSettings.Landscape = {is_landscape_ps}; "
            "$doc.OriginAtMargins = $false; "
            f"$doc.PrinterSettings.Duplex = [System.Drawing.Printing.Duplex]::{duplex_mode}; "
            f"$imgs = @([System.Drawing.Image]::FromFile('{_ps_quote(temp_front)}'), "
            f"[System.Drawing.Image]::FromFile('{_ps_quote(temp_back)}')); "
            "$pageState = @{ Index = 0 }; "
            "$doc.add_PrintPage({ "
            "  param($s, $e) "
            "  $img = $imgs[$pageState.Index]; "
            "  $e.Graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic; "
            "  $pb = $e.PageBounds; "
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
            "  $pageState.Index += 1; "
            "  $e.HasMorePages = ($pageState.Index -lt $imgs.Count); "
            "}); "
            "try { $doc.Print() } finally { foreach ($i in $imgs) { $i.Dispose() }; $doc.Dispose() }"
        )
        res = _ps([ps_cmd], timeout=90)
        if res.returncode == 0 and not (res.stderr or "").strip():
            return True, ""
        return False, (res.stderr or res.stdout or "").strip()[:400]
    except subprocess.TimeoutExpired:
        return False, "Принтер не ответил за 90 секунд."
    except Exception as exc:
        return False, str(exc)
    finally:
        for path in (temp_front, temp_back):
            try:
                os.remove(path)
            except Exception:
                pass


def print_pass_two_sided(front_image, back_image, printer_name=None,
                         confirm_flip=None) -> tuple[bool, str]:
    if printer_can_duplex(printer_name):
        return _send_duplex_job(front_image, back_image, printer_name)
    ok, err = send_image_to_printer(front_image, printer_name)
    if not ok:
        return ok, err
    if confirm_flip is not None and not confirm_flip():
        return False, "Печать оборотной стороны отменена."
    return send_image_to_printer(back_image, printer_name)


def save_document(image: Image.Image, filepath: str) -> None:
    with atomic_output(filepath) as temporary:
        _save_document(image, temporary)


def _save_document(image, filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".jpg", ".jpeg"):
        # Предотвращение падения "cannot write mode RGBA as JPEG"
        if image.mode in ("RGBA", "LA", "P"):
            rgb_img = Image.new("RGB", image.size, (255, 255, 255))
            converted = image.convert("RGBA")
            rgb_img.paste(converted, mask=converted.getchannel("A"))
            save_img = rgb_img
        elif image.mode != "RGB":
            save_img = image.convert("RGB")
        else:
            save_img = image
        save_img.save(filepath, "JPEG", quality=95, dpi=(300, 300))
    elif ext == ".png":
        image.save(filepath, "PNG", dpi=(300, 300))
    else:
        image.save(filepath, "PDF", resolution=300.0)


def save_pdf_pages(pages, filepath: str) -> int:
    return write_pdf(pages, filepath, dpi=300)
