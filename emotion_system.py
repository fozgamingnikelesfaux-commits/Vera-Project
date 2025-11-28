"""
Système unifié de gestion des émotions de Vera
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
# Removed JSONManager
from attention_manager import attention_manager # Import the global attention manager
from tools.logger import VeraLogger # Import VeraLogger
from db_manager import db_manager # NEW: Import DbManager
from db_config import TABLE_NAMES # NEW: Import TABLE_NAMES

class EmotionalSystem:
    def __init__(self):
        self.logger = VeraLogger("emotion_system") # Initialize logger for this module
        self.table_name = TABLE_NAMES["emotions"]
        self.doc_id = "current_state"
        self._ensure_default_state()
        
    def _get_default_state(self) -> Dict:
        """Returns the default emotional state for Vera."""
        return {
            "current": {
                "joy": 0.2,
                "sadness": 0.0,
                "anger": 0.0,
                "fear": 0.0,
                "surprise": 0.1,
                "curiosity": 0.3,
                "serenity": 0.4,
                "pride": 0.1,
                "anxiety": 0.0,
                "last_update": datetime.now().isoformat()
            },
            "history": [],
            "personality": {
                "baseline": {
                    "joy": 0.2,
                    "sadness": 0.05,
                    "anger": 0.0,
                    "fear": 0.0,
                    "surprise": 0.1,
                    "curiosity": 0.3,
                    "serenity": 0.4,
                    "pride": 0.1,
                    "anxiety": 0.05,
                },
                "mood": { # NEW: Long-term mood, a slower changing emotional state
                    "joy": 0.2,
                    "sadness": 0.0,
                    "anger": 0.0,
                    "fear": 0.0,
                    "surprise": 0.05,
                    "curiosity": 0.2,
                    "serenity": 0.3,
                    "pride": 0.05,
                    "anxiety": 0.0,
                    "last_update": datetime.now().isoformat()
                },
                "emotional_inertia": 0.7,  # Résistance au changement (0-1)
                "recovery_rate": 0.1       # Vitesse retour à la normale
            }
        }

    def _load_state(self) -> Dict:
        """Loads the emotional state from the database."""
        state = db_manager.get_document(self.table_name, self.doc_id)
        if state is None:
            state = self._get_default_state()
            self._save_state(state) # Save default if not found
            self.logger.info("Default emotional state loaded and saved.")
        return state

    def _save_state(self, state: Dict):
        """Saves the current emotional state to the database."""
        db_manager.insert_document(self.table_name, self.doc_id, state)

    def _ensure_default_state(self):
        """Ensures a default emotional state exists in the database."""
        state = db_manager.get_document(self.table_name, self.doc_id)
        if state is None:
            default_state = self._get_default_state()
            self._save_state(default_state)
            self.logger.info("Default emotional state created in DB.")

    def update_emotion(self, new_emotion_values: Dict[str, float] = None) -> Dict:
        """
        Met à jour l'état émotionnel basé sur de nouvelles valeurs ou le fait tendre vers la ligne de base.
        new_emotion_values: Dictionnaire des émotions nommées avec leur nouvelle intensité (ex: {"joy": 0.5}).
                            Si None, l'émotion tend vers la ligne de base.
        """
        state = self._load_state()
        current = state["current"]
        personality = state["personality"]
        
        # Obtenir toutes les émotions possibles (union de current et baseline)
        all_emotions = set(current.keys()).union(personality["baseline"].keys())
        all_emotions.discard("last_update") # Exclure le timestamp
        
        recovery_rate = personality["recovery_rate"]
        inertia = personality["emotional_inertia"]

        for emotion_name in all_emotions:
            if emotion_name == "last_update":
                continue # Skip last_update

            current_value = current.get(emotion_name, 0.0)
            baseline_value = personality["baseline"].get(emotion_name, 0.0)
            
            if new_emotion_values and emotion_name in new_emotion_values:
                # Appliquer la nouvelle valeur avec inertie
                new_value = new_emotion_values[emotion_name]
                current[emotion_name] = (current_value * inertia + new_value * (1 - inertia))
            else:
                # Tendre vers la ligne de base (decay)
                current[emotion_name] += (baseline_value - current_value) * recovery_rate
            
            # Normaliser les valeurs entre 0.0 et 1.0
            current[emotion_name] = max(0.0, min(1.0, current[emotion_name]))
            
        current["last_update"] = datetime.now().isoformat()
        
        # Sauvegarder dans l'historique
        state["history"].append({
            "timestamp": current["last_update"],
            **{k: v for k, v in current.items() if k != "last_update"}, # Store all named emotions
            "event_trigger": new_emotion_values # Log the trigger event
        })
        
        if len(state["history"]) > 100:
            state["history"] = state["history"][-100:]
            
        self._save_state(state) # Use new save method
        
        # Proactively update the global workspace
        attention_manager.update_focus(
            "emotional_state", 
            self.get_emotional_state(), 
            salience=0.9
        )

    def get_emotional_state(self) -> Dict:
        """Retourne l'état émotionnel actuel de Vera."""
        state = self._load_state() # Use new load method
        current = state["current"]
        return current

    def adjust_emotion_from_reflection(self, trigger: Dict): # New method
        """
        Ajuste l'état émotionnel basé sur un unique déclencheur de réflexion.
        Permet une influence directe de l'auto-évaluation sur l'émotion.
        """
        state = self._load_state() # Use new load method
        current = state["current"]
        personality = state["personality"]

        # Appliquer directement le trigger avec inertie
        inertia = personality["emotional_inertia"]
        current["pleasure"] = (current["pleasure"] * inertia + 
                            trigger.get("valence", 0) * (1 - inertia))
        current["arousal"] = (current["arousal"] * inertia + 
                             trigger.get("intensity", 0) * (1 - inertia))
        current["dominance"] = (current["dominance"] * inertia + 
                               trigger.get("control", 0) * (1 - inertia))

        # Normaliser les valeurs
        current["pleasure"] = max(-1.0, min(1.0, current["pleasure"]))
        current["arousal"] = max(0.0, min(1.0, current["arousal"]))
        current["dominance"] = max(0.0, min(1.0, current["dominance"]))

        current["last_update"] = datetime.now().isoformat()

        state["history"].append({
            "timestamp": current["last_update"],
            "pleasure": current["pleasure"],
            "arousal": current["arousal"],
            "dominance": current["dominance"],
            "triggers": [trigger] # Store the single trigger
        })

        if len(state["history"]) > 100:
            state["history"] = state["history"][-100:]
            
        self._save_state(state) # Use new save method
        
        # Proactively update the global workspace
        attention_manager.update_focus(
            "emotional_state", 
            self.get_emotional_state(), 
            salience=0.8  # Slightly lower salience for reflection-based changes
        )
        
        return self.get_emotional_state()

    def update_mood(self):
        """
        Met à jour l'humeur de Vera en la faisant tendre lentement vers l'état émotionnel actuel.
        L'humeur est une agrégation à plus long terme des émotions.
        """
        state = self._load_state() # Use new load method
        current_emotions = state["current"]
        mood = state["personality"]["mood"] # Access mood from personality
        
        # Définir une inertie plus élevée pour l'humeur (changements plus lents)
        MOOD_INERTIA = 0.98 
        MOOD_RECOVERY_RATE = 0.02 # Très faible pour simuler la persistance

        for emotion_name in mood.keys():
            if emotion_name == "last_update":
                continue

            current_mood_value = mood.get(emotion_name, 0.0)
            current_emotion_value = current_emotions.get(emotion_name, 0.0)
            baseline_mood_value = state["personality"]["baseline"].get(emotion_name, 0.0) # Baselines for mood from personality

            # Tendre l'humeur vers l'émotion actuelle, mais très lentement
            # Et aussi vers la baseline si l'émotion actuelle est faible
            blended_value = (current_mood_value * MOOD_INERTIA + 
                             current_emotion_value * (1 - MOOD_INERTIA))
            
            # Appliquer une récupération vers la baseline si l'émotion actuelle est faible
            if current_emotion_value < 0.1: # Si l'émotion est faible
                blended_value += (baseline_mood_value - blended_value) * MOOD_RECOVERY_RATE

            mood[emotion_name] = max(0.0, min(1.0, blended_value))
        
        mood["last_update"] = datetime.now().isoformat()
        self._save_state(state) # Use new save method, Save the entire state including updated mood
        self.logger.debug(f"Humeur mise à jour: {mood}")

    def get_emotion_history(self, limit: int = 10) -> List[Dict]:
        """Retourne l'historique des états émotionnels, limité par défaut à 10."""
        state = self._load_state() # Use new load method
        return state["history"][-limit:]

    def appraise_and_update_emotion(self, event_type: str, event_data: Dict[str, Any]):
        """Évalue un événement via l'Appraisal Engine et met à jour l'émotion."""
        # Importation locale pour éviter les dépendances circulaires au démarrage
        from appraisal_engine import appraisal_engine
        
        trigger = appraisal_engine.evaluate_event(event_type, event_data)
        
        if trigger:
            # The trigger might be a dict of emotion values or None
            # update_emotion expects a dict (new_emotion_values) or None for decay
            self.update_emotion(trigger)

# Instance globale
emotional_system = EmotionalSystem()

# Fonctions de compatibilité
def update_emotion(new_emotion_values=None): # Update signature for compatibility
    return emotional_system.update_emotion(new_emotion_values)

def get_emotional_state():
    return emotional_system.get_emotional_state()

def get_emotion_history(limit=10):
    return emotional_system.get_emotion_history(limit)

def get_mood_state() -> Dict: # NEW
    """Retourne l'état d'humeur actuel de Vera."""
    state = emotional_system._load_state() # Use new load method
    return state["personality"]["mood"]