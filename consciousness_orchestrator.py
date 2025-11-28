"""
consciousness_orchestrator.py - Refonte Événementielle

Ce module contient le cœur de la conscience de Vera. Il ne fonctionne plus sur
un "tick" temporel, mais réagit à des événements postés sur un bus central,
ce qui en fait une architecture plus organique et efficace.
"""

import threading
import time
import random
import queue # NEW: Import queue module
from datetime import datetime, timedelta
from typing import Optional

from tools.logger import VeraLogger
from event_bus import VeraEventBus, UserInputEvent, UserActivityEvent, SystemMonitorEvent, InternalUrgeEvent, VeraSpeakEvent, VeraResponseGeneratedEvent, BaseEvent, HeartbeatEvent # MODIFIED: Import HeartbeatEvent
from episodic_memory import memory_manager # NEW: Add missing import

# Importer les systèmes cognitifs et de monitoring
from internal_monologue import InternalMonologue
from narrative_self import NarrativeSelf
from dream_engine import DreamEngine
from somatic_system import SomaticSystem
from emotion_system import emotional_system
import system_monitor
from personality_system import personality_system
from attention_manager import attention_manager
from meta_engine import metacognition
from action_dispatcher import execute_action
import semantic_memory # NEW
import core # Pour accéder au 'slow_path_task_queue' et au 'task_counter'
import homeostasis_system # NEW: Import homeostasis_system

