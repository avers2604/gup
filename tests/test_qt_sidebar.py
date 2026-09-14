from PySide6.QtWidgets import QLabel

from getpass_qt.widgets.sidebar import Sidebar


def test_sidebar_shows_brand_logo_image_when_asset_available(qapp):
    # Раньше в сайдбаре был просто текст "GET-Passes" без фирменного
    # знака — на светлом фоне QLabel это ещё и рисовало несовпадающий
    # прямоугольник поверх тёмно-синей панели (см. test_qt_theme.py).
    sidebar = Sidebar()
    brand = sidebar.layout().itemAt(0).widget()
    icon = brand.findChild(QLabel)
    assert icon is not None
    assert not icon.pixmap().isNull()
