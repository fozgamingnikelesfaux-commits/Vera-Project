from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QScrollArea, QTextEdit # Added QTextEdit
)
from PyQt5.QtCore import pyqtSignal
import json # Added json for formatting introspection data
from meta_engine import metacognition # Import metacognition

class IntrospectionTab(QWidget):
    """Onglet d'affichage de l'introspection de Vera"""
    on_refresh = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.init_ui()
        self._load_and_display_data() # Load data on init

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # Zone de texte scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.introspection_text_edit = QTextEdit() # Changed from QLabel to QTextEdit
        self.introspection_text_edit.setReadOnly(True) # Make it read-only
        scroll.setWidget(self.introspection_text_edit)
        layout.addWidget(scroll)

        # Bouton rafraîchir
        refresh_btn = QPushButton("Rafraîchir introspection")
        refresh_btn.clicked.connect(self._refresh)
        layout.addWidget(refresh_btn)

    def set_introspection_data(self, text: str):
        """Met à jour le contenu de l'introspection"""
        self.introspection_text_edit.setText(text)

    def _load_and_display_data(self):
        """Charge les données d'introspection et les affiche."""
        introspection_state = metacognition.introspect()
        formatted_text = json.dumps(introspection_state, indent=2, ensure_ascii=False)
        self.set_introspection_data(formatted_text)

    def _refresh(self):
        """Déclenche le rafraîchissement de l'introspection et met à jour l'affichage."""
        self.on_refresh.emit()
        self._load_and_display_data()