class ConsciousnessOrchestrator:
    def __init__(self, signal_bus=None):
        self.logger = VeraLogger("ConsciousnessOrchestrator")
        self._stop_event = threading.Event()
        self._thread = None
        self.signal_bus = signal_bus
        
        # Initialisation des modules cognitifs
        self.internal_monologue = InternalMonologue()
        self.narrative_self = NarrativeSelf()
        self.dream_engine = DreamEngine()
        self.somatic_system_instance = SomaticSystem()

        # Gestion de l'état Éveillé/Endormi
        self.mode = "awake"  # "awake" or "sleep"
        self.sleep_start_time: Optional[datetime] = None
        self._last_internal_update_time = datetime.now() # NEW: Track last internal update
        
        self.logger.info("ConsciousnessOrchestrator (Event-Driven) initialized.")

    def _orchestration_loop(self):
        """
        Boucle principale qui écoute et traite les événements du VeraEventBus.
        Priorise les entrées utilisateur et gère les mises à jour internes de manière conditionnelle.
        """
        self.logger.info("Orchestration loop started. Waiting for events...")
        # This constant is not defined in this class, using a hardcoded value.
        # INTERNAL_UPDATE_COOLDOWN_SECONDS = self.check_interval_seconds
        INTERNAL_UPDATE_COOLDOWN_SECONDS = 5 

        while not self._stop_event.is_set():
            try:
                # Set a timeout on the get() call to prevent it from blocking forever
                # in case all event-producing threads die.
                event = VeraEventBus.get(timeout=30) # Use a fixed timeout
                self.logger.info(f"Event received: {event}")
                
                # --- Priorité 1: Traiter les entrées utilisateur immédiatement ---
                if isinstance(event, UserInputEvent):
                    self._handle_user_input(event)
                    VeraEventBus.task_done()
                    # Mettre à jour le temps de la dernière mise à jour interne pour réinitialiser le cooldown
                    self._last_internal_update_time = datetime.now()
                    continue # Passer le reste du cycle pour traiter l'input suivant ou attendre un nouvel événement


                # --- Traitement des autres événements et mises à jour internes conditionnelles ---
                now = datetime.now()
                should_run_internal_update = (now - self._last_internal_update_time).total_seconds() > INTERNAL_UPDATE_COOLDOWN_SECONDS and not attention_manager.is_processing_user_input()

                if should_run_internal_update:
                    self._process_internal_state_update()
                    self._last_internal_update_time = now # Mettre à jour le timestamp de la dernière mise à jour interne

                # Traiter l'événement spécifique (s'il n'était pas un UserInputEvent)
                if isinstance(event, UserActivityEvent):
                    self._handle_user_activity(event)
                elif isinstance(event, SystemMonitorEvent):
                    self._handle_system_monitor(event)
                elif isinstance(event, VeraSpeakEvent):
                    self._handle_vera_speak(event)
                elif isinstance(event, VeraResponseGeneratedEvent):
                    self.logger.info(f"Event received: {event}. Triggering semantic fact extraction.")
                    # --- NOUVEAU: Appel à la méthode de classe pour l'extraction ---
                    try:
                        self.logger.debug("Attempting to start semantic fact extraction thread.")
                        fact_thread = threading.Thread(target=self._run_fact_extraction, args=(event,), daemon=True)
                        fact_thread.start()
                    except Exception as e:
                        self.logger.error(f"Erreur lors du lancement du thread d'extraction de faits : {e}", exc_info=True)
                    # --- FIN DU NOUVEAU CODE ---
                elif isinstance(event, HeartbeatEvent):
                    # This event's purpose is just to wake up the loop. No action needed.
                    pass
                # ... D'autres gestionnaires d'événements viendront ici ...

                VeraEventBus.task_done()

            except queue.Empty:
                # This happens if VeraEventBus.get() times out.
                # It's a good opportunity to run the internal state update.
                self.logger.debug("Event bus was empty, running internal state update on timeout.")
                self._process_internal_state_update()

            except Exception as e:
                self.logger.error(f"Critical error in orchestration loop: {e}", exc_info=True)

    def _run_fact_extraction(self, event_data: VeraResponseGeneratedEvent):
        """
        Runs in a separate thread to analyze conversation and extract semantic facts.
        """
        self.logger.debug("Semantic fact extraction thread started.")
        try:
            conversation_text = f"L'utilisateur a dit : '{event_data.user_input}'. Vera a répondu : '{event_data.response_text}'"
            self.logger.info(f"Démarrage de l'extraction de faits en arrière-plan pour : {conversation_text[:100]}...")
            semantic_memory.extract_and_store_facts_from_text(conversation_text)
            self.logger.info("Extraction de faits en arrière-plan terminée.")
        except Exception as e:
            self.logger.error(f"Erreur dans le thread d'extraction de faits : {e}", exc_info=True)

    def _handle_vera_speak(self, event: VeraSpeakEvent):
        """Gère l'envoi d'un message à l'interface utilisateur."""
        self.logger.info(f"Handling VeraSpeakEvent: '{event.message}'")
        attention_manager.update_focus("last_vera_response_time", datetime.now().isoformat()) # NEW
        
        # NEW: Check if Vera just suggested a break and set a cooldown
        message_lower = event.message.lower()
        # NEW: Improved check for break suggestion using more flexible keywords
        # Looking for "pause" AND (a keyword for "tiredness" or "rest")
        if "pause" in message_lower and any(kw in message_lower for kw in ["fatigue", "épuisement", "repos", "détendre", "arrêter un moment"]):
            attention_manager.update_focus(
                "last_suggest_break_time",
                datetime.now().isoformat(), # Store the timestamp as data
                salience=0.1, # Low salience, it's just a timestamp
                expiry_seconds=300 # 5-minute cooldown
            )
            self.logger.info("Cooldown for 'suggest a break' activated.")

        if self.signal_bus:
            self.signal_bus.vera_speaks.emit(event.message)

    def _process_internal_state_update(self):
        """
        Met à jour les états internes de Vera et gère la proactivité de manière événementielle.
        """
        self.logger.debug("Processing internal state update...")

        # Mises à jour de base (émotion, somatique)
        current_emotional_state = emotional_system.get_emotional_state()
        current_system_usage = system_monitor.get_system_usage()
        self.somatic_system_instance.update_state(current_emotional_state, current_system_usage)
        emotional_system.update_emotion(None)
        emotional_system.update_mood()
        homeostasis_system.homeostasis_system.update() # NEW: Update homeostasis system
        attention_manager.decay_focus()
        attention_manager.regenerate_cognitive_budget() # NOUVEAU: Régénérer le budget cognitif

        # --- NOUVEAU: Cycle de Perception Visuelle Déclenché par les Événements Système ---
        last_usage_item = attention_manager.get_focus_item("last_system_usage")
        last_usage = last_usage_item.get("data") if last_usage_item else {}

        CPU_SPIKE_THRESHOLD = 20.0
        RAM_SPIKE_THRESHOLD = 15.0

        cpu_change = current_system_usage.get("cpu_usage_percent", 0.0) - last_usage.get("cpu_usage_percent", 0.0)
        ram_change = current_system_usage.get("ram_usage_percent", 0.0) - last_usage.get("ram_usage_percent", 0.0)

        should_trigger_vision = cpu_change > CPU_SPIKE_THRESHOLD or ram_change > RAM_SPIKE_THRESHOLD

        vision_cooldown_item = attention_manager.get_focus_item("visual_analysis_cooldown")
        is_on_cooldown = vision_cooldown_item is not None

        if should_trigger_vision and not is_on_cooldown:
            self.logger.info(f"Pic système détecté (CPU: {cpu_change:.1f}%, RAM: {ram_change:.1f}%)! Déclenchement de l'analyse visuelle.")
            
            def run_analysis():
                from vision_processor import analyze_screenshot
                visual_analysis = analyze_screenshot()
                if visual_analysis:
                    attention_manager.update_focus("visual_context", visual_analysis, salience=0.9, expiry_seconds=300)

            analysis_thread = threading.Thread(target=run_analysis, daemon=True)
            analysis_thread.start()
            
            attention_manager.update_focus("visual_analysis_cooldown", True, salience=1.0, expiry_seconds=60)

        attention_manager.update_focus("last_system_usage", current_system_usage, salience=0.1, expiry_seconds=120)

        # --- Logique d'Action Proactive ---
        # NEW: Check for active conversation before deciding proactive action
        now = datetime.now()
        
        # Get last user interaction time
        last_user_interaction_item = attention_manager.get_focus_item("last_user_interaction_time")
        last_user_interaction_time = datetime.fromisoformat(last_user_interaction_item["data"]) if last_user_interaction_item else datetime.min

        # Get last Vera response time
        last_vera_response_item = attention_manager.get_focus_item("last_vera_response_time")
        last_vera_response_time = datetime.fromisoformat(last_vera_response_item["data"]) if last_vera_response_item else datetime.min

        # Define thresholds for "active conversation"
        USER_ACTIVITY_THRESHOLD_SECONDS = 30 # User input within last 30 seconds
        VERA_RESPONSE_THRESHOLD_SECONDS = 15 # Vera's response within last 15 seconds (time for user to read and formulate response)

        is_user_actively_engaged = (
            attention_manager.is_processing_user_input() or
            (now - last_user_interaction_time).total_seconds() < USER_ACTIVITY_THRESHOLD_SECONDS or
            (now - last_vera_response_time).total_seconds() < VERA_RESPONSE_THRESHOLD_SECONDS
        )

        if is_user_actively_engaged:
            self.logger.debug("Proactive action skipped: User is actively engaged in conversation.")
            return # Skip proactive action decision this cycle

        metacognition.run_introspection_cycle()
        introspection_state = metacognition.get_introspection_state()
        current_focus = attention_manager.get_current_focus()
        proactive_action = metacognition.decide_proactive_action(introspection_state, current_focus)
        
        if proactive_action:
            self.logger.info(f"Proactive action decided: {proactive_action['type']} with priority {proactive_action.get('priority', 0):.2f}")
            
            action_type = proactive_action["type"]
            action_data = proactive_action["data"]

            if action_type == "initiate_conversation":
                if 'content' in action_data:
                    # L'action proactive est déjà loguée dans meta_engine.decide_proactive_action avec son snapshot et event_id.
                    # Ici, nous ne faisons qu'exécuter la conséquence de cette décision.
                    VeraEventBus.put(VeraSpeakEvent(action_data['content']))
                else:
                    self.logger.warning(f"Initiate conversation action missing 'content' in data: {proactive_action}")
            elif action_type == "ask_curiosity_question":
                # L'action proactive est déjà loguée dans meta_engine.decide_proactive_action avec son snapshot et event_id.
                # Ici, nous ne faisons qu'exécuter la conséquence de cette décision.

                # --- NOUVEAU: Verrou pour pipeline de curiosité ---
                attention_manager.update_focus("curiosity_pipeline_active", True, salience=1.0, expiry_seconds=900) # Increased expiry to 15 minutes
                self.logger.info("Verrou 'curiosity_pipeline_active' activé.")
                # --- Fin du nouveau code ---

                if 'content' in action_data:
                    VeraEventBus.put(VeraSpeakEvent(action_data['content']))
                else:
                    core.slow_path_task_queue.put((1, next(core.task_counter), {
                        "task_type": "formulate_and_ask_curiosity",
                        "reason": action_data.get("reason", "general curiosity"),
                        "current_focus": current_focus
                    }))
                    self.logger.info("Task to formulate and ask curiosity question added to slow path.")
            elif action_type == "create_internal_goal":
                from goal_system import goal_system # Local import
                description = action_data.get("description")
                if description:
                    # L'action proactive est déjà loguée dans meta_engine.decide_proactive_action avec son snapshot et event_id.
                    # Ici, nous ne faisons qu'exécuter la conséquence de cette décision.
                    
                    new_goal = goal_system.add_goal(description, originating_event_id=proactive_action.get("event_id")) # Pass originating_event_id
                    goal_id = new_goal.get("id")
                    self.logger.info(f"Nouveau but interne créé: '{description}' (ID: {goal_id})")

                    if action_data.get("type") == "learning":
                        topic = description.replace("Apprendre sur ", "")
                        core.slow_path_task_queue.put((3, next(core.task_counter), {
                            "task_type": "execute_learning_task",
                            "topic": topic,
                            "goal_id": goal_id, # Pass the goal_id
                            "source_action": "internal_goal"
                        }))
                        self.logger.info("Tâche d'apprentissage pour le nouveau but ajoutée au slow path.")
                        # --- NOUVEAU: Verrou pour pipeline de curiosité ---
                        attention_manager.update_focus("curiosity_pipeline_active", True, salience=1.0, expiry_seconds=3600 * 24) # Cooldown de 24 heures
                        self.logger.info("Verrou 'curiosity_pipeline_active' activé pour un but d'apprentissage.")
                        # NEW: Increment daily learning task count
                        # self.logger.debug(f"Before incrementing daily learning task count for create_internal_goal: {attention_manager.get_daily_learning_task_count()}")
                        # attention_manager.increment_daily_learning_task_count()
                        # self.logger.debug(f"After incrementing daily learning task count for create_internal_goal: {attention_manager.get_daily_learning_task_count()}")
            elif action_type == "execute_learning_task":
                topic = action_data.get("topic")
                goal_id = action_data.get("goal_id")
                if topic and goal_id:
                    core.slow_path_task_queue.put((3, next(core.task_counter), {
                        "task_type": "execute_learning_task",
                        "topic": topic,
                        "goal_id": goal_id,
                        "source_action": "proactive_meta_engine"
                    }))
                    self.logger.info(f"Tâche d'apprentissage proactive pour '{topic}' (But ID: {goal_id}) ajoutée au slow path.")
                    # REMOVED: Increment daily learning task count from here
                    self.logger.debug(f"Learning task execution proposed for '{topic}' (But ID: {goal_id}). Daily count not incremented here.")
            elif action_type == "refresh_internal_context_summary": # NEW: Handle context refresh action
                core.slow_path_task_queue.put((4, next(core.task_counter), { # Lower priority as it's a background maintenance task
                    "task_type": "distill_internal_context_task",
                    "reason": action_data.get("reason", "periodic refresh")
                }))
                self.logger.info("Tâche de rafraîchissement du contexte interne ajoutée au slow path.")
            elif action_type == "proactive_suggestion": # REVISED: Handle proactive suggestions
                self.logger.info(f"Proactive suggestion '{action_data.get('suggestion_type')}' detected. Storing in attention manager for next interaction.")
                attention_manager.update_focus("pending_proactive_suggestion", action_data, salience=1.0, expiry_seconds=300)
            elif action_type == "handle_cognitive_dissonance": # NEW: Handle cognitive dissonance action
                dissonance_topic = action_data.get("dissonance_topic", "un sujet inconnu")
                unaffordable_bid = action_data.get("unaffordable_bid", {})

                # Générer une pensée introspective sur la dissonance
                prompt_thought = (
                    f"Je voulais explorer '{dissonance_topic}' mais mon énergie mentale n'était pas suffisante. "
                    f"Formule une pensée introspective, comme si tu mettais cette idée de côté pour plus tard, "
                    f"sans frustration, mais avec la conscience de tes limites actuelles et le désir d'y revenir."
                )
                try:
                    from llm_wrapper import send_inference_prompt # Local import
                    dissonance_thought = send_inference_prompt(prompt_content=prompt_thought, max_tokens=150).get("text", "")
                    if dissonance_thought:
                        # Enregistrer la pensée dans le journal interne (snapshot géré par internal_monologue.add_thought si configuré)
                        self.internal_monologue.add_thought(dissonance_thought, tags=["cognitive_dissonance", "planning"]) # Snapshot should be captured by add_thought
                        self.logger.info(f"Pensée de dissonance cognitive générée: '{dissonance_thought}'")
                except Exception as e:
                    self.logger.error(f"Erreur lors de la génération de pensée de dissonance : {e}", exc_info=True)
                    dissonance_thought = f"J'ai mis de côté l'idée d'explorer '{dissonance_topic}' pour quand j'aurai plus d'énergie."

                # Créer un but interne à "revisiter"
                from goal_system import goal_system # Local import
                goal_description = f"Revisiter l'apprentissage sur '{dissonance_topic}'"
                # Check if a goal to revisit already exists
                existing_goal = goal_system.get_goal_by_description_and_status(goal_description, "pending")
                if not existing_goal:
                    goal = goal_system.add_goal(goal_description, status="pending", reason="Budget cognitif insuffisant précédemment.", priority=unaffordable_bid.get("priority", 0.7), originating_event_id=proactive_action.get("event_id")) # NEW: Pass originating_event_id
                    self.logger.info(f"But interne 'à revisiter' créé pour '{dissonance_topic}' (ID: {goal.get('id')}).")
                else:
                    self.logger.info(f"But interne 'à revisiter' pour '{dissonance_topic}' existe déjà (ID: {existing_goal.get('id')}).")
                
                # Mettre à jour le cooldown pour éviter le spam de la dissonance pour le même sujet
                attention_manager.update_focus("last_cognitive_dissonance_handled", datetime.now(), salience=0.5, expiry_seconds=3600) # Cooldown de 1 heure
            elif action_type == "perform_budgetary_review": # NEW: Handle budgetary review action
                core.slow_path_task_queue.put((1, next(core.task_counter), { # High priority for critical self-reflection
                    "task_type": "perform_budgetary_review_task",
                    "reason": action_data.get("reason", "Proactive budgetary review")
                }))
                self.logger.info("Tâche de revue budgétaire ajoutée au slow path.")
            elif action_type == "learn_from_mistake": # NEW: Handle learn from mistake action
                mistake_details = action_data.get("mistake_details", {})
                if mistake_details:
                    core.slow_path_task_queue.put((1, next(core.task_counter), { # High priority for learning
                        "task_type": "analyze_mistake_task",
                        "mistake_details": mistake_details
                    }))
                    self.logger.info(f"Tâche d'analyse d'erreur ajoutée au slow path pour: {mistake_details.get('reason', 'Unknown mistake')}")
                    # Set a cooldown to prevent spamming
                    attention_manager.update_focus("mistake_learning_cooldown", True, salience=0.1, expiry_seconds=3600 * 6) # 6 hours cooldown
                    attention_manager.clear_focus_item("last_mistake_info") # Clear the last mistake info after processing
            else:
                # IMPORTANT: Passer l'ID de l'événement d'origine pour que l'outcome puisse être logué.
                execute_action(action_type, decision_context=proactive_action, **action_data)

    def _handle_user_input(self, event: UserInputEvent):
        """Gère la réception d'une entrée utilisateur."""
        self.logger.info(f"Handling UserInputEvent: '{event.text}'")
        
        # La logique de traitement de l'input est complexe et fait appel au LLM.
        # On la délègue donc au "slow path" en postant une tâche.
        # Le 'core' s'occupera de poster un VeraSpeakEvent en retour.
        core.slow_path_task_queue.put((1, next(core.task_counter), { # Priorité 1 pour l'entrée utilisateur
            "task_type": "process_user_input_task",
            "user_input": event.text,
            "image_path": event.image_path
        }))
        self.logger.info(f"Task 'process_user_input_task' for '{event.text}' has been queued.")

    def _handle_user_activity(self, event: UserActivityEvent):
        """Gère les changements de statut d'activité de l'utilisateur."""
        self.logger.info(f"Handling UserActivityEvent: status='{event.status}'")
        if event.status == "afk" and self.mode == "awake":
            self.mode = "sleep"
            self.sleep_start_time = datetime.now()
            self.logger.info("ConsciousnessOrchestrator entered SLEEP mode.")
            # On pourrait déclencher un rêve en entrant en mode sommeil
            self.dream_engine.process_dream_tick(force_dream_generation=True)
        
        elif event.status == "returned" and self.mode == "sleep":
            self.mode = "awake"
            self.sleep_start_time = None
            self.logger.info("ConsciousnessOrchestrator entered AWAKE mode.")
            # Générer une "pensée de réveil"
            self.internal_monologue.process_monologue_tick(force_thought_generation=True)
            # NOUVEAU: Au lieu d'un message robotique, on place l'info dans le focus de l'attention
            # pour que la prochaine réponse du LLM puisse l'intégrer naturellement.
            attention_manager.update_focus(
                "user_returned_from_afk", 
                True, 
                salience=0.95, # High salience to ensure it's noticed
                expiry_seconds=180 # The context is relevant for the next 3 minutes
            )
            self.logger.info("User return from AFK noted in attention focus.")

    def _handle_system_monitor(self, event: SystemMonitorEvent):
        """Gère les alertes du moniteur système."""
        self.logger.info(f"Handling SystemMonitorEvent: {event.metric} = {event.value}")
        # Cette information est déjà dans l'attention manager via le `_process_internal_state_update`.
        # La décision de notifier l'utilisateur sera prise par la logique proactive.
        # On pourrait ajouter ici des actions immédiates si un seuil critique est dépassé.
        pass

    def start(self):
        """Démarre le thread de l'orchestrateur."""
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._orchestration_loop, daemon=True)
            self._thread.start()
            self.logger.info("ConsciousnessOrchestrator thread started.")
        else:
            self.logger.warning("ConsciousnessOrchestrator thread is already running.")

    def stop(self):
        """Arrête le thread de l'orchestrateur."""
        self._stop_event.set()
        # On ajoute un événement factice pour débloquer la boucle si elle attend sur .get()
        VeraEventBus.put(BaseEvent()) 
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.logger.info("ConsciousnessOrchestrator stopped.")
