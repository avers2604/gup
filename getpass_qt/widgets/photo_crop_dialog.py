from __future__ import annotations

from PIL import ImageOps
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from getpass_core.crop import compute_crop_from_state
from getpass_design.tokens import BRAND, LIGHT

MIN_SCALE = 1.0
MAX_SCALE = 6.0
_DEFAULT_CANVAS = (560, 560)
_EXIF_ORIENTATION = 274


def _normalized_source(image):
    orientation = image.getexif().get(_EXIF_ORIENTATION, 1)
    source = ImageOps.exif_transpose(image) if orientation != 1 else image
    return source if source.mode == "RGB" else source.convert("RGB")


class _CropCanvas(QWidget):
    def __init__(self, dialog: "PhotoCropDialog") -> None:
        super().__init__(dialog)
        self._dialog = dialog
        self._last_pos: QPoint | None = None
        self.setMinimumSize(360, 360)
        self.setMouseTracking(True)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor(LIGHT.surface_alt))

        image = self._dialog.source_image
        current_scale = (
            self._dialog.state["base_scale"] * self._dialog.state["scale"]
        )
        width = max(1, round(image.width * current_scale))
        height = max(1, round(image.height * current_scale))
        qimage = ImageQt(image.convert("RGBA")).copy()
        pixmap = QPixmap.fromImage(qimage).scaled(
            width,
            height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        left = self.width() / 2 + self._dialog.state["offset_x"] - width / 2
        top = self.height() / 2 + self._dialog.state["offset_y"] - height / 2
        painter.drawPixmap(round(left), round(top), pixmap)

        self._draw_crop_overlay(painter)

    def _draw_crop_overlay(self, painter: QPainter) -> None:
        fx, fy, fw, fh = self._dialog.frame_box
        shade = QColor(LIGHT.ink)
        shade.setAlpha(115)
        painter.fillRect(QRectF(0, 0, self.width(), fy), shade)
        painter.fillRect(QRectF(0, fy + fh, self.width(), self.height() - fy - fh), shade)
        painter.fillRect(QRectF(0, fy, fx, fh), shade)
        painter.fillRect(QRectF(fx + fw, fy, self.width() - fx - fw, fh), shade)

        painter.setPen(QPen(QColor(BRAND["red"]), 3))
        painter.drawRect(QRectF(fx, fy, fw, fh))
        painter.setPen(QPen(QColor(LIGHT.on_primary), 1))
        for index in (1, 2):
            painter.drawLine(
                round(fx + fw * index / 3),
                fy,
                round(fx + fw * index / 3),
                fy + fh,
            )
            painter.drawLine(
                fx,
                round(fy + fh * index / 3),
                fx + fw,
                round(fy + fh * index / 3),
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._dialog._update_geometry(self.width(), self.height())

    def wheelEvent(self, event: QWheelEvent) -> None:
        self._dialog.zoom(1.12 if event.angleDelta().y() > 0 else 0.89)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_pos = event.position().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._last_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            current = event.position().toPoint()
            delta = current - self._last_pos
            self._last_pos = current
            self._dialog.pan_by(delta.x(), delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)


class PhotoCropDialog(QDialog):
    def __init__(self, image, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PhotoCropDialog")
        self.setWindowTitle("Кадрирование фотографии 3:4")
        self.resize(680, 760)

        self.source_image = _normalized_source(image)
        self.orig_w, self.orig_h = self.source_image.size
        self.canvas_size = _DEFAULT_CANVAS
        self.frame_box = self._frame_for_canvas(*self.canvas_size)
        self.state = {
            "scale": 1.0,
            "offset_x": 0.0,
            "offset_y": 0.0,
            "base_scale": self._base_scale(),
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hint = QLabel(
            "Колесо мыши — масштаб · ЛКМ и перетаскивание — положение фото"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.canvas = _CropCanvas(self)
        self.canvas.setObjectName("PhotoCropCanvas")
        layout.addWidget(self.canvas, 1)

        controls = QHBoxLayout()
        self.zoom_out_button = QPushButton("–")
        self.zoom_out_button.clicked.connect(lambda: self.zoom(0.85))
        controls.addWidget(self.zoom_out_button)

        self.reset_button = QPushButton("Сброс")
        self.reset_button.clicked.connect(self.reset)
        controls.addWidget(self.reset_button)

        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.clicked.connect(lambda: self.zoom(1.15))
        controls.addWidget(self.zoom_in_button)
        controls.addStretch(1)

        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        controls.addWidget(cancel_button)

        self.apply_button = QPushButton("Применить")
        self.apply_button.setObjectName("PhotoCropApplyButton")
        self.apply_button.setProperty("role", "accent")
        self.apply_button.clicked.connect(self.accept)
        controls.addWidget(self.apply_button)
        layout.addLayout(controls)

    def zoom(self, factor: float) -> None:
        value = float(self.state["scale"]) * float(factor)
        self.state["scale"] = max(MIN_SCALE, min(value, MAX_SCALE))
        self.canvas.update()

    def pan_by(self, dx: float, dy: float) -> None:
        self.state["offset_x"] += dx
        self.state["offset_y"] += dy
        self.canvas.update()

    def reset(self) -> None:
        self.state.update({"scale": 1.0, "offset_x": 0.0, "offset_y": 0.0})
        self.canvas.update()

    def cropped_image(self):
        return compute_crop_from_state(
            self.source_image,
            self.orig_w,
            self.orig_h,
            self.state,
            self.frame_box,
            self.canvas_size,
        )

    def _update_geometry(self, width: int, height: int) -> None:
        if width <= 1 or height <= 1:
            return
        old_frame = self.frame_box
        self.canvas_size = (width, height)
        self.frame_box = self._frame_for_canvas(width, height)
        if old_frame != self.frame_box:
            self.state["base_scale"] = self._base_scale()
        self.canvas.update()

    @staticmethod
    def _frame_for_canvas(width: int, height: int) -> tuple[int, int, int, int]:
        max_h_units = max(1, round(height * 0.82 / 4))
        max_w_units = max(1, round(width * 0.88 / 3))
        units = min(max_h_units, max_w_units)
        frame_w = units * 3
        frame_h = units * 4
        return (
            (width - frame_w) // 2,
            (height - frame_h) // 2,
            frame_w,
            frame_h,
        )

    def _base_scale(self) -> float:
        _, _, frame_w, frame_h = self.frame_box
        return max(
            frame_w / max(1, self.orig_w),
            frame_h / max(1, self.orig_h),
        )
