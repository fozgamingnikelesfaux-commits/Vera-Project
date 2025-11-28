from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt5.QtCore import pyqtSignal, QThread
import time
from pathlib import Path
from journal_manager import journal_manager # Import the global instance

class JournalTab(QWidget):
    """Onglet pour afficher le journal d'observation de Vera."""
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_historical_entries() # Load existing entries on initialization

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        layout.addWidget(self.text_area)

    def append_entry(self, entry: str):
        """Ajoute une nouvelle entrée au journal."""
        self.text_area.append(entry)

    def load_historical_entries(self):
        """Charge les entrées existantes du journal.log."""
        try:
            if journal_manager.journal_file.exists():
                with open(journal_manager.journal_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.text_area.setText(content)
        except Exception as e:
            print(f"Error loading historical journal entries: {e}")
