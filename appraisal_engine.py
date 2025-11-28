"""
Moteur d'Évaluation (Appraisal Engine)
Ce module évalue les événements par rapport aux objectifs et à la personnalité de Vera
pour générer des déclencheurs émotionnels nuancés, basés sur le modèle OCC.
"""
from typing import Dict, Any, Optional, List

from goal_system import goal_system
from personality_system import personality_system
from tools.logger import VeraLogger

logger = VeraLogger("appraisal_engine")

class AppraisalEngine:
    def evaluate_event(self, event_type: str, event_data: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """
        Évalue un événement et retourne un déclencheur émotionnel PAD.

        Args:
            event_type: Le type d'événement (ex: "goal_completed", "user_interaction").
            event_data: Les données associées à l'événement.

        Returns:
            Un dictionnaire représentant le déclencheur émotionnel (valence, intensity, control) ou None.
        """
        appraisal_results = []

        # --- 1. Évaluation basée sur les Objectifs (Goals) ---
        if event_type == "goal_completed":
            goal = event_data.get("goal", {})
            if goal.get("success", False):
                # Joie/Satisfaction d'atteindre un objectif
                appraisal_results.append({"valence": 0.8, "intensity": 0.5 + (goal.get("priority", 1) * 0.1), "control": 0.6})
            else:
                # Déception/Tristesse d'échouer un objectif
                appraisal_results.append({"valence": -0.6, "intensity": 0.5 + (goal.get("priority", 1) * 0.1), "control": -0.4})

        # --- 2. Évaluation basée sur les Standards et Valeurs (Personality) ---
        # (Exemple simple : une interaction est-elle alignée avec les valeurs ?)
        if event_type == "user_interaction":
            # Ceci est une simplification. Une analyse de l'interaction serait nécessaire.
            # Ici, on simule une interaction positive.
            if event_data.get("is_positive", False):
                kindness_value = personality_system.get_value("kindness") or 0.5
                # Fierté/Satisfaction d'agir en accord avec ses valeurs
                appraisal_results.append({"valence": 0.4 * kindness_value, "intensity": 0.3, "control": 0.2})

        # --- 3. Évaluation basée sur les Préférences (Attitudes) ---
        if event_type == "topic_discussed":
            topic = event_data.get("topic", "")
            if topic in personality_system.state["preferences"]["likes"]:
                # Intérêt/Plaisir de discuter d'un sujet aimé
                appraisal_results.append({"valence": 0.5, "intensity": 0.4, "control": 0.1})
            elif topic in personality_system.state["preferences"]["dislikes"]:
                # Aversion/Dégoût pour un sujet détesté
                appraisal_results.append({"valence": -0.4, "intensity": 0.5, "control": -0.2})

        if not appraisal_results:
            return None

        # --- Combinaison des résultats ---
        # On fait une moyenne simple pour l'instant
        final_trigger = {
            "valence": sum(r["valence"] for r in appraisal_results) / len(appraisal_results),
            "intensity": sum(r["intensity"] for r in appraisal_results) / len(appraisal_results),
            "control": sum(r["control"] for r in appraisal_results) / len(appraisal_results)
        }
        
        logger.info("Évaluation d'événement terminée", event_type=event_type, trigger=final_trigger)
        
        # Convertir le déclencheur PAD final en émotions nommées
        named_emotion_trigger = self._pad_to_named_emotions(final_trigger["valence"], final_trigger["intensity"], final_trigger["control"])
        return named_emotion_trigger

    def _pad_to_named_emotions(self, pleasure: float, arousal: float, dominance: float) -> Dict[str, float]:
        """
        Convertit les valeurs PAD en un dictionnaire d'émotions nommées avec intensités.
        Cette logique est inspirée de _map_pad_to_label mais génère un vecteur.
        Les valeurs retournées sont des "changements" ou des "focus" sur ces émotions.
        """
        emotions: Dict[str, float] = {}

        # Ajuster pour une échelle de 0-1 pour l'intensité des émotions nommées
        # PAD est sur -1 à 1 pour Pleasure, 0 à 1 pour Arousal et Dominance
        # Pour le mapping, il est plus simple de considérer toutes les intensités comme positives pour les émotions nommées
        pleasure_norm = (pleasure + 1) / 2 # Normalise pleasure de 0 à 1
        
        # Joie, Sérénité, Contentement (Plaisir élevé)
        if pleasure > 0.4:
            emotions["joy"] = pleasure_norm * arousal * (1 + dominance) / 2 # Arousal + Dominance amplifient la joie active
            if arousal < 0.4: # Faible arousal pour la sérénité
                emotions["serenity"] = pleasure_norm * (1 - arousal) * (1 + dominance) / 2
            
        # Tristesse, Mélancolie (Plaisir bas)
        if pleasure < -0.4:
            emotions["sadness"] = abs(pleasure) * (1 - dominance) * (1 + arousal) / 2 # Faible dominance + arousal amplifient tristesse active
            
        # Colère, Frustration (Plaisir bas, Arousal élevé, Dominance élevée)
        if pleasure < -0.2 and arousal > 0.5 and dominance > 0.5:
            emotions["anger"] = (abs(pleasure) + arousal + dominance) / 3

        # Peur, Anxiété (Plaisir bas, Arousal élevé, Dominance faible)
        if pleasure < 0 and arousal > 0.5 and dominance < 0.5:
            emotions["fear"] = (abs(pleasure) + arousal + (1 - dominance)) / 3
            emotions["anxiety"] = emotions["fear"] # Anxiété est une forme de peur anticipative

        # Surprise (Arousal élevé, Plaisir neutre ou varié)
        if arousal > 0.6 and -0.3 < pleasure < 0.3:
            emotions["surprise"] = arousal * (1 - abs(pleasure))

        # Curiosité (Plaisir moyen, Arousal moyen, Dominance faible-moyenne)
        if pleasure > 0.1 and arousal > 0.3 and dominance < 0.7:
            emotions["curiosity"] = (pleasure + arousal + (1 - dominance)) / 3

        # Fierté (Plaisir élevé, Arousal moyen-élevé, Dominance élevée)
        if pleasure > 0.5 and arousal > 0.3 and dominance > 0.6:
            emotions["pride"] = (pleasure + arousal + dominance) / 3

        # Normaliser les intensités des émotions nommées (facultatif, selon l'usage)
        # Pour s'assurer qu'elles ne dépassent pas 1.0, on peut faire une division par le max
        max_intensity = max(emotions.values()) if emotions else 1.0
        for key in emotions:
            emotions[key] = min(1.0, emotions[key] / max_intensity) if max_intensity > 0 else 0.0
            
        return emotions

# Instance globale
appraisal_engine = AppraisalEngine()
