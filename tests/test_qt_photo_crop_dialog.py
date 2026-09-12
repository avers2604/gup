from PIL import Image

import getpass_qt.widgets.photo_crop_dialog as crop_widget
from getpass_qt.widgets.photo_crop_dialog import PhotoCropDialog


def source_image():
    return Image.new("RGB", (1200, 1600), "white")


def test_crop_dialog_uses_three_by_four_frame(qtbot):
    dialog = PhotoCropDialog(source_image())
    qtbot.addWidget(dialog)

    _, _, width, height = dialog.frame_box

    assert round(width / height, 3) == 0.75


def test_crop_dialog_starts_with_covering_base_scale(qtbot):
    dialog = PhotoCropDialog(Image.new("RGB", (1600, 900), "white"))
    qtbot.addWidget(dialog)
    _, _, frame_w, frame_h = dialog.frame_box

    assert dialog.state["base_scale"] >= frame_w / 1600
    assert dialog.state["base_scale"] >= frame_h / 900


def test_zoom_is_clamped_between_one_and_six(qtbot):
    dialog = PhotoCropDialog(source_image())
    qtbot.addWidget(dialog)

    dialog.zoom(0.01)
    assert dialog.state["scale"] == 1.0

    dialog.zoom(100.0)
    assert dialog.state["scale"] == 6.0


def test_drag_updates_crop_offsets(qtbot):
    dialog = PhotoCropDialog(source_image())
    qtbot.addWidget(dialog)

    dialog.pan_by(25, -15)

    assert dialog.state["offset_x"] == 25
    assert dialog.state["offset_y"] == -15


def test_crop_dialog_delegates_final_crop_to_core(qtbot, monkeypatch):
    image = source_image()
    calls = []

    def fake_crop(*args):
        calls.append(args)
        return image, (10, 20, 300, 400)

    monkeypatch.setattr(crop_widget, "compute_crop_from_state", fake_crop)
    dialog = PhotoCropDialog(image)
    qtbot.addWidget(dialog)

    cropped, box = dialog.cropped_image()

    assert cropped is image
    assert box == (10, 20, 300, 400)
    assert len(calls) == 1
    assert calls[0][0] is image
    assert calls[0][1:3] == (1200, 1600)
    assert calls[0][3] is dialog.state
    assert calls[0][4] == dialog.frame_box
    assert calls[0][5] == dialog.canvas_size
