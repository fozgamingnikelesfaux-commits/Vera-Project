import logging
from pathlib import Path
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal
from tools.logger import VeraLogger # Import VeraLogger

class JournalManager(QObject):
    """Gère le journal d'observation de Vera."""
    new_entry_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.log_dir = Path(__file__).parent / "logs"
        self.log_dir.mkdir(exist_ok=True)
        self.journal_file = self.log_dir / "journal.log"
        self.logger = VeraLogger("journal_manager") # Initialize logger for this module

    def add_entry(self, entry: str):
        """Ajoute une entrée au journal et émet un signal."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_entry = f"{timestamp} - {entry}"
        
        try:
            with open(self.journal_file, 'a', encoding='utf-8') as f:
                f.write(formatted_entry + '\n')
            self.new_entry_signal.emit(formatted_entry)
            self.logger.info("Entrée journal ajoutée", entry=entry)
        except Exception as e:
            self.logger.error(f"Erreur lors de l'écriture au journal: {e}", exc_info=True)

# Instance globale
journal_manager = JournalManager()
