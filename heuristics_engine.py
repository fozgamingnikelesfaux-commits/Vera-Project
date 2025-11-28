"""
Heuristics Engine
Ce module charge les règles distillées et les utilise pour prendre des décisions
rapides sans avoir besoin de faire appel au LLM.
"""
import json
from tools.logger import VeraLogger

class HeuristicsEngine:
    def __init__(self, rules_file="data/distilled_rules.json", confidence_threshold=0.7):
        self.logger = VeraLogger("heuristics_engine")
        self.rules = self._load_rules(rules_file)
        self.confidence_threshold = confidence_threshold
        self.logger.info(f"{len(self.rules)} règles chargées depuis '{rules_file}'.")

    def _load_rules(self, rules_file: str) -> list:
        """Charge les règles depuis le fichier JSON."""
        try:
            with open(rules_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning(f"Le fichier de règles '{rules_file}' n'a pas été trouvé. Le moteur d'heuristiques sera inactif.")
            return []
        except json.JSONDecodeError:
            self.logger.error(f"Erreur de décodage JSON dans '{rules_file}'. Le moteur d'heuristiques sera inactif.")
            return []

    def evaluate(self, thought: str) -> dict | None:
        """
        Évalue une pensée par rapport aux règles chargées.
        Retourne une décision si une règle de confiance est trouvée, sinon None.
        """
        if not self.rules:
            return None

        # Normaliser la pensée pour la comparaison
        normalized_thought = thought.lower()

        for rule in self.rules:
            if rule.get("confidence", 0) < self.confidence_threshold:
                continue # La règle n'est pas assez fiable

            trigger = rule.get("trigger", {})
            trigger_type = trigger.get("type")
            
            if trigger_type == "thought_contains_all_keywords":
                keywords = trigger.get("value", [])
                if not keywords:
                    continue
                
                # Vérifier si tous les mots-clés sont dans la pensée
                if all(keyword.lower() in normalized_thought for keyword in keywords):
                    self.logger.info(f"Règle heuristique déclenchée ! Pensée correspond aux mots-clés: {keywords}")
                    return rule.get("decision")
            
            # D'autres types de déclencheurs pourraient être ajoutés ici à l'avenir

        return None

# Instance globale pour un accès facile
heuristics_engine = HeuristicsEngine()
