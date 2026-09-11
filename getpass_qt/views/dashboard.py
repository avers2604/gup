from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


class DashboardPage(QWidget):
    vehicle_requested = Signal()
    employee_requested = Signal()
    batch_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("Главная")
        title.setProperty("role", "heading")
        layout.addWidget(title)

        subtitle = QLabel("Выберите рабочий сценарий")
        subtitle.setProperty("role", "muted")
        layout.addWidget(subtitle)

        card = QFrame()
        card.setProperty("role", "card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(12)

        self.vehicle_button = QPushButton("Новый пропуск ТС")
        self.vehicle_button.setProperty("role", "primary")
        self.vehicle_button.clicked.connect(self.vehicle_requested.emit)
        card_layout.addWidget(self.vehicle_button)

        self.employee_button = QPushButton("Пропуск работника")
        self.employee_button.setProperty("role", "accent")
        self.employee_button.clicked.connect(self.employee_requested.emit)
        card_layout.addWidget(self.employee_button)

        self.batch_button = QPushButton("Массовая печать")
        self.batch_button.clicked.connect(self.batch_requested.emit)
        card_layout.addWidget(self.batch_button)

        layout.addWidget(card)
        layout.addStretch(1)
