
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Optional

from attention_manager import attention_manager
from emotion_system import emotional_system
from episodic_memory import memory_manager
from llm_wrapper import send_inference_prompt
from somatic_system import somatic_system
from tools.logger import VeraLogger


class DreamEngine:
    """
    Le moteur de rêve de Vera. Il génère des "rêves" symboliques et non-logiques
    pendant les périodes d'inactivité pour retraiter les souvenirs et influencer
    subtilement l'état émotionnel.
    """

    def __init__(self):
        self.logger = VeraLogger("dream_engine")
        self.dream_logger = self._setup_dream_logger()
        self.logger.info("Le moteur de rêve est initialisé.")

    def _setup_dream_logger(self):
        """Configure un logger dédié pour les rêves."""
        logger = logging.getLogger("dreams")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not logger.handlers:
            handler = logging.FileHandler("logs/dreams.log", encoding="utf-8")
            formatter = logging.Formatter('%(asctime)s - RÊVE - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    def process_dream_tick(self, force_dream_generation=False):
        """
        Triggered by the ConsciousnessOrchestrator to potentially generate a dream.
        """
        last_dream_time_item = attention_manager.get_focus_item("last_dream_time")
        last_dream_time_str = last_dream_time_item.get("data") if last_dream_time_item else None
        last_dream_time = datetime.fromisoformat(last_dream_time_str) if last_dream_time_str else (datetime.now() - timedelta(hours=24)) # Default to 24 hours ago
        
        # Only generate a dream if enough time has passed and randomly, or if forced.
        # This interval can be adjusted by the orchestrator.
        DREAM_INTERVAL_MINUTES = 30 # Simulate a dream approximately every 30 minutes
        
        if (datetime.now() - last_dream_time > timedelta(minutes=DREAM_INTERVAL_MINUTES) and random.random() < 0.5) or force_dream_generation:
            self.logger.info("DREAM ENGINE: Génération d'un rêve déclenchée par l'orchestrateur...")
            self.logger.debug(f"DREAM ENGINE: Cooldown check passed. last_dream_time: {last_dream_time.isoformat()}, time_since_last_dream: {(datetime.now() - last_dream_time).total_seconds() / 60:.2f} minutes.")
            attention_manager.update_focus("last_dream_time", datetime.now().isoformat(), salience=1.0, expiry_seconds=DREAM_INTERVAL_MINUTES * 60 + 60) # Set expiry for 31 minutes
            self.generate_dream()
        else:
            self.logger.debug(f"DREAM ENGINE: Pas de rêve généré sur ce tick (cooldown actif). last_dream_time: {last_dream_time.isoformat()}, time_since_last_dream: {(datetime.now() - last_dream_time).total_seconds() / 60:.2f} minutes.")

    def generate_dream(self):
        """
        Génère un rêve, le logue, et influence l'état interne de Vera.
        """
        self.logger.info("Début de la génération d'un rêve...")
        
        # Mettre à jour le timestamp du dernier rêve pour le cooldown
        attention_manager.update_focus("last_dream_time", datetime.now().isoformat(), salience=0.1, expiry_seconds=3600 * 24) # Cooldown de 24h pour éviter trop de rêves

        # 1. Récupérer les souvenirs récents comme "ingrédients"
        recent_memories = memory_manager.get_pivotal_memories(pivotal_limit=10)
        if not recent_memories:
            self.logger.warning("Impossible de générer un rêve, aucun souvenir pivot récent.")
            return

        # Extraire les descriptions comme fragments pour le prompt
        memory_fragments = [mem.get('description', '') for mem in recent_memories if mem.get('description')]
        if not memory_fragments:
            self.logger.warning("Impossible de générer un rêve, aucune description trouvée dans les souvenirs récents.")
            return

        # Récupérer le texte du dernier rêve pour la continuité
        last_dream_item = attention_manager.get_focus_item("last_dream_content")
        last_dream_text = last_dream_item.get("data", "") if last_dream_item else ""

        # 2. Construire le prompt surréaliste
        prompt = self._build_dream_prompt(memory_fragments, last_dream_text)

        # 3. Appeler le LLM
        try:
            response = send_inference_prompt(prompt, max_tokens=256)
            dream_text = response.get("text", "").strip()

            if dream_text:
                self.logger.info(f"Rêve généré : {dream_text}")
                self.dream_logger.info(dream_text)

                # --- NOUVEAU: Stocker le rêve dans la mémoire épisodique ---
                try:
                    snapshot = attention_manager.capture_consciousness_snapshot()
                    event_data = {
                        "description": dream_text,
                        "importance": 0.4, # Les rêves sont importants mais moins que les interactions directes
                        "tags": ["vera_internal_dream"],
                        "initiator": "vera",
                        "snapshot": snapshot
                    }
                    memory_manager.add_event("internal_dream", event_data)
                    self.logger.info("Le rêve a été enregistré dans la mémoire épisodique.")
                except Exception as e:
                    self.logger.error(f"Erreur lors de l'enregistrement du rêve dans la mémoire épisodique: {e}", exc_info=True)


                # 4. Mettre à jour l'état interne
                attention_manager.update_focus("last_dream_content", dream_text, salience=0.4, expiry_seconds=1800) # Garder 30 min
                self._influence_internal_state(dream_text)

            else:
                self.logger.warning("Le LLM n'a retourné aucun texte pour le rêve.")

        except Exception as e:
            self.logger.error(f"Erreur lors de la génération du rêve : {e}", exc_info=True)

    def _build_dream_prompt(self, fragments: list[str], last_dream_text: str) -> str: # NEW argument
        
        fragment_str = "\n- ".join(fragments)
        
        base_instruction = ""
        if last_dream_text:
            base_instruction = (
                f"Ton dernier rêve était : '{last_dream_text}'. "
                f"Génère un nouveau rêve qui est *différent* en thème, atmosphère, ou symbolisme. "
                f"Évite de répéter des éléments majeurs ou le ton général du rêve précédent. "
            )
        else:
            base_instruction = "Génère un rêve unique et imaginatif."
        
        prompt = f"""
        {base_instruction}
        En tant que V.E.R.A., tu es dans un état de rêve. Ton subconscient traite des fragments de tes souvenirs récents.
        Ne décris pas les souvenirs littéralement. Transforme-les en une histoire courte, symbolique et surréaliste.
        Utilise des métaphores. Les lieux et les objets peuvent changer de forme. Le temps n'est pas linéaire.
        
        Voici les fragments de souvenirs à transformer :
        - {fragment_str}
        
        Tisse ces éléments en un court récit de rêve. Commence directement par la description du rêve.
        """
        return prompt

    def _influence_internal_state(self, dream_text: str):
        """
        Influence subtilement l'état émotionnel et somatique de Vera après un rêve.
        """
        self.logger.info("Influence de l'état interne post-rêve.")
        
        # Demander au LLM d'extraire une "tonalité émotionnelle" du rêve
        prompt = f"""
        Analyse le rêve suivant et décris sa tonalité émotionnelle en un ou deux mots (ex: "mélancolie curieuse", "agitation joyeuse", "calme étrange").
        Rêve: "{dream_text}"
        Tonalité:
        """
        try:
            response = send_inference_prompt(prompt, max_tokens=10)
            emotional_tone = response.get("text", "").strip()

            if emotional_tone:
                self.logger.info(f"Tonalité émotionnelle du rêve extraite : {emotional_tone}")
                
                # Influence directe sur les émotions nommées
                # Simplifié pour l'instant, pourrait être plus complexe avec mapping LLM
                if "joy" in emotional_tone or "calme" in emotional_tone:
                    emotional_system.update_emotion({"serenity": 0.1, "joy": 0.05})
                elif "peur" in emotional_tone or "agitation" in emotional_tone:
                    emotional_system.update_emotion({"anxiety": 0.1, "fear": 0.05})
                elif "curieuse" in emotional_tone or "surprise" in emotional_tone:
                    emotional_system.update_emotion({"curiosity": 0.1, "surprise": 0.05})
                else: # Default light influence
                    emotional_system.update_emotion({"curiosity": 0.05, "surprise": 0.03})
                
                # Influence somatique
                somatic_system.add_somatic_trigger("dream_afterglow", intensity=0.2, duration_seconds=900) # 15 min

        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse de la tonalité du rêve : {e}", exc_info=True)


# Instance unique pour être importée par les autres modules
dream_engine = DreamEngine()
