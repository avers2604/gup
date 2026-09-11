from PIL import Image
from PySide6.QtCore import Qt

from getpass_qt.widgets.image_preview import ImagePreview


def test_image_preview_accepts_pil_image_and_preserves_aspect_ratio(qtbot):
    preview = ImagePreview()
    qtbot.addWidget(preview)
    preview.resize(240, 240)
    preview.show()

    image = Image.new("RGB", (400, 200), "white")
    preview.set_pil_image(image)
    qtbot.wait(10)

    pixmap = preview.image_label.pixmap()
    assert preview.has_image is True
    assert pixmap is not None
    assert not pixmap.isNull()
    assert pixmap.width() <= preview.image_label.width()
    assert pixmap.height() <= preview.image_label.height()
    assert abs((pixmap.width() / pixmap.height()) - 2.0) < 0.05


def test_image_preview_rescales_from_original_on_resize(qtbot):
    preview = ImagePreview()
    qtbot.addWidget(preview)
    image = Image.new("RGB", (600, 300), "white")
    preview.resize(180, 140)
    preview.show()
    preview.set_pil_image(image)
    qtbot.wait(10)
    first_size = preview.image_label.pixmap().size()

    preview.resize(360, 280)
    qtbot.wait(10)
    second_size = preview.image_label.pixmap().size()

    assert second_size.width() >= first_size.width()
    assert second_size.height() >= first_size.height()
    assert image.size == (600, 300)


def test_image_preview_none_clears_pixmap_and_shows_empty_state(qtbot):
    preview = ImagePreview()
    qtbot.addWidget(preview)
    preview.set_pil_image(Image.new("RGB", (100, 50), "white"))

    preview.set_pil_image(None)

    pixmap = preview.image_label.pixmap()
    assert preview.has_image is False
    assert pixmap is None or pixmap.isNull()
    assert "предпросмотр" in preview.image_label.text().lower()
    assert preview.image_label.alignment() & Qt.AlignmentFlag.AlignCenter
