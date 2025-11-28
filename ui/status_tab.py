from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QScrollArea
)
from PyQt5.QtCore import pyqtSignal, QTimer

class StatusTab(QWidget):
    """Onglet d'affichage de l'état interne"""
    on_refresh = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.init_ui()
        # Ajout d'un QTimer pour le rafraîchissement automatique
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(3000) # Rafraîchit toutes les 3 secondes

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # Zone de texte scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        scroll.setWidget(self.status_label)
        layout.addWidget(scroll)

        # Bouton rafraîchir
        refresh_btn = QPushButton("Rafraîchir état")
        refresh_btn.clicked.connect(self._refresh)
        layout.addWidget(refresh_btn)

    def set_status(self, text: str):
        """Met à jour le contenu de l'état"""
        self.status_label.setText(text)

    def _refresh(self):
        """Déclenche le rafraîchissement de l'état"""
        self.on_refresh.emit()