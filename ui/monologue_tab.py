from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton
from PyQt5.QtCore import pyqtSignal, Qt # Import Qt
import os # Added os for file path
from pathlib import Path # Added Path for file operations

class MonologueTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self._load_and_display_data() # Load existing data on init

    def init_ui(self):
        layout = QVBoxLayout()

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        layout.addWidget(self.text_area)

        # Optional: Add a clear button
        clear_button = QPushButton("Effacer")
        clear_button.clicked.connect(self.text_area.clear)
        layout.addWidget(clear_button)

        self.setLayout(layout)

    def _load_and_display_data(self):
        """Loads existing monologue data from logs/thoughts.log and displays it."""
        log_file_path = Path("logs") / "thoughts.log"
        if log_file_path.exists():
            try:
                with open(log_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.text_area.setText(content)
                    self.text_area.verticalScrollBar().setValue(self.text_area.verticalScrollBar().maximum())
            except Exception as e:
                self.text_area.setText(f"Erreur lors du chargement des logs : {e}")
        else:
            self.text_area.setText("Aucun log de monologue trouvé.")

    def append_thought(self, text: str):
        """Public slot to append a new thought to the text area."""
        # Ensure this is thread-safe by executing in the main UI thread context
        # (which pyqtSignal automatically does)
        self.text_area.append(f"{text}") # Add timestamp if needed, but log file already has it
        self.text_area.verticalScrollBar().setValue(self.text_area.verticalScrollBar().maximum())
