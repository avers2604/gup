"""Потоковая запись многостраничного PDF.

Pillow при save_all собирает СПИСОК всех страниц до начала кодирования
(PdfImagePlugin строит `ims`), поэтому лист А4 300 dpi × N страниц целиком
лежит в памяти: 25 листов — около 840 МБ. Здесь страницы кодируются и
пишутся по одной, память не зависит от их числа.

Формат намеренно минимальный: каждая страница — одно изображение
DCTDecode (JPEG), ровно как это делает Pillow для RGB.
"""
from __future__ import annotations

import io
import zlib

_HEADER = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"


class _Writer:
    def __init__(self, fp):
        self.fp = fp
        self.pos = 0
        self.offsets: dict[int, int] = {}

    def write(self, data: bytes) -> None:
        self.fp.write(data)
        self.pos += len(data)

    def begin_object(self, num: int) -> None:
        self.offsets[num] = self.pos
        self.write(f"{num} 0 obj\n".encode("ascii"))

    def end_object(self) -> None:
        self.write(b"endobj\n")

    def stream_object(self, num: int, dict_body: str, payload: bytes) -> None:
        self.begin_object(num)
        self.write(f"<< {dict_body} /Length {len(payload)} >>\nstream\n".encode("ascii"))
        self.write(payload)
        self.write(b"\nendstream\n")
        self.end_object()


def _encode_page(image, quality: int):
    """Закодировать страницу. Возвращает (данные, фильтр, цветовое пространство)."""
    mode = image.mode
    if mode not in ("RGB", "L"):
        image = image.convert("RGB")
        mode = "RGB"
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=quality, optimize=False, progressive=False)
    colorspace = "/DeviceGray" if mode == "L" else "/DeviceRGB"
    return buf.getvalue(), "/DCTDecode", colorspace


def write_pdf(pages, filepath: str, dpi: int = 300, quality: int = 88) -> int:
    """Записать страницы в PDF по одной. Возвращает число страниц."""
    page_refs: list[int] = []
    next_num = 3                      # 1 — каталог, 2 — дерево страниц
    count = 0

    with open(filepath, "wb") as fp:
        w = _Writer(fp)
        w.write(_HEADER)

        w.begin_object(1)
        w.write(b"<< /Type /Catalog /Pages 2 0 R >>\n")
        w.end_object()

        for image in pages:
            img_num, content_num, page_num = next_num, next_num + 1, next_num + 2
            next_num += 3
            data, filt, colorspace = _encode_page(image, quality)
            width, height = image.size
            w_pt = width * 72.0 / dpi
            h_pt = height * 72.0 / dpi

            w.stream_object(
                img_num,
                f"/Type /XObject /Subtype /Image /Width {width} /Height {height} "
                f"/ColorSpace {colorspace} /BitsPerComponent 8 /Filter {filt}",
                data)

            content = f"q\n{w_pt:.4f} 0 0 {h_pt:.4f} 0 0 cm\n/Im0 Do\nQ\n".encode("ascii")
            packed = zlib.compress(content)
            w.stream_object(content_num, "/Filter /FlateDecode", packed)

            w.begin_object(page_num)
            w.write(
                f"<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {w_pt:.4f} {h_pt:.4f}] "
                f"/Resources << /XObject << /Im0 {img_num} 0 R >> "
                f"/ProcSet [/PDF /ImageC /ImageB] >> "
                f"/Contents {content_num} 0 R >>\n".encode("ascii"))
            w.end_object()

            page_refs.append(page_num)
            count += 1
            # страница больше не нужна: освобождаем буфер немедленно
            try:
                image.close()
            except Exception:
                pass
            del image, data

        if not count:
            raise ValueError("нет страниц для сохранения")

        kids = " ".join(f"{n} 0 R" for n in page_refs)
        w.begin_object(2)
        w.write(f"<< /Type /Pages /Count {count} /Kids [{kids}] >>\n".encode("ascii"))
        w.end_object()

        max_num = next_num - 1
        xref_pos = w.pos
        w.write(f"xref\n0 {max_num + 1}\n".encode("ascii"))
        w.write(b"0000000000 65535 f \n")
        for num in range(1, max_num + 1):
            w.write(f"{w.offsets[num]:010d} 00000 n \n".encode("ascii"))
        w.write(f"trailer\n<< /Size {max_num + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_pos}\n%%EOF\n".encode("ascii"))
    return count
