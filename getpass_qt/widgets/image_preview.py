from __future__ import annotations

from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


_EMPTY_TEXT = "Предпросмотр появится после ввода данных"


class ImagePreview(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("VehiclePreview")
        self.setProperty("role", "preview")
        self._pil_image = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        self.image_label = QLabel(_EMPTY_TEXT)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setWordWrap(True)
        self.image_label.setMinimumSize(1, 1)
        layout.addWidget(self.image_label, 1)

    @property
    def has_image(self) -> bool:
        return self._pil_image is not None

    def set_pil_image(self, image) -> None:
        self._pil_image = image
        if image is None:
            self.image_label.clear()
            self.image_label.setText(_EMPTY_TEXT)
            return
        self.image_label.setText("")
        self._update_pixmap()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._pil_image is not None:
            self._update_pixmap()

    def _update_pixmap(self) -> None:
        rgba = self._pil_image.convert("RGBA")
        qimage = ImageQt(rgba).copy()
        pixmap = QPixmap.fromImage(qimage)
        target = self.image_label.size()
        if target.width() > 1 and target.height() > 1:
            pixmap = pixmap.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.image_label.setPixmap(pixmap)
