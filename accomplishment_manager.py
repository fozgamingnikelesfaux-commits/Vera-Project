"""
Gestionnaire pour le Journal des Accomplissements de Vera.
Ce module permet d'enregistrer et de récupérer les événements positifs.
"""
from datetime import datetime
from typing import List, Dict
from tools.logger import VeraLogger
from db_manager import db_manager # NEW: Import DbManager
from db_config import TABLE_NAMES # NEW: Import TABLE_NAMES

logger = VeraLogger("accomplishments")

class AccomplishmentManager:
    def __init__(self):
        self.table_name = TABLE_NAMES["accomplishments"]
        # _ensure_default_structure will ensure the table exists
        db_manager._create_tables_if_not_exist() # Ensure table is created
        logger.info("AccomplishmentManager initialized.")

    def add_accomplishment(self, description: str, category: str, details: Dict = None):
        """
        Ajoute un nouvel accomplissement au journal.

        Args:
            description (str): Une description de l'accomplissement.
            category (str): La catégorie (e.g., 'goal_completed', 'positive_feedback').
            details (Dict, optional): Données supplémentaires.
        """
        accomplishment = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"), # Ensure unique ID
            "timestamp": datetime.now().isoformat(),
            "description": description,
            "category": category,
            "details": details or {}
        }

        db_manager.insert_document(self.table_name, accomplishment["id"], accomplishment, column_name="state_json")
        logger.info("Accomplishment added", description=description, category=category)

    def get_recent_accomplishments(self, limit: int = 5) -> List[Dict]:
        """Récupère les accomplissements les plus récents en les chargeant de la DB et en les triant."""
        all_accomplishments = db_manager.get_all_documents(self.table_name, column_name="state_json")
        
        # Sort by timestamp in descending order and then take the limit
        sorted_accomplishments = sorted(
            all_accomplishments, 
            key=lambda x: datetime.fromisoformat(x.get("timestamp", datetime.min.isoformat())), 
            reverse=True
        )
        return sorted_accomplishments[:limit]

# Instance globale
accomplishment_manager = AccomplishmentManager()
