from PySide6.QtCore import qVersion


def test_qt_runtime_is_supported_611_line():
    major, minor, *_ = (int(part) for part in qVersion().split("."))
    assert (major, minor) == (6, 11)
