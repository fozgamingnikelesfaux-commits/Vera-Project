from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QScrollArea
)
from PyQt5.QtCore import pyqtSignal

class LogsTab(QWidget):
    """Onglet d'affichage des logs"""
    on_refresh = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # Zone de texte scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.logs_label = QLabel()
        self.logs_label.setWordWrap(True)
        scroll.setWidget(self.logs_label)
        layout.addWidget(scroll)

        # Bouton rafraîchir
        refresh_btn = QPushButton("Rafraîchir logs")
        refresh_btn.clicked.connect(self._refresh)
        layout.addWidget(refresh_btn)

    def set_logs(self, text: str):
        """Met à jour le contenu des logs"""
        self.logs_label.setText(text)

    def _refresh(self):
        """Déclenche le rafraîchissement des logs"""
        self.on_refresh.emit()