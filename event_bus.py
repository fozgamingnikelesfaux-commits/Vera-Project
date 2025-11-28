"""
event_bus.py
Ce module définit le bus d'événements central de Vera, basé sur une simple
file d'attente (queue), ainsi que les différentes classes d'événements
qui peuvent y transiter.
"""

import queue
from typing import Any, Dict, Optional

# Le bus d'événements central. C'est une simple file d'attente thread-safe.
# Tous les modules peuvent y poster des événements.
# L'orchestrateur de conscience est le principal consommateur.
VeraEventBus = queue.Queue()

# --- Définitions des Classes d'Événements ---
# Utiliser des classes permet d'avoir un code plus propre et plus lisible
# que de passer des dictionnaires avec des chaînes de caractères.

class BaseEvent:
    """Classe de base pour tous les événements."""
    def __repr__(self):
        return f"{self.__class__.__name__}"

class UserInputEvent(BaseEvent):
    """Événement déclenché par une nouvelle entrée de l'utilisateur."""
    def __init__(self, text: str, image_path: Optional[str] = None):
        self.text = text
        self.image_path = image_path
    
    def __repr__(self):
        return f"UserInputEvent(text='{self.text[:30]}...', image_path='{self.image_path}')"

class UserActivityEvent(BaseEvent):
    """Événement lié à l'activité de l'utilisateur (AFK/retour)."""
    def __init__(self, status: str): # status: "afk" or "returned"
        self.status = status

    def __repr__(self):
        return f"UserActivityEvent(status='{self.status}')"

class SystemMonitorEvent(BaseEvent):
    """
    Événement déclenché par le moniteur système lorsqu'un seuil est franchi.
    """
    def __init__(self, metric: str, value: Any, threshold: Any):
        self.metric = metric # e.g., "cpu_usage", "ram_usage"
        self.value = value
        self.threshold = threshold

    def __repr__(self):
        return f"SystemMonitorEvent(metric='{self.metric}', value={self.value})"

class InternalUrgeEvent(BaseEvent):
    """
    Événement représentant une "pulsion" ou un "désir" interne de Vera
    qui demande de l'attention (ex: curiosité, ennui).
    """
    def __init__(self, urge_type: str, description: str):
        self.urge_type = urge_type
        self.description = description

    def __repr__(self):
        return f"InternalUrgeEvent(urge_type='{self.urge_type}')"

class LLMTaskCompletedEvent(BaseEvent):
    """
    Événement déclenché lorsqu'une tâche du "slow path" (LLM) est terminée
    et que le résultat doit être traité par l'orchestrateur.
    """
    def __init__(self, original_task_type: str, result: Dict):
        self.original_task_type = original_task_type
        self.result = result

    def __repr__(self):
        return f"LLMTaskCompletedEvent(original_task_type='{self.original_task_type}')"

class VeraSpeakEvent(BaseEvent):
    """
    Événement pour faire parler Vera (envoyer un message à l'UI).
    """
    def __init__(self, message: str):
        self.message = message

    def __repr__(self):
        return f"VeraSpeakEvent(message='{self.message[:30]}...')"

class VeraResponseGeneratedEvent(BaseEvent):
    """
    Événement déclenché lorsque Vera a généré une réponse complète et qu'elle est prête à être parlée.
    Contient la réponse finale de Vera et l'input utilisateur qui l'a déclenchée.
    """
    def __init__(self, response_text: str, user_input: str, image_path: Optional[str] = None):
        self.response_text = response_text
        self.user_input = user_input
        self.image_path = image_path

    def __repr__(self):
        return f"VeraResponseGeneratedEvent(response_text='{self.response_text[:30]}...', user_input='{self.user_input[:30]}...')"

class HeartbeatEvent(BaseEvent):
    """Événement périodique pour s'assurer que la boucle de l'orchestrateur ne reste jamais bloquée."""
    pass
