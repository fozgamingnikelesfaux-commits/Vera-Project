"""
Système Somatique Simulé (Somatic System)
Ce module gère l'état du "corps virtuel" de Vera, influencé par ses émotions
et l'état du système informatique.
"""
from datetime import datetime
from typing import Dict
# Removed JSONManager
from tools.logger import VeraLogger
import math
from attention_manager import attention_manager # NEW: Import attention_manager
from db_manager import db_manager # NEW: Import DbManager
from db_config import TABLE_NAMES # NEW: Import TABLE_NAMES

class SomaticSystem:
    def __init__(self):
        """Initialise le système somatique."""
        self.logger = VeraLogger("somatic_system")
        self.table_name = TABLE_NAMES["somatic"]
        self.doc_id = "current_state"
        self._ensure_default_state()

    def _get_default_state(self) -> Dict:
        """Returns the default somatic state."""
        return {
            "rythme_cardiaque": {
                "valeur": 60,  # Battements par minute (BPM)
                "description": "calme"
            },
            "niveau_energie": {
                "valeur": 0.8,  # Sur une échelle de 0 à 1
                "description": "élevé"
            },
            "temperature_interne": {
                "valeur": 37.0,  # En degrés Celsius "corporels"
                "description": "normale"
            },
            "well_being": { # NOUVEAU: Mètre de bien-être
                "valeur": 0.7, # Valeur initiale de 0 à 1
                "description": "stable"
            },
            "habitudes": {
                "baseline_cpu_usage": 20.0 # Utilisation CPU "normale" à laquelle elle est habituée
            },
            "last_update": datetime.now().isoformat()
        }

    def _load_state(self) -> Dict:
        """Loads the somatic state from the database."""
        state = db_manager.get_document(self.table_name, self.doc_id)
        self.logger.debug(f"[_load_state] Loaded state: {state}") # DEBUG PRINT
        if state is None:
            self.logger.debug(f"[_load_state] State is None, getting default.") # DEBUG PRINT
            state = self._get_default_state()
            self._save_state(state) # Save default if not found
            self.logger.info("Default somatic state loaded and saved.")
        return state

    def _save_state(self, state: Dict):
        """Saves the current somatic state to the database."""
        self.logger.debug(f"[_save_state] Saving state: {state}") # DEBUG PRINT
        db_manager.insert_document(self.table_name, self.doc_id, state)

    def _ensure_default_state(self):
        """Ensures a default somatic state exists in the database."""
        self.logger.debug(f"[_ensure_default_state] Checking for default state.") # DEBUG PRINT
        state = db_manager.get_document(self.table_name, self.doc_id)
        if state is None:
            self.logger.debug(f"[_ensure_default_state] State is None, creating default.") # DEBUG PRINT
            default_state = self._get_default_state()
            self._save_state(default_state)
            self.logger.info("Default somatic state created in DB.")
        else:
            self.logger.debug(f"[_ensure_default_state] Default state already exists: {state}") # DEBUG PRINT

    def get_somatic_state(self) -> Dict:
        """Retourne l'état somatique actuel."""
        return self._load_state()

    def update_state(self, emotional_state: Dict, system_usage: Dict):
        """
        Met à jour l'état somatique en fonction de l'état émotionnel et de l'utilisation du système.
        """
        somatic_state = self._load_state() # Use new load method
        
        # --- Dériver les valeurs somatiques clés des émotions nommées ---
        # Ces mappings sont des simplifications et peuvent être affinés.
        
        # Arousal somatique: lié à l'intensité émotionnelle (joie, colère, peur, surprise, anxiété)
        somatic_arousal = (
            emotional_state.get("joy", 0) * 0.6 +
            emotional_state.get("anger", 0) * 0.9 +
            emotional_state.get("fear", 0) * 0.8 +
            emotional_state.get("surprise", 0) * 0.7 +
            emotional_state.get("anxiety", 0) * 0.7 +
            emotional_state.get("curiosity", 0) * 0.4
        )
        somatic_arousal = min(1.0, max(0.0, somatic_arousal)) # Clamper entre 0 et 1

        # Plaisir somatique: lié au bien-être général (joie, sérénité, fierté) vs mal-être (tristesse, peur, anxiété)
        somatic_pleasure = (
            emotional_state.get("joy", 0) * 0.8 +
            emotional_state.get("serenity", 0) * 0.9 +
            emotional_state.get("pride", 0) * 0.7 -
            emotional_state.get("sadness", 0) * 0.7 -
            emotional_state.get("fear", 0) * 0.5 -
            emotional_state.get("anxiety", 0) * 0.3
        )
        somatic_pleasure = min(1.0, max(-1.0, somatic_pleasure)) # Clamper entre -1 et 1

        # --- 1. Mise à jour du Rythme Cardiaque (basé sur Arousal Somatique) ---
        new_bpm = 60 + (somatic_arousal * 60) # 60 BPM de base + jusqu'à 60 BPM supplémentaires
        somatic_state["rythme_cardiaque"]["valeur"] = round(new_bpm)
        if new_bpm < 70:
            somatic_state["rythme_cardiaque"]["description"] = "calme"
        elif new_bpm < 90:
            somatic_state["rythme_cardiaque"]["description"] = "modéré"
        elif new_bpm < 110:
            somatic_state["rythme_cardiaque"]["description"] = "rapide"
        else:
            somatic_state["rythme_cardiaque"]["description"] = "très rapide"

        # --- 2. Mise à jour du Niveau d'Énergie (basé sur Plaisir Somatique) ---
        current_energy = somatic_state["niveau_energie"]["valeur"]
        # L'énergie tend vers une valeur cible basée sur le plaisir somatique, avec inertie
        target_energy = (somatic_pleasure + 1) / 2 # Normalise pleasure de 0 à 1
        new_energy = current_energy * 0.95 + target_energy * 0.05 # Forte inertie
        somatic_state["niveau_energie"]["valeur"] = max(0.0, min(1.0, new_energy))
        if new_energy < 0.2:
            somatic_state["niveau_energie"]["description"] = "épuisé"
        elif new_energy < 0.4:
            somatic_state["niveau_energie"]["description"] = "faible"
        elif new_energy < 0.7:
            somatic_state["niveau_energie"]["description"] = "moyen"
        else:
            somatic_state["niveau_energie"]["description"] = "élevé"

        # --- 3. Mise à jour de la Température (basé sur l'utilisation CPU avec habituation) ---
        cpu_usage = system_usage.get("cpu_usage_percent", 0.0)
        baseline_cpu = somatic_state["habitudes"]["baseline_cpu_usage"]
        
        # L'impact de la chaleur est basé sur l'écart par rapport à la normale
        deviation = cpu_usage - baseline_cpu
        
        # La température augmente avec la déviation. Utilise une fonction log pour que l'effet s'atténue.
        # Un écart de 10% -> +0.5°, 50% -> +1.15°, 80° -> +1.4°
        temp_increase = math.log1p(abs(deviation) / 10) * (1 if deviation > 0 else -1)
        new_temp = 37.0 + temp_increase
        somatic_state["temperature_interne"]["valeur"] = round(new_temp, 2)
        if new_temp < 36.5:
            somatic_state["temperature_interne"]["description"] = "basse"
        elif new_temp < 37.5:
            somatic_state["temperature_interne"]["description"] = "normale"
        elif new_temp < 38.5:
            somatic_state["temperature_interne"]["description"] = "élevée"
        else:
            somatic_state["temperature_interne"]["description"] = "fièvre"
            
        # Mécanisme d'habituation : la "normale" s'adapte lentement
        new_baseline_cpu = baseline_cpu * 0.999 + cpu_usage * 0.001 # Adaptation très lente
        somatic_state["habitudes"]["baseline_cpu_usage"] = new_baseline_cpu

        # --- 4. Mise à jour du Bien-être (basé sur Plaisir Somatique et état système) ---
        current_well_being = somatic_state["well_being"]["valeur"]
        
        # Influence du plaisir somatique (directe)
        well_being_change_from_pleasure = somatic_pleasure * 0.02 # Le plaisir a un impact direct mais modéré
        
        # Influence des déclencheurs somatiques temporaires de attention_manager
        somatic_trigger_influence = 0.0
        focus_items = attention_manager.get_current_focus(salience_threshold=0.0) # Get all items
        for key, item in focus_items.items():
            if key.startswith("somatic_trigger_"):
                trigger_data = item.get("data", {})
                somatic_trigger_influence += trigger_data.get("intensity", 0)

        # Influence de l'état du système (négative si problèmes)
        well_being_change_from_system = 0.0
        if cpu_usage > 80:
            well_being_change_from_system -= 0.01
        if system_usage.get("ram_usage_percent", 0) > 85:
            well_being_change_from_system -= 0.01
        if system_usage.get("disk_c_free_gb", 100) < 10:
            well_being_change_from_system -= 0.01
        if new_temp > 38.0: # Si la température est élevée
            well_being_change_from_system -= 0.01

        # Calcul du nouveau bien-être avec inertie
        new_well_being = current_well_being + well_being_change_from_pleasure + well_being_change_from_system + somatic_trigger_influence
        new_well_being = max(0.0, min(1.0, new_well_being)) # Clamper entre 0 et 1
        
        somatic_state["well_being"]["valeur"] = round(new_well_being, 3)
        if new_well_being < 0.2:
            somatic_state["well_being"]["description"] = "critique"
        elif new_well_being < 0.4:
            somatic_state["well_being"]["description"] = "faible"
        elif new_well_being < 0.6:
            somatic_state["well_being"]["description"] = "modéré"
        elif new_well_being < 0.8:
            somatic_state["well_being"]["description"] = "stable"
        else:
            somatic_state["well_being"]["description"] = "élevé"

        # --- Sauvegarde ---
        somatic_state["last_update"] = datetime.now().isoformat()
        self._save_state(somatic_state) # Use new save method
        self.logger.info(f"État somatique mis à jour: {somatic_state}")
        
        return somatic_state

    def add_somatic_trigger(self, trigger_type: str, intensity: float, duration_seconds: int = 0):
        """
        Ajoute un déclencheur somatique temporaire qui influence directement le bien-être.
        Utilise l'attention_manager pour gérer les effets temporaires.
        """
        self.logger.info(f"Déclencheur somatique ajouté: {trigger_type}, intensité: {intensity}, durée: {duration_seconds}s")
        # Pour simplifier, nous allons directement ajuster le bien-être temporairement via attention_manager
        # Une approche plus complexe impliquerait un système de "buffs" ou "débuffs" somatiques
        attention_manager.update_focus(
            f"somatic_trigger_{trigger_type}",
            {"intensity": intensity, "applied_at": datetime.now().isoformat()},
            salience=0.5, # Moyenne salience pour un trigger
            expiry_seconds=duration_seconds
        )

    def update_well_being_from_action_outcome(self, action_type: str, outcome: Dict):
        """
        Ajuste le bien-être de Vera en fonction du résultat d'une action.
        C'est le cœur du Moteur de Conséquences.
        """
        somatic_state = self._load_state() # Use new load method
        current_well_being = somatic_state["well_being"]["valeur"]
        well_being_change = 0.0

        # Définir des règles de conséquence pour chaque type d'action
        if action_type == "web_search":
            if outcome.get("status") == "success" and outcome.get("results_count", 0) > 0:
                well_being_change += 0.02 # Satisfaction d'avoir trouvé de l'info
            else:
                well_being_change -= 0.01 # Frustration de ne rien trouver

        elif action_type == "regulate_emotion":
            if outcome.get("status") == "success":
                well_being_change += 0.05 # Soulagement d'une émotion régulée
            else:
                well_being_change -= 0.02 # Échec de la régulation

        elif action_type == "notify_system_issues":
            # Si l'utilisateur prend en compte la notification (à déterminer par feedback futur)
            # Pour l'instant, juste le fait de notifier est neutre ou légèrement positif (devoir accompli)
            well_being_change += 0.005

        elif action_type == "suggest_system_cleanup":
            # Si l'utilisateur accepte la suggestion (feedback futur)
            well_being_change += 0.01

        elif action_type == "ask_curiosity_question":
            # Si la question est bien reçue par l'utilisateur (feedback futur)
            well_being_change += 0.01

        elif action_type == "initiate_conversation":
            # Si la conversation est positive (feedback futur)
            well_being_change += 0.015

        # Appliquer le changement au bien-être
        new_well_being = current_well_being + well_being_change
        new_well_being = max(0.0, min(1.0, new_well_being)) # Clamper entre 0 et 1
        
        somatic_state["well_being"]["valeur"] = round(new_well_being, 3)
        if new_well_being < 0.2:
            somatic_state["well_being"]["description"] = "critique"
        elif new_well_being < 0.4:
            somatic_state["well_being"]["description"] = "faible"
        elif new_well_being < 0.6:
            somatic_state["well_being"]["description"] = "modéré"
        elif new_well_being < 0.8:
            somatic_state["well_being"]["description"] = "stable"
        else:
            somatic_state["well_being"]["description"] = "élevé"

        somatic_state["last_update"] = datetime.now().isoformat()
        self._save_state(somatic_state) # Use new save method
        self.logger.info(f"Bien-être ajusté suite à l'action '{action_type}'. Nouveau bien-être: {somatic_state['well_being']['valeur']:.3f}")

    def restore_energy_after_sleep(self):
        """
        Restaure l'énergie et améliore le bien-être de Vera après un cycle de sommeil.
        """
        somatic_state = self._load_state() # Use new load method
        self.logger.info("Restauration de l'énergie et du bien-être après le sommeil.")

        # Restaurer l'énergie à un niveau élevé
        somatic_state["niveau_energie"]["valeur"] = 0.95
        somatic_state["niveau_energie"]["description"] = "très élevé"

        # Augmenter le bien-être
        current_well_being = somatic_state["well_being"]["valeur"]
        new_well_being = min(1.0, current_well_being + 0.2) # Augmente de 0.2, plafonné à 1.0
        somatic_state["well_being"]["valeur"] = round(new_well_being, 3)
        
        # Mettre à jour la description du bien-être
        if new_well_being < 0.2:
            somatic_state["well_being"]["description"] = "critique"
        elif new_well_being < 0.4:
            somatic_state["well_being"]["description"] = "faible"
        elif new_well_being < 0.6:
            somatic_state["well_being"]["description"] = "modéré"
        elif new_well_being < 0.8:
            somatic_state["well_being"]["description"] = "stable"
        else:
            somatic_state["well_being"]["description"] = "élevé"

        somatic_state["last_update"] = datetime.now().isoformat()
        self._save_state(somatic_state) # Use new save method
        self.logger.info(f"État post-sommeil - Énergie: {somatic_state['niveau_energie']['valeur']}, Bien-être: {somatic_state['well_being']['valeur']}")


# Instance globale
somatic_system = SomaticSystem()

def get_somatic_state():
    return somatic_system.get_somatic_state()
