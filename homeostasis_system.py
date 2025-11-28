"""
Système d'Homéostasie Virtuelle de Vera

Ce module simule les "besoins" internes de Vera (curiosité, interaction sociale, etc.).
Chaque besoin a une valeur qui décroît avec le temps, créant une "tension" lorsque
la valeur sort d'une plage optimale. Cette tension est utilisée par le meta_engine
pour motiver des actions proactives visant à "remplir" le besoin et à retrouver l'équilibre.
"""

from datetime import datetime, timedelta
from typing import Dict, List
from tools.logger import VeraLogger
from db_manager import db_manager # Import DbManager
from db_config import TABLE_NAMES # Import TABLE_NAMES

class HomeostasisSystem:
    def __init__(self):
        self.logger = VeraLogger("homeostasis_system")
        self.table_name = TABLE_NAMES["homeostasis"]
        self.doc_id = "current_state"
        self._ensure_default_state()

    def _get_default_state(self) -> Dict:
        """Returns the default state for the homeostasis system."""
        return {
            "needs": {
                "curiosity": {
                    "value": 0.7, # Valeur actuelle du besoin (0-1)
                    "optimal_range": [0.7, 0.9], # Plage où il n'y a pas de tension
                    "decay_rate": 0.02 # Quantité perdue à chaque 'update'
                },
                "social_interaction": {
                    "value": 0.7,
                    "optimal_range": [0.4, 1.0],
                    "decay_rate": 0.002
                },
                "cognitive_load": {
                    "value": 0.3, # Un besoin d'être "chargé" mais pas trop
                    "optimal_range": [0.1, 0.7], 
                    "decay_rate": 0.01 # Décroît vers le "sous-régime"
                },
                "security": { # Représente la sécurité du système, la confiance
                    "value": 0.9,
                    "optimal_range": [0.8, 1.0],
                    "decay_rate": 0.0001 # Décroît très lentement
                }
            },
            "last_update": datetime.now().isoformat()
        }

    def _load_state(self) -> Dict:
        """Loads the current state from the database."""
        state = db_manager.get_document(self.table_name, self.doc_id)
        if state is None:
            state = self._get_default_state()
            self._save_state(state) # Save default if not found
            self.logger.info("Default homeostasis state loaded and saved.")
        return state

    def _save_state(self, state: Dict):
        """Saves the current state to the database."""
        db_manager.insert_document(self.table_name, self.doc_id, state)

    def _ensure_default_state(self):
        """Ensures a default state exists in the database and applies desired updates."""
        state = db_manager.get_document(self.table_name, self.doc_id)
        default_state = self._get_default_state() # Get the latest default configuration
        
        if state is None:
            self._save_state(default_state)
            self.logger.info("Default homeostasis state created in DB.")
        else:
            # Check and update specific values that might have old configurations
            needs_changed = False
            
            # Check curiosity settings
            current_curiosity_settings = state["needs"].get("curiosity", {})
            default_curiosity_settings = default_state["needs"]["curiosity"]

            if current_curiosity_settings.get("optimal_range") != default_curiosity_settings["optimal_range"]:
                state["needs"]["curiosity"]["optimal_range"] = default_curiosity_settings["optimal_range"]
                self.logger.info(f"Updated curiosity optimal_range from {current_curiosity_settings.get('optimal_range')} to {default_curiosity_settings['optimal_range']}.")
                needs_changed = True
            
            if current_curiosity_settings.get("decay_rate") != default_curiosity_settings["decay_rate"]:
                state["needs"]["curiosity"]["decay_rate"] = default_curiosity_settings["decay_rate"]
                self.logger.info(f"Updated curiosity decay_rate from {current_curiosity_settings.get('decay_rate')} to {default_curiosity_settings['decay_rate']}.")
                needs_changed = True
            
            # Add any new needs that might be in the default but not in the loaded state
            for need_name, default_need_config in default_state["needs"].items():
                if need_name not in state["needs"]:
                    state["needs"][need_name] = default_need_config
                    self.logger.info(f"Added new homeostasis need: {need_name}.")
                    needs_changed = True

            if needs_changed:
                self._save_state(state)
                self.logger.info("Homeostasis state updated in DB with latest configurations.")

    def update(self):
        """Met à jour l'état de tous les besoins, en appliquant la dégradation."""
        state = self._load_state()
        now = datetime.now()
        
        for need_name, need_data in state["needs"].items():
            decay = need_data["decay_rate"]
            need_data["value"] = max(0.0, need_data["value"] - decay)

        state["last_update"] = now.isoformat()
        self._save_state(state)
        self.logger.debug(f"Besoins mis à jour après dégradation: {state['needs']}")
    
    def fulfill_need(self, need_name: str, amount: float):
        """Augmente la valeur d'un besoin spécifique."""
        if amount <= 0:
            return
            
        state = self._load_state()
        if need_name in state["needs"]:
            need = state["needs"][need_name]
            need["value"] = min(1.0, need["value"] + amount)
            self._save_state(state)
            self.logger.info(f"Besoin '{need_name}' rempli de {amount}. Nouvelle valeur: {need['value']:.2f}")
        else:
            self.logger.warning(f"Tentative de remplir un besoin inconnu: '{need_name}'")

    def get_needs(self) -> Dict:
        """Retourne l'état actuel de tous les besoins."""
        return self._load_state().get("needs", {})

    def get_tensions(self) -> Dict[str, float]:
        """
        Calcule et retourne les "tensions" actuelles.
        Une tension est une valeur positive qui représente à quel point un besoin
        est en dehors de sa plage optimale.
        """
        tensions = {}
        needs = self.get_needs()
        for name, data in needs.items():
            value = data["value"]
            low_bound, high_bound = data["optimal_range"]
            
            tension = 0.0
            if value < low_bound:
                tension = (low_bound - value) / low_bound if low_bound > 0 else low_bound - value
            elif value > high_bound:
                tension = (value - high_bound) / (1 - high_bound) if high_bound < 1 else value - high_bound
            
            if tension > 0:
                tensions[name] = max(0.0, min(1.0, tension)) # Clamp between 0 and 1
        
        if tensions:
            self.logger.debug(f"Tensions détectées: {tensions}")
            
        return tensions

# Instance globale pour un accès facile
homeostasis_system = HomeostasisSystem()
