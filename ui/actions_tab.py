from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QPushButton
from PyQt5.QtCore import pyqtSignal, QTimer
import os

class ActionsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_file_path = os.path.join("logs", "actions.log")
        self.init_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_actions_log)
        self.timer.start(2000) # Refresh every 2 seconds

    def init_ui(self):
        layout = QVBoxLayout()

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        layout.addWidget(self.text_area)

        refresh_button = QPushButton("Rafraîchir")
        refresh_button.clicked.connect(self.load_actions_log)
        layout.addWidget(refresh_button)

        self.setLayout(layout)
        self.load_actions_log() # Initial load

    def load_actions_log(self):
        if os.path.exists(self.log_file_path):
            try:
                with open(self.log_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.text_area.setText(content)
                self.text_area.verticalScrollBar().setValue(self.text_area.verticalScrollBar().maximum())
            except Exception as e:
                self.text_area.setText(f"Erreur de lecture du fichier d'actions : {e}")
        else:
            self.text_area.setText("Le fichier d'actions (actions.log) n'existe pas encore.")
