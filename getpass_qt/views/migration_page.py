from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class MigrationPage(QWidget):
    def __init__(self, title: str, description: str, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(12)

        heading = QLabel(title)
        heading.setProperty("role", "heading")
        layout.addWidget(heading)

        body = QLabel(description)
        body.setWordWrap(True)
        body.setProperty("role", "muted")
        layout.addWidget(body)
        layout.addStretch(1)
