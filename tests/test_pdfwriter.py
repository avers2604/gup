import os

import pytest
from PIL import Image

from getpass_core.pdfwriter import write_pdf

# pypdf нужен только для проверки корректности PDF и не входит в
# requirements.txt — без него тесты структуры пропускаются, а не падают
pypdf = pytest.importorskip("pypdf")


def pages(n, size=(2480, 3508)):
    for _ in range(n):
        yield Image.new("RGB", size, "white")


def test_produces_readable_pdf(tmp_path):
    out = tmp_path / "x.pdf"
    assert write_pdf(pages(4), str(out)) == 4
    reader = pypdf.PdfReader(str(out))
    assert len(reader.pages) == 4


def test_a4_page_geometry(tmp_path):
    out = tmp_path / "x.pdf"
    write_pdf(pages(1), str(out))
    box = pypdf.PdfReader(str(out)).pages[0].mediabox
    assert abs(float(box.width) - 595.3) < 1.5      # A4 в пунктах
    assert abs(float(box.height) - 841.9) < 1.5


def test_embeds_full_resolution_image(tmp_path):
    out = tmp_path / "x.pdf"
    write_pdf(pages(1), str(out))
    images = pypdf.PdfReader(str(out)).pages[0].images
    assert len(images) == 1
    assert images[0].image.size == (2480, 3508)


def test_grayscale_pages(tmp_path):
    out = tmp_path / "g.pdf"
    write_pdf((Image.new("L", (600, 800), 255) for _ in range(2)), str(out))
    assert len(pypdf.PdfReader(str(out)).pages) == 2


def test_empty_input_raises(tmp_path):
    with pytest.raises(ValueError):
        write_pdf(iter([]), str(tmp_path / "empty.pdf"))


def test_memory_flat_regardless_of_page_count(tmp_path):
    """Память не должна расти с числом страниц (лист А4 300dpi ~25 МБ)."""
    resource = pytest.importorskip("resource")

    def peak():
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

    write_pdf(pages(3), str(tmp_path / "warm.pdf"))
    before = peak()
    write_pdf(pages(40), str(tmp_path / "many.pdf"))
    growth = peak() - before
    assert growth < 200, f"память выросла на {growth:.0f} МБ — страницы копятся"
    assert os.path.getsize(tmp_path / "many.pdf") > 0
