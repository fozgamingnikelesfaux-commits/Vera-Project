import threading
from datetime import datetime, timedelta
import time
# Removed JSONManager
from tools.logger import VeraLogger # Import VeraLogger
from db_manager import db_manager # NEW: Import DbManager
from db_config import TABLE_NAMES # NEW: Import TABLE_NAMES
from uuid import uuid4 # NEW: For generating unique IDs

class TimeManager:
    def __init__(self):
        self.table_name = TABLE_NAMES["reminders"]
        db_manager._create_tables_if_not_exist() # Ensure table is created
        self.reminder_callbacks = []  # Pour notifier l'UI
        self.reminder_thread = threading.Thread(target=self._check_reminders, daemon=True)
        self.reminder_thread.start()
        self.logger = VeraLogger("time_manager") # Initialize logger for this module
        
    def _load_reminders(self) -> list[dict]:
        """Loads all reminders from the database."""
        return db_manager.get_all_documents(self.table_name, column_name="reminder_json")
        
    def _save_reminder(self, reminder: dict):
        """Saves (inserts or updates) a single reminder to the database."""
        db_manager.insert_document(self.table_name, reminder["id"], reminder, column_name="reminder_json")

    def _delete_reminder(self, reminder_id: str):
        """Deletes a single reminder from the database."""
        db_manager.delete_document(self.table_name, reminder_id)
            
    def add_reminder(self, description: str, target_date: datetime, user_id: str, importance: str = "normal") -> dict:
        """Ajouter un nouveau rappel"""
        reminder = {
            "id": str(uuid4()), # Generate a unique ID
            "description": description,
            "target_date": target_date.isoformat(),
            "user_id": user_id,
            "importance": importance,
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }
        self._save_reminder(reminder)
        self.logger.info("Rappel ajouté", reminder_id=reminder["id"], description=description)
        return reminder
        
    def get_upcoming_reminders(self, days: int = 7) -> list[dict]:
        """Obtenir les rappels à venir dans les X prochains jours"""
        reminders = self._load_reminders()
        now = datetime.now()
        future = now + timedelta(days=days)
        return [r for r in reminders 
                if r["status"] == "pending" 
                and now <= datetime.fromisoformat(r["target_date"]) <= future]
        
    def mark_reminder_done(self, reminder_id: str) -> bool:
        """Marquer un rappel comme effectué"""
        reminders = self._load_reminders()
        for r in reminders:
            if r["id"] == reminder_id:
                r["status"] = "done"
                r["completed_at"] = datetime.now().isoformat()
                self._save_reminder(r) # Save the updated reminder
                self.logger.info("Rappel marqué comme effectué", reminder_id=reminder_id)
                return True
        self.logger.warning("Rappel non trouvé pour marquer comme effectué", reminder_id=reminder_id)
        return False
        
    def register_callback(self, callback):
        """Enregistrer une fonction de rappel pour les notifications"""
        self.reminder_callbacks.append(callback)
        
    def _check_reminders(self):
        """Thread de vérification des rappels"""
        while True:
            reminders = self._load_reminders() # Load reminders for each check
            now = datetime.now()
            for reminder in reminders:
                if reminder.get("status") == "pending" and "target_date" in reminder:
                    try:
                        target = datetime.fromisoformat(reminder["target_date"])
                        if now >= target:
                            self._trigger_reminder(reminder)
                            reminder["status"] = "triggered" # Update status
                            self._save_reminder(reminder) # Save updated reminder status
                            self.logger.info("Rappel déclenché", reminder_id=reminder["id"])
                    except Exception as e:
                        self.logger.error(f"Erreur de vérification de rappel: {e}", reminder_id=reminder.get("id"))
            time.sleep(60)  # Vérifier chaque minute
            
    def _trigger_reminder(self, reminder: dict):
        """Déclencher les callbacks pour un rappel"""
        for callback in self.reminder_callbacks:
            try:
                callback(reminder)
            except Exception as e:
                self.logger.error(f"Erreur lors du callback de rappel: {e}", reminder_id=reminder.get("id"))

    def get_current_datetime_str(self) -> str:
        """Retourne la date et l'heure actuelles sous forme de chaîne de caractères formatée."""
        now = datetime.now()
        day = now.day
        month_names = [
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre"
        ]
        month_name = month_names[now.month - 1]
        year = now.year
        hour = now.hour
        minute = f"{now.minute:02d}"
        day_names = [
            "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"
        ]
        day_name = day_names[now.weekday()]
        
        return f"Nous sommes le {day_name} {day} {month_name} {year}, et il est {hour}h{minute}."

# Instance globale
time_manager = TimeManager()