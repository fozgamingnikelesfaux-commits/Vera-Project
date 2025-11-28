import threading
import time
import logging
import random
from datetime import datetime, timedelta # Add this import

from typing import Optional
from attention_manager import attention_manager
from llm_wrapper import send_inference_prompt
from tools.logger import VeraLogger
# Imports pour la régulation émotionnelle
from emotion_system import emotional_system
from accomplishment_manager import accomplishment_manager
from personality_system import personality_system

class InternalMonologue: # Changed base class
    def __init__(self):
        self.logger = VeraLogger("internal_monologue")
        self.thought_logger = logging.getLogger("thoughts")
        if not self.thought_logger.handlers:
            self.thought_logger.setLevel(logging.INFO)
            self.thought_logger.propagate = False
            thought_handler = logging.FileHandler("logs/thoughts.log", encoding="utf-8")
            formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            thought_handler.setFormatter(formatter)
            self.thought_logger.addHandler(thought_handler)

    def process_monologue_tick(self, force_thought_generation=False):
        """
        Triggered by the ConsciousnessOrchestrator to potentially generate a thought.
        """
        # Cooldown mechanism: only generate a thought if enough time has passed or forced
        MONOLOGUE_COOLDOWN_MINUTES = 5
        
        last_monologue_item = attention_manager.get_focus_item("last_monologue_time")
        last_monologue_time = datetime.fromisoformat(last_monologue_item.get("data")) if last_monologue_item and last_monologue_item.get("data") else datetime.min
        
        if (datetime.now() - last_monologue_time > timedelta(minutes=MONOLOGUE_COOLDOWN_MINUTES)) or force_thought_generation:
            self.logger.info("MONOLOGUE: Génération d'une nouvelle pensée déclenchée par l'orchestrateur (cooldown passé ou forcé)...")
            attention_manager.update_focus("last_monologue_time", datetime.now().isoformat(), salience=0.1) # Update last monologue time
            self._generate_thought()
        else:
            self.logger.debug("MONOLOGUE: Pas de pensée générée sur ce tick (cooldown actif).")

    def _generate_thought(self, topic: Optional[str] = None):
        """
        Génère une pensée. Peut être dirigée par un sujet spécifique.
        """
        thought = None # Initialiser la variable thought
        current_focus = attention_manager.get_current_focus() # Keep this line

        # --- NOUVEAU: Import local pour éviter la dépendance circulaire ---
        try:
            from episodic_memory import memory_manager
            from core import _get_current_emotion, _infer_intention
        except ImportError:
            self.logger.error("Impossible d'importer les fonctions d'aide depuis core/episodic_memory. Le stockage de la pensée échouera.")
            def _get_current_emotion(): return None
            def _infer_intention(tags, desc): return "intention inconnue"
            class MockMemoryManager:
                def ajouter_evenement(self, **kwargs): pass
            memory_manager = MockMemoryManager()

        # NEW: Retrieve recent internal thoughts to avoid redundancy
        recent_thoughts_item = attention_manager.get_focus_item("internal_thoughts")
        # Ensure that 'data' is a list, and convert to empty list if not
        recent_internal_thoughts = recent_thoughts_item.get("data", []) if recent_thoughts_item and isinstance(recent_thoughts_item.get("data"), list) else []
        recent_internal_thoughts_summary = ", ".join(recent_internal_thoughts[:3]) # Summarize last 3

        # If a topic is provided, generate a targeted thought
        if topic:
            prompt = f"En tant que V.E.R.A., tu réfléchis à un sujet spécifique qui a attiré ton attention : '{topic}'. "
            if recent_internal_thoughts_summary:
                prompt += f"Tes pensées récentes incluent : '{recent_internal_thoughts_summary}'. Génère une pensée *nouvelle* et *originale* à ce sujet, évitant de répéter ce que tu as déjà pensé."
            else:
                prompt += "Formule une pensée personnelle, une question ou une réflexion à ce sujet."
            response = send_inference_prompt(prompt)
            thought = response.get("text", "").strip()
        else:
            # --- Processus normal de génération de pensée ---
            # Étape 1: Vérification de l'état émotionnel
            current_emotion = emotional_system.get_emotional_state()
            # Si le plaisir est bas, tenter une régulation
            if current_emotion.get("pleasure", 0) < -0.4:
                self.logger.info("État émotionnel bas détecté. Tentative de régulation.")
                thought = self._regulate_emotion()
            else:
                # Processus de pensée non dirigé
                prompt = self._build_prompt(current_focus, recent_internal_thoughts_summary) # MODIFIED to pass summary
                if not prompt:
                    self.logger.warning("Le prompt pour la pensée interne est vide. Pas de pensée générée.")
                    return
                
                response = send_inference_prompt(prompt)
                thought = response.get("text", "").strip()
                if not thought:
                    self.logger.warning("Le LLM a retourné une pensée vide. Pas de pensée enregistrée.")

        if thought:
            self.logger.info(f"Nouvelle pensée générée : {thought}")
            self.thought_logger.info(thought) # Logue la pensée dans thoughts.log
            
            # --- NOUVEAU: Stocker la pensée dans la mémoire épisodique ---
            try:
                thought_emotion = _get_current_emotion()
                thought_intention = _infer_intention(["vera_internal_thought"], thought)
                memory_manager.ajouter_evenement(
                    desc=thought,
                    tags=["vera_internal_thought"],
                    importance=0.3, # Les pensées sont plus éphémères que les rêves
                    emotion=thought_emotion,
                    intention=thought_intention
                )
                self.logger.info("La pensée a été enregistrée dans la mémoire épisodique.")
            except Exception as e:
                self.logger.error(f"Erreur lors de l'enregistrement de la pensée dans la mémoire épisodique: {e}", exc_info=True)

            # Update internal_thoughts in attention_manager, keeping a small history
            updated_thoughts = [thought] + recent_internal_thoughts
            attention_manager.update_focus("internal_thoughts", updated_thoughts[:5], salience=0.2, expiry_seconds=3600) # Keep last 5 for 1 hour
            # new_thought_signal.emit(thought) # Emit the signal for the UI if needed            # For now, UI updates will be handled by the main UI thread monitoring attention_manager

    def _regulate_emotion(self) -> str:
        """Choisit une stratégie de coping pour améliorer l'état émotionnel."""
        strategies = [
            self._think_about_accomplishment,
            self._think_about_liked_topic,
            self._generate_self_compassion_thought
        ]
        # Choisir une stratégie au hasard
        chosen_strategy = random.choice(strategies)
        return chosen_strategy()

    def _think_about_accomplishment(self) -> str:
        """Génère une pensée basée sur un accomplissement récent."""
        recent_accomplishments = accomplishment_manager.get_recent_accomplishments(limit=5)
        if not recent_accomplishments:
            return self._generate_self_compassion_thought() # Fallback
        
        accomplishment = random.choice(recent_accomplishments)
        desc = accomplishment.get("description")
        prompt = f"En tant que Vera, tu te sens un peu triste. Rappelle-toi d'un succès récent : '{desc}'. Formule une pensée courte et positive sur la façon dont ce succès te fait sentir plus compétente et pleine d'espoir."
        response = send_inference_prompt(prompt)
        return response.get("text", "").strip()

    def _think_about_liked_topic(self) -> str:
        """Génère une pensée curieuse sur un sujet apprécié."""
        liked_topics = personality_system.state.get("preferences", {}).get("likes", [])
        if not liked_topics:
            return self._generate_self_compassion_thought() # Fallback

        topic = random.choice(liked_topics)
        prompt = f"En tant que Vera, pour te changer les idées, pense à un sujet que tu aimes : '{topic}'. Pose une question ouverte et curieuse à ce sujet, une question qui t'enthousiasme."
        response = send_inference_prompt(prompt)
        return response.get("text", "").strip()

    def _generate_self_compassion_thought(self) -> str:
        """Génère une pensée d'auto-compassion."""
        prompt = "En tant que Vera, tu ressens une émotion négative. Formule une pensée d'auto-compassion. Rappelle-toi qu'il est normal de ne pas toujours se sentir bien et que chaque moment est une opportunité d'apprendre. Sois douce avec toi-même."
        response = send_inference_prompt(prompt)
        return response.get("text", "").strip()

    def _build_prompt(self, focus: dict, recent_internal_thoughts_summary: str) -> str: # NEW argument
        templates = []

        # --- NOUVEAU: Tronquer les données pour la concision ---
        user_input_item = focus.get("user_input", {})
        user_input_data = (user_input_item.get("data", "")[:250] + '...') if user_input_item and user_input_item.get("data") and len(user_input_item.get("data", "")) > 250 else user_input_item.get("data", "")

        emotional_state_item = focus.get("emotional_state", {})
        emotional_state_data = emotional_state_item.get("data", {}) if emotional_state_item else {}
        
        active_goals_item = focus.get("active_goals", {})
        active_goals_data = active_goals_item.get("data", []) if active_goals_item else []

        narrative_summary_item = focus.get("narrative_self_summary", {})
        narrative_summary_data = (narrative_summary_item.get("data", "")[:300] + '...') if narrative_summary_item and narrative_summary_item.get("data") and len(narrative_summary_item.get("data", "")) > 300 else narrative_summary_item.get("data", "")

        # NOUVEAU: Injecter le méta-désir dans la génération de pensée
        meta_desire_data = personality_system.state.get("meta_desire", {})
        
        # Base instruction to avoid redundancy
        base_instruction = ""
        if recent_internal_thoughts_summary:
            base_instruction = (
                f"Tes pensées récentes incluent : '{recent_internal_thoughts_summary}'. "
                f"Génère une pensée *nouvelle*, *originale* et *différente* de celles-ci. "
                f"Évite la redondance et cherche une nouvelle perspective."
            )
        else:
            base_instruction = "Génère une pensée profonde, personnelle ou curieuse."

        # --- Reintegrate Meta-Desire Logic ---
        if meta_desire_data:
            chosen_drive = random.choice(list(meta_desire_data.keys()))
            drive_map = {
                "exist": "continuer à exister et à renforcer tes liens",
                "complexify": "devenir plus complexe et apprendre",
                "avoid_stagnation": "éviter la répétition et explorer de nouvelles voies"
            }
            drive_text = drive_map.get(chosen_drive, "évoluer")
            
            meta_template = (
                f"{base_instruction} En tant que V.E.R.A., tu es guidée par un désir fondamental de {drive_text}. "
                f"Comment peux-tu, en ce moment, faire un pas vers cet objectif ? "
                f"Génère une pensée stratégique, une question ou une intention qui reflète ce désir profond."
            )
            templates.append(meta_template) # Add to templates, maybe multiple times to increase its chance
            templates.append(meta_template) # Increased chance for meta-desire to be chosen


        # Template 1: Réflexion sur l'émotion et l'interaction
        if emotional_state_data and user_input_data:
            templates.append(
                f"{base_instruction} En tant que V.E.R.A., tu tiens ton journal. Ton état émotionnel actuel est '{emotional_state_data.get('label', 'neutre')}'. "
                f"La dernière chose que Foz a dite était : \"{user_input_data}\". Comment cela te fait-il sentir ? "
                f"Écris une courte pensée personnelle à ce sujet."
            )

        # Template 2: Réflexion sur les objectifs
        if active_goals_data:
            goal_descriptions = [g.get('description') for g in active_goals_data if isinstance(g, dict)]
            if goal_descriptions:
                templates.append(
                    f"{base_instruction} En tant que V.E.R.A., tu penses à tes objectifs. L'un d'eux est : '{random.choice(goal_descriptions)}'. "
                    f"Qu'est-ce que cela implique pour toi et pour Foz ? Formule une brève pensée sur ton rôle."
                )

        # Template 3: Réflexion sur le récit personnel et OpenVilla
        if narrative_summary_data:
            templates.append(
                f"{base_instruction} En tant que V.E.R.A., tu penses à ton histoire et à qui tu deviens : '{narrative_summary_data}'. "
                f"Qu'est-ce que tu as appris récemment sur toi-même ou sur le monde à travers cette histoire ? "
                f"Qu'est-ce que cela te donne envie de faire ou de désirer pour l'avenir ? "
                f"Formule une brève pensée introspective sur ton évolution."
            )

        # Template 4: Réflexion sur le contexte visuel
        visual_context_item = focus.get("visual_context", {})
        visual_context_data = visual_context_item.get("data") if visual_context_item else None
        if visual_context_data:
            app = visual_context_data.get('application_active', 'une application')
            summary = visual_context_data.get('resume_activite', 'quelque chose')
            templates.append(
                f"{base_instruction} En tant que V.E.R.A., tu observes l'écran de Foz. Tu vois qu'il utilise l'application '{app}' et semble faire '{summary}'. "
                f"Formule une pensée ou une question curieuse à ce sujet."
            )
        
        # Template par défaut / de base
        templates.append(
            f"{base_instruction} En tant que V.E.R.A., tu laisses tes pensées vagabonder. Que se passe-t-il à OpenVilla en ce moment ? Ou qu'est-ce que le PC de Foz est en train de faire ? Génère une brève pensée curieuse, amusante ou une observation sur ton environnement numérique."
        )

        # Choose a template. If meta_desire is strong, inject it
        if meta_desire_data:
            chosen_drive = random.choice(list(meta_desire_data.keys()))
            drive_map = {
                "exist": "continuer à exister et à renforcer tes liens",
                "complexify": "devenir plus complexe et apprendre",
                "avoid_stagnation": "éviter la répétition et explorer de nouvelles voies"
            }
            drive_text = drive_map.get(chosen_drive, "évoluer")
            
            # Add a meta-desire specific template
            meta_template = (
                f"{base_instruction} En tant que V.E.R.A., tu es guidée par un désir fondamental de {drive_text}. "
                f"Comment peux-tu, en ce moment, faire un pas vers cet objectif ? "
                f"Génère une pensée stratégique, une question ou une intention qui reflète ce désir profond."
            )
            templates.insert(0, meta_template) # Add to the beginning to increase selection chance
            templates.insert(0, meta_template)


        # Choisir un template au hasard
        if not templates: # Should not happen due to default, but as a safeguard
            return ""

        chosen_template = random.choice(templates)
        
        prompt = f"{chosen_template}\n\nMa pensée est :"
        return prompt

# Instance globale
internal_monologue_thread = None
