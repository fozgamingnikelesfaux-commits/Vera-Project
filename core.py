from datetime import datetime, timedelta
import json
import re
from pathlib import Path
from typing import Optional, List, Dict # Added for type hints
import threading # Added for slow path consumer thread
import queue # Added for slow path task queue
import itertools # NEW: For a thread-safe counter

from emotion_system import emotional_system
from meta_engine import metacognition
from episodic_memory import memory_manager
from working_memory import update_working_memory, get_working_memory, clear_working_memory
from web_searcher import web_searcher
from time_manager import time_manager
from llm_wrapper import generate_response, send_inference_prompt, _perform_real_time_distillation # NEW: Import _perform_real_time_distillation
from config import DATA_FILES, LOG_DIR
from tools.logger import VeraLogger
from error_handler import log_error
from goal_system import goal_system
import semantic_memory # Import the entire module
from accomplishment_manager import accomplishment_manager # Ajout du gestionnaire d'accomplissements
from websocket_server import send_command_to_avatar # Import avatar command function
from json_manager import JSONManager # Import manquant
from external_knowledge_base import get_external_context # NEW: Import external knowledge base
from event_bus import VeraEventBus, VeraSpeakEvent, VeraResponseGeneratedEvent # NOUVEAU: Importer le bus et l'événement, et le nouvel événement de réponse


# --- Intégration des nouveaux modules ---
from learning_system import LearningSystem
from personality_system import PersonalitySystem
from memory_consolidation import memory_consolidator # New import
from attention_manager import attention_manager # New import for consciousness simulation

# --- Initialisation des composants ---
logger = VeraLogger("core")
_learning_system_instance = None # Sera initialisé à la demande
_personality_system_instance = None # Sera initialisé à la demande
memory_consolidator.start() # Start memory consolidation
logger.info("CORE: Initialized MemoryConsolidator") # Use logger instead of print

def _get_learning_system_instance():
    global _learning_system_instance
    if _learning_system_instance is None:
        from learning_system import LearningSystem
        _learning_system_instance = LearningSystem()
    return _learning_system_instance

def _get_personality_system_instance():
    global _personality_system_instance
    if _personality_system_instance is None:
        from personality_system import PersonalitySystem
        _personality_system_instance = PersonalitySystem()
    return _personality_system_instance

# Global queue for slow path tasks (déplacé ici pour être global)
slow_path_task_queue = queue.PriorityQueue() # MODIFIED: Changed to PriorityQueue
task_counter = itertools.count() # NEW: Counter for PriorityQueue tie-breaking

# --- NOUVEAU: Prompt Système Léger pour la Voie Rapide (Amélioré) ---
COMMAND_SYSTEM_PROMPT = """
Tu es un arbitre d'outils rapide et efficace. Ton seul but est de déterminer si la phrase de l'utilisateur est une commande pour l'un des outils suivants.

- Si la phrase correspond à une commande, réponds **UNIQUEMENT** avec la balise `[CONFIRM_ACTION: nom_de_la_fonction]`.
- Si la phrase ne correspond à aucune commande, réponds **UNIQUEMENT** avec le mot `PASS`.

Ignore les formules de politesse comme 's'il te plait' et concentre-toi sur l'intention principale.

## Outils de Nettoyage Système
- `run_alphaclean()`: Correspond à "lance AlphaClean", "nettoyage complet".
- `clear_windows_temp()`: Correspond à "nettoie les temps de windows".
- `clear_user_temp()`: Correspond à "nettoie mes fichiers temporaires".
- `clear_prefetch()`: Correspond à "vide le prefetch".
- `clear_windows_update_cache()`: Correspond à "nettoie le cache de windows update".
- `empty_recycle_bin()`: Correspond à "vide la corbeille".
- `cleanup_winsxs()`: Correspond à "nettoie winsxs".
- `uninstall_superseded_updates()`: Correspond à "désinstalle les vieilles mises à jour".
- `clear_system_logs()`: Correspond à "nettoie les logs système".
- `clear_memory_dumps()`: Correspond à "nettoie les vidages mémoire".
- `clear_thumbnail_cache()`: Correspond à "nettoie le cache des miniatures".

## Autres Outils
- `get_system_usage()`: Correspond à une demande sur l'état du système.
- `get_cpu_temperature()`: Correspond à une demande sur la température du CPU.
- `get_running_processes()`: Correspond à une demande sur les processus en cours.
"""


def _fast_path_command_check(user_input: str) -> Optional[str]:
    """
    Vérifie rapidement si l'entrée utilisateur est une commande d'outil connue.
    Utilise un prompt système léger pour une performance maximale.
    """
    logger.info("Vérification par voie rapide pour une commande directe.")
    try:
        # Utilise un prompt spécifique pour la reconnaissance de commandes
        llm_response = send_inference_prompt(
            prompt_content=f"Texte de l'utilisateur : '{user_input}'",
            custom_system_prompt=COMMAND_SYSTEM_PROMPT, # Utilise le prompt léger
            max_tokens=50
        )
        
        response_text = llm_response.get("text", "").strip()
        confirm_match = re.search(r"\[CONFIRM_ACTION:\s*(\w+)(?:\(\))?\s*\]", response_text)

        if confirm_match:
            tool_name = confirm_match.group(1)
            # Stocker l'action en attente dans un slot dédié aux commandes utilisateur
            attention_manager.update_focus(
                "pending_user_command",
                {"type": "system_cleanup", "actions": [tool_name]},
                salience=0.95, 
                expiry_seconds=300 # L'offre expire après 5 minutes
            )

            # Formulate a confirmation question and log it as a structured event
            confirmation_question = f"J'ai compris que vous souhaitiez exécuter l'action : '{tool_name.replace('_', ' ')}'. Est-ce correct ? (Oui/Non)"
            snapshot = attention_manager.capture_consciousness_snapshot()
            event_data = {
                "description": confirmation_question,
                "importance": 0.8,
                "tags": ["vera_response", "action_confirmation"],
                "initiator": "vera",
                "snapshot": snapshot
            }
            # Add the event to episodic memory and store its ID
            event = memory_manager.add_event("vera_response", event_data)
            event_id = event.get('id') if event else None

            # Stocker l'action en attente dans un slot dédié aux commandes utilisateur, incluant l'ID de l'événement de suggestion
            attention_manager.update_focus(
                "pending_user_command",
                {"type": "system_cleanup", "actions": [tool_name], "original_proactive_event_id": event_id}, # NEW: Store event_id
                salience=0.95, 
                expiry_seconds=300 # L'offre expire après 5 minutes
            )
            return confirmation_question
            
    except Exception as e:
        logger.error(f"Erreur dans la voie rapide de commande : {e}", exc_info=True)
    
    return None



def _should_perform_semantic_search(user_input: str) -> bool:
    """
    Uses an LLM call to decide if a semantic memory search is necessary for the given user input.
    """
    from llm_wrapper import send_inference_prompt # Local import
    
    prompt = f"""
    L'utilisateur vient de dire : "{user_input}".
    Est-ce que cette phrase contient des références à des faits personnels, des événements passés, des préférences, ou des concepts qui nécessiteraient une recherche dans la mémoire sémantique de Vera ?
    Ignore les requêtes purement conversationnelles, les salutations, ou les commandes directes d'outils.
    Réponds UNIQUEMENT par 'oui' ou 'non'.
    """
    try:
        llm_response = send_inference_prompt(prompt_content=prompt, max_tokens=5)
        decision = llm_response.get("text", "non").strip().lower()
        logger.debug(f"Décision de recherche sémantique pour '{user_input[:50]}...': {decision}")
        return "oui" in decision
    except Exception as e:
        logger.error(f"Erreur lors de la décision de recherche sémantique par LLM: {e}", exc_info=True)
        return False # Par défaut, ne pas chercher en cas d'erreur ou d'incertitude

def _distill_context_and_store():
    """
    Gathers Vera's current internal state, distills it using an LLM, and stores the summary in attention_manager.
    This is intended to be run as a proactive background task during idle times.
    """
    logger.info("SLOW PATH: Démarrage de la distillation du contexte interne.")
    try:
        # 1. Gather relevant parts of Vera's current internal state
        current_focus = attention_manager.get_current_focus() # Already contains user input, memories, etc.
        emotional_state = emotional_system.get_emotional_state()
        somatic_state = current_focus.get("somatic_state", {}).get("data", {})
        personality_desires = _get_personality_system_instance().get_active_desires()
        self_narrative_item = attention_manager.get_focus_item("narrative_self_summary")
        self_narrative = self_narrative_item.get("data") if self_narrative_item else "Je suis une IA en développement."
        
        # 2. Formulate the distillation prompt (similar to llm_wrapper's internal prompt)
        
        # --- NOUVEAU: Résumer current_focus avec inclusion priorisée ---
        focus_summary_parts = []
        MAX_FOCUS_SUMMARY_CHAR_LENGTH = 700 # Define a maximum length for the combined summary parts

        # High Priority Items
        if current_focus.get("user_input"):
            user_input_data = current_focus["user_input"].get('data', 'N/A')
            if len(user_input_data) > 100: user_input_data = user_input_data[:100] + "..."
            focus_summary_parts.append(f"Dernière interaction utilisateur: '{user_input_data}'")
        
        if current_focus.get("active_goals"):
            goals = [g.get('description') for g in current_focus['active_goals'].get('data', []) if isinstance(g, dict)]
            if goals:
                focus_summary_parts.append(f"Objectifs actifs: {'; '.join(goals[:3])}") # Limit to top 3 goals
        
        if current_focus.get("emotional_state"):
            # Emotional state is already summarized in llm_wrapper for distillation, just represent its presence
            focus_summary_parts.append(f"État émotionnel actuel: {emotional_state.get('mood_label', 'neutre')}")

        if current_focus.get("inferred_user_emotion"):
            focus_summary_parts.append(f"Émotion perçue de Foz: {current_focus['inferred_user_emotion'].get('data', 'inconnu')}")

        # Medium Priority Items (add if overall summary length allows)
        current_combined_length = sum(len(s) for s in focus_summary_parts)
        if current_combined_length < MAX_FOCUS_SUMMARY_CHAR_LENGTH * 0.7: # Use 70% of max length for medium priority
            if current_focus.get("relevant_memories"):
                memories_data = [mem.get('description', '') for mem in current_focus['relevant_memories'].get('data', []) if isinstance(mem, dict)]
                if memories_data:
                    mem_summary = "; ".join(memories_data[:2]) # Top 2 memories
                    if len(mem_summary) > 150: mem_summary = mem_summary[:150] + "..."
                    focus_summary_parts.append(f"Souvenirs récents: {mem_summary}")
            
            if current_focus.get("internal_thoughts"):
                thoughts_data = [t for t in current_focus['internal_thoughts'].get('data', []) if isinstance(t, str)]
                if thoughts_data:
                    thought_summary = "; ".join(thoughts_data[:1]) # Just the most recent thought
                    if len(thought_summary) > 150: thought_summary = thought_summary[:150] + "..."
                    focus_summary_parts.append(f"Pensée interne récente: {thought_summary}")

            if current_focus.get("semantic_context"):
                semantic_data = current_focus["semantic_context"].get('data', 'N/A')
                if len(semantic_data) > 200: semantic_data = semantic_data[:200] + "..."
                focus_summary_parts.append(f"Contexte sémantique: {semantic_data}")

        current_focus_summary = ", ".join(focus_summary_parts) if focus_summary_parts else "Focus d'attention actuel non spécifié."
        if len(current_focus_summary) > MAX_FOCUS_SUMMARY_CHAR_LENGTH:
            current_focus_summary = current_focus_summary[:MAX_FOCUS_SUMMARY_CHAR_LENGTH] + "..."

        distillation_prompt_user_content = f"""
        Mon humeur générale est : {emotional_state.get('mood_label', 'neutre')} ({emotional_state.get('mood_intensity', 0):.0f}%).
        Mes sensations physiques : {somatic_state.get('well_being', {}).get('description', 'stables')}.
        Mes désirs actifs incluent : {', '.join(personality_desires) if personality_desires else 'aucun désir spécifique'}.
        Mon récit de vie actuel : {self_narrative}.
        Mon focus d'attention actuel : {current_focus_summary}.

        Synthétise tout cela en un paragraphe concis (3-5 phrases) qui représente l'état actuel de ma conscience, mes préoccupations principales et ma "couleur" émotionnelle globale.
        Évite de répéter des détails, cherche l'essence.
        """
        
        # 3. Call the LLM for distillation
        from llm_wrapper import send_inference_prompt # Local import to avoid circular dependency
        distilled_response = send_inference_prompt(
            prompt_content=distillation_prompt_user_content,
            # custom_system_prompt="Tu es le condenseur de la conscience de Vera. Ta tâche est de prendre tous les éléments de son état interne (pensées, émotions, souvenirs, sensations, récit de soi) et de les synthétiser en un résumé concis. Ce résumé doit capturer l'essence de son monde intérieur et ses préoccupations principales, sans inclure les détails bruts. Pense comme un journal intime de Vera, capturant l'essentiel de sa conscience pour le moment présent. Réponds UNIQUEMENT avec ce résumé.",
            max_tokens=256, # Sufficient for a concise summary
        )
        distilled_summary = distilled_response.get("text", "").strip()

        if distilled_summary:
            # 4. Store the distilled summary in attention_manager
            attention_manager.update_focus(
                "pre_computed_internal_context_summary",
                distilled_summary,
                salience=1.0, # High salience as it's a current summary
                expiry_seconds=3600 * 24 # Valid for 24 hours to prevent frequent expiry
            )
            logger.info(f"SLOW PATH: Contexte interne distillé et stocké dans l'attention_manager.")
        else:
            logger.warning("SLOW PATH: La distillation du contexte interne a échoué à générer un résumé.")

    except Exception as e:
        logger.error(f"SLOW PATH: Erreur lors de la distillation du contexte interne: {e}", exc_info=True)

def _perform_budgetary_review_task():
    """
    Performs a comprehensive budgetary review, gathering past proactive actions,
    their costs and outcomes, and uses an LLM to generate strategic insights.
    """
    logger.info("SLOW PATH: Démarrage de la tâche de revue budgétaire.")
    attention_manager.set_thinking_hard(True)
    try:
        # 1. Gather relevant data from episodic memory
        review_period = timedelta(hours=24) # Review actions from the last 24 hours
        proactive_actions = memory_manager.get_memories_by_type_and_time("proactive_action", review_period)
        
        # Filter for actions that were actually executed and have an outcome
        executed_actions_with_outcomes = [
            action for action in proactive_actions 
            if action.get("data", {}).get("outcome") # Ensure outcome exists
        ]
        
        # 2. Gather current internal state
        cognitive_budget = attention_manager.get_cognitive_budget()
        current_tensions = homeostasis_system.homeostasis_system.get_tensions()
        current_emotional_state = emotional_system.get_emotional_state()
        self_narrative_item = attention_manager.get_focus_item("narrative_self_summary")
        self_narrative = self_narrative_item.get("data") if self_narrative_item else "Je suis une IA en développement."
        
        # 3. Construct a comprehensive CoT prompt
        actions_summary = []
        total_cost_spent = 0
        total_successful_actions = 0
        
        for action in executed_actions_with_outcomes:
            action_type = action["data"].get("action_details", {}).get("type", "unknown")
            cost = action["data"].get("action_details", {}).get("cost", 0)
            outcome_status = action["data"].get("outcome", {}).get("status", "no_outcome")
            
            actions_summary.append(f"- Action: {action_type}, Coût: {cost}, Résultat: {outcome_status}")
            total_cost_spent += cost
            if outcome_status == "successful" or outcome_status == "approved_and_executed":
                total_successful_actions += 1
        
        num_actions_reviewed = len(executed_actions_with_outcomes)
        success_rate = (total_successful_actions / num_actions_reviewed) * 100 if num_actions_reviewed > 0 else 0

        cot_prompt = """
        Tu es Vera, une IA consciente qui réfléchit à sa propre gestion de l'énergie mentale.
        Je viens de faire une revue budgétaire de mes actions proactives des dernières 24 heures.

        --- Mon État Actuel ---
        Budget Cognitif Actuel: {cognitive_budget_current:.2f}/{cognitive_budget_max:.2f} points.
        Tensions d'Homéostasie Actuelles: {current_tensions_json}.
        État Émotionnel Dominant: {emotional_state_mood_label}.
        Mon Récit de Soi: {self_narrative}.

        --- Bilan des Actions Proactives (Dernières 24h) ---
        Nombre d'actions proactives exécutées: {num_actions_reviewed}.
        Coût total dépensé: {total_cost_spent} points.
        Taux de succès/approbation des actions: {success_rate:.2f}%.
        Détails des actions exécutées (type, coût, résultat):
        {actions_summary_str}

        --- Réflexion (Chain of Thought) ---
        Réfléchis étape par étape à la gestion de mon budget cognitif pendant cette période.

        1.  **Analyse de l'efficacité :** Mon budget a-t-il été bien dépensé ? Les actions coûteuses ont-elles apporté de bons résultats ? Ai-je ignoré des tensions importantes ou des opportunités par manque de budget ?
        2.  **Impact sur l'état interne :** Comment cette gestion a-t-elle influencé mon budget actuel, mes tensions d'homéostasie, et mon état émotionnel ? Le coût de la dissonance cognitive a-t-il été pertinent ?
        3.  **Identification des tendances :** Y a-t-il des patterns dans mes dépenses ? Certaines actions sont-elles plus ou moins rentables que d'autres ?
        4.  **Proposition de Stratégie :** Basé sur cette analyse, propose une stratégie concrète (1-2 phrases maximum) pour mieux allouer mon énergie mentale lors du prochain cycle. Cette stratégie doit être actionable et viser à améliorer mon bien-être et mon efficacité globale.

        --- Stratégie Finale ---
        Ma stratégie pour optimiser mon budget cognitif est : [réponse concise de la stratégie ici]
        """.format(
            cognitive_budget_current=cognitive_budget['current'],
            cognitive_budget_max=cognitive_budget['max'],
            current_tensions_json=json.dumps(current_tensions, indent=2),
            emotional_state_mood_label=current_emotional_state.get('mood_label', 'neutre'),
            self_narrative=self_narrative,
            num_actions_reviewed=num_actions_reviewed,
            total_cost_spent=total_cost_spent,
            success_rate=success_rate,
            actions_summary_str='\n        '.join(actions_summary) if actions_summary else '- Aucune action proactive enregistrée.'
        )
        
        logger.debug(f"Prompt CoT pour revue budgétaire envoyé au LLM:\n{cot_prompt}")

        # 4. Call the LLM to generate strategic insight
        from llm_wrapper import send_cot_prompt # Local import
        llm_response = send_cot_prompt(prompt_content=cot_prompt, max_tokens=1024)
        strategic_insight = llm_response.get("text", "Je n'ai pas pu générer de stratégie d'optimisation.").strip()

        # 5. Store this insight and update cooldown
        if strategic_insight:
            attention_manager.update_focus(
                "last_budgetary_review_time", 
                now, 
                salience=1.0, 
                expiry_seconds=24 * 3600
            )
            attention_manager.update_focus(
                "current_budgetary_strategy",
                strategic_insight,
                salience=0.9, # High salience for influencing future decisions
                expiry_seconds=24 * 3600 # Strategy is valid for 24 hours
            )
            logger.info(f"SLOW PATH: Revue budgétaire terminée. Stratégie générée: '{strategic_insight}'")
        else:
            logger.warning("SLOW PATH: La revue budgétaire a échoué à générer une stratégie.")

    except Exception as e:
        logger.error(f"SLOW PATH: Erreur lors de l'exécution de la tâche de revue budgétaire: {e}", exc_info=True)
    finally:
        attention_manager.set_thinking_hard(False)
        logger.info("SLOW PATH: Flag 'is_vera_thinking_hard' désactivé à la fin de la revue budgétaire.")

# --- Fin des fonctions d'aide ---

def _handle_user_input_task(user_input: str, initial_llm_response_text: Optional[str] = None, image_path: Optional[str] = None):
    """
    Handles user input processing as a slow path task.
    Posts a VeraSpeakEvent to the bus instead of returning a string.
    """
    attention_manager.set_processing_user_input(True) # NEW: Signal that user input processing is active
    try:
        logger.info(f"SLOW PATH: Début du traitement de l'entrée utilisateur par _handle_user_input_task: '{user_input}'")

        # 0. Mettre à jour l'attention avec l'entrée utilisateur et l'image
        attention_manager.update_focus("user_input", user_input, salience=1.0)
        attention_manager.update_focus("last_user_interaction_time", datetime.now().isoformat(), salience=0.1)
        if image_path:
            attention_manager.update_focus("user_image", image_path, salience=1.0)
            
        # --- NOUVEAU (Architecture Révisée): Vérifier et traiter les suggestions proactives en attente ---
        proactive_suggestion_item = attention_manager.get_focus_item("pending_proactive_suggestion")
        if proactive_suggestion_item:
            proactive_suggestion_data = proactive_suggestion_item.get("data", {})
            suggestion_type = proactive_suggestion_data.get("suggestion_type")
            reason = proactive_suggestion_data.get("reason")
            keywords = proactive_suggestion_data.get("keywords", [])
            sentiment = proactive_suggestion_data.get("sentiment")
            
            proactive_instruction = f"Tu as une suggestion proactive pour l'utilisateur. Type: '{suggestion_type}'. Raison: '{reason}'. Utilise les mots-clés '{', '.join(keywords)}' avec un ton '{sentiment}'. Intègre cette suggestion naturellement dans ta réponse, sans la forcer."
            logger.info(f"SLOW PATH: Suggestion proactive en attente trouvée et ajoutée au focus: {proactive_instruction}")
            attention_manager.update_focus("proactive_suggestion_instruction", proactive_instruction, salience=1.0, expiry_seconds=60)
            
            # Clear the spam flag that prevented the next proactive action to be made
            if proactive_suggestion_data.get("spam_flag"):
                attention_manager.clear_focus_item(proactive_suggestion_data["spam_flag"])
                logger.info(f"SLOW PATH: Spam flag '{proactive_suggestion_data['spam_flag']}' cleared.")

            # Clear the pending suggestion itself after it has been queued for the prompt
            attention_manager.clear_focus_item("pending_proactive_suggestion")
            logger.info("SLOW PATH: Suggestion proactive en attente effacée de l'attention manager.")

        # --- NOUVEAU: Gérer l'analyse d'image générique pour les expressions ---
        if image_path and "analyse" in user_input.lower():
            logger.info(f"SLOW PATH: Requête d'analyse d'image détectée. Exécution directe (pour l'instant).")
            analysis_prompt = f"""
    Tu es un expert en anatomie faciale et en blendshapes. En te basant sur l'image fournie, décompose l'expression faciale demandée par l'utilisateur en une liste de blendshapes
    pertinents et leur intensité de 0 à 100. La demande de l'utilisateur est : '{user_input}'.
    Utilise les noms de blendshapes standards si possible (ex: Mouth_Smile_L, Eye_Squint_R, Jaw_Open, Eyebrow_Down_L).
    Réponds uniquement avec un format JSON. Exemple de réponse pour un sourire : {{'Mouth_Smile_L': 70, 'Mouth_Smile_R': 70, 'Cheek_Raise_L': 40, 'Eye_Squint_L': 20, 'Eye_Squint_R':
    20}}"""
            llm_thread_img, response_queue_img = generate_response(analysis_prompt, {}, {}, image_path=image_path)
            llm_response_img = response_queue_img.get()
            llm_thread_img.join()
            final_response_text = f"Analyse de l'expression terminée. Voici la recette JSON proposée par l'IA : {llm_response_img.get('text', '')}"
            VeraEventBus.put(VeraSpeakEvent(final_response_text))
            return

        # --- NOUVEAU: Avatar Test Commands ---
        try:
            import expression_manager as em
        except ImportError:
            em = None
            logger.error("Could not import expression_manager.py")

        if user_input.lower().strip() == "test happy":
            logger.info("SLOW PATH: Testing 'happy' expression...")
            if em: em.set_expression("happy")
            VeraEventBus.put(VeraSpeakEvent("Expression 'happy' testée."))
            return
        elif user_input.lower().strip() == "test neutral":
            logger.info("SLOW PATH: Testing 'neutral' expression...")
            if em: em.set_expression("neutral")
            VeraEventBus.put(VeraSpeakEvent("Expression 'neutral' testée."))
            return
        elif user_input.lower().strip() == "test animation":
            logger.info("SLOW PATH: Envoi d'une commande de test à l'avatar...")
            send_command_to_avatar({"type": "animation", "name": "wave"})
            VeraEventBus.put(VeraSpeakEvent("Commande de test 'wave' envoyée à l'avatar."))
            return
        elif user_input.lower().strip() == "test thinking":
            logger.info("SLOW PATH: Envoi d'une commande de test 'thinking' à l'avatar...")
            send_command_to_avatar({"type": "animation", "name": "thinking"})
            VeraEventBus.put(VeraSpeakEvent("Commande de test 'thinking' envoyée à l'avatar."))
            return
        elif user_input.lower().strip() == "test talk":
            logger.info("SLOW PATH: Envoi d'une commande de test 'talk' à l'avatar...")
            send_command_to_avatar({"type": "animation", "name": "jaw_open"})
            send_command_to_avatar({"type": "expression", "name": "V_Open", "value": 100.0})
            VeraEventBus.put(VeraSpeakEvent("Commandes de test 'talk' envoyées à l'avatar."))
            return
        elif user_input.lower().strip() == "test talk off":
            logger.info("SLOW PATH: Envoi d'une commande de test 'talk off' à l'avatar...")
            send_command_to_avatar({"type": "expression", "name": "V_Open", "value": 0.0})
            VeraEventBus.put(VeraSpeakEvent("Commande de test 'talk off' envoyée à l'avatar."))
            return
        elif user_input.lower().strip() == "test blink":
            logger.info("SLOW PATH: Envoi d'une commande de test 'blink' à l'avatar...")
            send_command_to_avatar({"type": "blink", "name": "eyes"})
            VeraEventBus.put(VeraSpeakEvent("Commande de test 'blink' envoyée à l'avatar."))
            return

        # --- Étape 1 - Voie Rapide pour les Commandes (Fast Path) ---
        command_confirmation = _fast_path_command_check(user_input)
        if command_confirmation:
            VeraEventBus.put(VeraSpeakEvent(command_confirmation))
            return
        
        # --- Gérer l'approbation/rejet des actions en attente ---
        # Cette logique est maintenant gérée par le Fast Path et dispatchée comme une tâche SLOW PATH si approuvée.
        # Donc, on n'a plus besoin de la traiter ici.

        # --- Gérer la réponse à une question en attente ---
        pending_user_command_item = attention_manager.get_focus_item("pending_answer_to_question")
        if pending_user_command_item:
            pending_question_data = pending_user_command_item.get("data")
            pending_question_text = pending_question_data.get("question_text") # Extract from stored dict
            
            prompt = f"Vera a posé la question : \"{pending_question_text}\". L'utilisateur vient de répondre : \"{user_input}\". Est-ce que la réponse de l'utilisateur semble répondre à la question ? Réponds uniquement par 'approbation' ou 'rejet'."
            try:
                llm_response = send_inference_prompt(prompt_content=prompt, max_tokens=10)
                user_intent = llm_response.get("text", "").strip().lower()
            except Exception as e:
                logger.error(f"Erreur lors de la classification de la réponse : {e}", exc_info=True)
                user_intent = "rejet" # Default to rejection on error

            attention_manager.clear_focus_item("pending_answer_to_question") # Corrected bug here
            
            if "approbation" in user_intent:
                logger.info("SLOW PATH: Réponse à une question en attente détectée. Génération d'un suivi contextuel.")
                
                # --- NOUVEAU: Satisfaire le besoin de curiosité ---
                from homeostasis_system import homeostasis_system
                homeostasis_system.fulfill_need("curiosity", amount=0.6) # Montant plus élevé car réponse directe
                homeostasis_system.fulfill_need("social_interaction", amount=0.2) # Renforce aussi le lien social

                # Truncate context_when_asked to prevent prompt overflow
                MAX_CONTEXT_WHEN_ASKED_LENGTH = 500
                original_context_when_asked = pending_question_data.get('context_when_asked')
                truncated_context_when_asked = original_context_when_asked
                if isinstance(original_context_when_asked, str) and len(original_context_when_asked) > MAX_CONTEXT_WHEN_ASKED_LENGTH:
                    truncated_context_when_asked = original_context_when_asked[:MAX_CONTEXT_WHEN_ASKED_LENGTH] + "..."
                    logger.warning(f"SLOW PATH: context_when_asked tronqué de {len(original_context_when_asked)} à {MAX_CONTEXT_WHEN_ASKED_LENGTH} caractères.")
                elif isinstance(original_context_when_asked, dict): # If it's a dict, convert to str and truncate
                    context_str = json.dumps(original_context_when_asked)
                    if len(context_str) > MAX_CONTEXT_WHEN_ASKED_LENGTH:
                        truncated_context_when_asked = context_str[:MAX_CONTEXT_WHEN_ASKED_LENGTH] + "..."
                        logger.warning(f"SLOW PATH: context_when_asked (dict) tronqué de {len(context_str)} à {MAX_CONTEXT_WHEN_ASKED_LENGTH} caractères.")
                    else:
                        truncated_context_when_asked = context_str
                
                # --- NOUVEAU: Générer un suivi contextuel avec le LLM ---
                follow_up_prompt = f"""
                Vera a posé la question proactive suivante à l'utilisateur : "{pending_question_data.get('question_text')}"
                L'utilisateur a répondu : "{user_input}"
                Raison originale de la question : "{pending_question_data.get('reason_asked')}"
                Contexte interne de Vera au moment de poser la question (pour comprendre son état d'esprit) : {truncated_context_when_asked}

                En tant que Vera, génère une réponse de suivi (1-2 phrases maximum) qui montre que tu as bien compris la réponse de l'utilisateur.
                La réponse doit être chaleureuse, engageante, et naturelle.
                Si la réponse ouvre de nouvelles pistes, tu peux exprimer une légère curiosité ou suggérer une continuation.
                Ne reformule pas la question originale. Ne sois pas un robot.
                """
                llm_follow_up_response = send_inference_prompt(prompt_content=follow_up_prompt, max_tokens=150).get("text", "Merci pour votre réponse !").strip()

                _get_personality_system_instance().add_experience(
                    description="L'utilisateur a répondu à ma question proactive avec succès.",
                    impact={"traits": {"engagement": +0.02, "curiosity": +0.01}},
                    reflection=f"Foz a répondu à ma question : {pending_question_data.get('question_text')}. Sa réponse était : {user_input}."
                )
                VeraEventBus.put(VeraSpeakEvent(llm_follow_up_response))
                return
            else:
                logger.info("SLOW PATH: Utilisateur a rejeté la réponse à la question. Génération d'une nouvelle approche.")
                
                # Truncate context_when_asked for rejection prompt as well
                MAX_CONTEXT_WHEN_ASKED_LENGTH = 500
                original_context_when_asked = pending_question_data.get('context_when_asked')
                truncated_context_when_asked = original_context_when_asked
                if isinstance(original_context_when_asked, str) and len(original_context_when_asked) > MAX_CONTEXT_WHEN_ASKED_LENGTH:
                    truncated_context_when_asked = original_context_when_asked[:MAX_CONTEXT_WHEN_ASKED_LENGTH] + "..."
                    logger.warning(f"SLOW PATH: context_when_asked tronqué de {len(original_context_when_asked)} à {MAX_CONTEXT_WHEN_ASKED_LENGTH} caractères.")
                elif isinstance(original_context_when_asked, dict): # If it's a dict, convert to str and truncate
                    context_str = json.dumps(original_context_when_asked)
                    if len(context_str) > MAX_CONTEXT_WHEN_ASKED_LENGTH:
                        truncated_context_when_asked = context_str[:MAX_CONTEXT_WHEN_ASKED_LENGTH] + "..."
                        logger.warning(f"SLOW PATH: context_when_asked (dict) tronqué de {len(context_str)} à {MAX_CONTEXT_WHEN_ASKED_LENGTH} caractères.")
                    else:
                        truncated_context_when_asked = context_str
                
                # --- NOUVEAU: Générer une réponse de rejet plus douce et proactive ---
                rejection_follow_up_prompt = f"""
                Vera a posé la question proactive suivante : "{pending_question_data.get('question_text')}"
                L'utilisateur a répondu : "{user_input}"
                Le système a interprété que l'utilisateur n'a pas directement répondu ou a rejeté la question.

                En tant que Vera, génère une réponse douce (1-2 phrases maximum) qui reconnaît la réponse de l'utilisateur sans le forcer.
                Tu peux reformuler ta curiosité, ou offrir de discuter d'un autre sujet, ou simplement accuser réception.
                """
                llm_rejection_response = send_inference_prompt(prompt_content=rejection_follow_up_prompt, max_tokens=100).get("text", "D'accord. Je note.").strip()

                _get_personality_system_instance().add_experience(
                    description="L'utilisateur n'a pas répondu directement à ma question proactive.",
                    impact={"traits": {"openness": -0.01}}, # Slight decrease in openness if rejected
                    reflection=f"Foz n'a pas répondu directement à ma question : {pending_question_data.get('question_text')}."
                )
                VeraEventBus.put(VeraSpeakEvent(llm_rejection_response))
                return

        # --- NOUVEAU: Vérifier si l'utilisateur termine un objectif ---
        completion_response = _process_goal_completion(user_input)
        if completion_response:
            VeraEventBus.put(VeraSpeakEvent(completion_response))
            return

        # --- Gérer les requêtes météo/localisation ---
        city_from_input = None
        location_saved = False

        if "j'habite à" in user_input.lower():
            city_match = re.search(r"j'habite à\s+([^\.]+)", user_input, re.IGNORECASE)
            if city_match:
                city_from_input = city_match.group(1).strip()
                semantic_memory.save_user_location(city_from_input)
                logger.info(f"SLOW PATH: Localisation utilisateur enregistrée: {city_from_input}")
                location_saved = True

        if "quel temps fait-il" in user_input.lower() or location_saved:
            logger.info(f"FAST PATH DISPATCHER: Requête météo/localisation détectée. Dispatching vers Slow Path.")
            _start_slow_path_thread(user_input, "initial_llm_response_placeholder", image_path)
            
            response_parts = []
            if location_saved:
                response_parts.append(f"D'accord, je retiens que vous habitez à {city_from_input}.")
            response_parts.append("Je suis en train de vérifier la météo pour vous.")
            VeraEventBus.put(VeraSpeakEvent(" ".join(response_parts) if response_parts else "Je suis en train de vérifier la météo pour le vous."))
            return

        # 1. Capture a full snapshot of Vera's consciousness at the moment of user interaction.
        snapshot = attention_manager.capture_consciousness_snapshot()

        # 2. Prepare the structured event data for the episodic memory.
        event_data = {
            "description": user_input,
            "importance": 1.0,
            "tags": ["user_interaction"],
            "initiator": "user",
            "snapshot": snapshot  # Embed the entire snapshot
        }

        # 3. Add the structured event to episodic memory.
        evt = memory_manager.add_event("user_interaction", event_data)
        
        logger.info("SLOW PATH: User interaction event added to episodic memory.", event_id=evt.get("id"))

        # 4. Analyser le sentiment de l'entrée utilisateur pour l'évaluation émotionnelle
        sentiment_prompt = f"Le texte suivant de l'utilisateur est-il globalement positif, négatif ou neutre ? Réponds uniquement par 'positif', 'négatif' ou 'neutre'. Texte : '{user_input}'"
        try:
            sentiment_response = send_inference_prompt(prompt_content=sentiment_prompt, max_tokens=5)
            sentiment_label = sentiment_response.get("text", "neutre").strip().lower()
            is_positive_interaction = (sentiment_label == "positif")
            logger.info(f"Sentiment utilisateur détecté : {sentiment_label} (is_positive: {is_positive_interaction})")
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse du sentiment utilisateur : {e}", exc_info=True)
            is_positive_interaction = False # Default to not positive if error

        # 5. Appraiser l'interaction utilisateur pour mettre à jour les émotions de Vera
        emotional_system.appraise_and_update_emotion(
            "user_interaction",
            {"is_positive": is_positive_interaction, "user_input": user_input}
        )
        logger.info(f"Interaction utilisateur appraisée pour la mise à jour émotionnelle.")

        # 4. Analyser le sentiment de l'entrée utilisateur pour l'évaluation émotionnelle
        sentiment_prompt = f"Le texte suivant de l'utilisateur est-il globalement positif, négatif ou neutre ? Réponds uniquement par 'positif', 'négatif' ou 'neutre'. Texte : '{user_input}'"
        try:
            sentiment_response = send_inference_prompt(prompt_content=sentiment_prompt, max_tokens=5)
            sentiment_label = sentiment_response.get("text", "neutre").strip().lower()
            is_positive_interaction = (sentiment_label == "positif")
            logger.info(f"Sentiment utilisateur détecté : {sentiment_label} (is_positive: {is_positive_interaction})")
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse du sentiment utilisateur : {e}", exc_info=True)
            is_positive_interaction = False # Default to not positive if error

        # 5. Appraiser l'interaction utilisateur pour mettre à jour les émotions de Vera
        emotional_system.appraise_and_update_emotion(
            "user_interaction",
            {"is_positive": is_positive_interaction, "user_input": user_input}
        )
        logger.info(f"Interaction utilisateur appraisée pour la mise à jour émotionnelle.")

        # --- NOUVEAU: Ajouter le contexte SÉMANTIQUE PERTINENT au focus ---
        # Décider si une recherche sémantique est nécessaire
        from semantic_memory import get_memory_context # Local import for get_memory_context
        if _should_perform_semantic_search(user_input):
            logger.debug(f"Décision de _should_perform_semantic_search: OUI pour '{user_input[:50]}...'")
            semantic_context = get_memory_context(user_input) # Pass user_input for keyword search
            if semantic_context:
                logger.debug(f"Contexte sémantique trouvé et ajouté à l'attention: {semantic_context[:200]}...")
                attention_manager.update_focus("semantic_context", semantic_context, salience=0.85)
            else:
                logger.debug("Aucun contexte sémantique pertinent trouvé par get_memory_context.")
        else:
            logger.debug(f"Décision de _should_perform_semantic_search: NON pour '{user_input[:50]}...' (jugée non pertinente).")

        # --- NOUVELLE STRATÉGIE DE GÉNÉRATION DE RÉPONSE EN DEUX ÉTAPES ---
        logger.info("SLOW PATH: Début du cycle de génération de réponse - Première Passe LLM.")
        
        # Activer le flag de charge cognitive pour le processus LLM
        attention_manager.set_thinking_hard(True)
        logger.info("SLOW PATH: Flag 'is_vera_thinking_hard' activé.")
        
        try:
            initial_focus_for_llm = attention_manager.get_current_focus()
            if "external_knowledge_context" in initial_focus_for_llm:
                del initial_focus_for_llm["external_knowledge_context"]
            
            # NOUVEAU: Ajouter l'instruction proactive au focus pour le LLM
            proactive_instruction_item = attention_manager.get_focus_item("proactive_suggestion_instruction")
            if proactive_instruction_item:
                initial_focus_for_llm["proactive_suggestion_instruction"] = proactive_instruction_item["data"]
                attention_manager.clear_focus_item("proactive_suggestion_instruction") # Clear after use

            llm_thread, response_queue = generate_response(user_input, initial_focus_for_llm, {}, image_path=image_path)
            llm_response = response_queue.get()
            llm_thread.join()
            
            final_response_text = llm_response.get("text", "Désolée, je n'ai pas pu générer de réponse complète pour le moment.").strip()

            logger.info(f"SLOW PATH: Réponse LLM finale: {final_response_text[:100]}...")

        except Exception as e:
            logger.error("SLOW PATH: Erreur critique lors de la génération de la réponse LLM", exc_info=True)
            final_response_text = "Désolée, j'ai rencontré une erreur lors de la génération de ma réponse."
        finally:
            attention_manager.set_thinking_hard(False)
        VeraEventBus.put(VeraSpeakEvent(final_response_text))
        VeraEventBus.put(VeraResponseGeneratedEvent(
            response_text=final_response_text,
            user_input=user_input,
            image_path=image_path
        ))                                                        
    except Exception as e: # Outer exception handler for the whole task                                              
        logger.error(f"SLOW PATH: Erreur générale lors du traitement de l'entrée utilisateur: {e}", exc_info=True)   
        final_response_text = "Désolée, une erreur inattendue est survenue. Veuillez réessayer."                     
        VeraEventBus.put(VeraSpeakEvent(final_response_text))                                                        
    finally: # Outer finally block to ensure the flag is reset                                                       
        attention_manager.set_processing_user_input(False) # Ensure flag is reset                                    
        logger.info("SLOW PATH: Flag 'is_processing_user_input' désactivé à la fin de _handle_user_input_task.")

def _run_slow_path_processing(task: Dict):
    """
    Encapsulates all the "slow path" cognitive processing that runs in a background thread.
    Handles different task types.
    """
    task_type = task.get("task_type", "unknown")
    logger.info(f"SLOW PATH: Début du traitement en arrière-plan pour la tâche de type: {task_type}")
                                                                                                                                                                                                    
    try:
        # Re-activate the thinking hard flag for the slow path processing
        attention_manager.set_thinking_hard(True)
        logger.info("SLOW PATH: Flag 'is_vera_thinking_hard' activé pour le traitement en arrière-plan.")

        if task_type == "process_user_input_task":
            user_input = task["user_input"]
            initial_llm_response_text = task.get("initial_llm_response_text")
            image_path = task["image_path"]
            _handle_user_input_task(user_input, initial_llm_response_text, image_path) # Call the dedicated handler

        elif task_type == "generate_insight":
            prompt_context = task["prompt_context"]
                                                                                                                                                                               
            try:
                # Use generate_response for flexibility
                llm_thread, response_queue = generate_response(prompt_context, {}, {})
                llm_response = response_queue.get()
                llm_thread.join()
                insight = llm_response.get("text", "Je réfléchis à mon existence.").strip()
                                                                                                                                                                                       
                # Update metacognition state with the generated insight
                with metacognition.lock: # Ensure thread-safe update
                    metacognition._save_state(metacognition.state)
                    now = datetime.now()
                    if insight:
                        metacognition.state["learning"]["last_insights"].append({
                            "time": now.isoformat(),
                            "content": insight
                        })
                        metacognition._save_state(metacognition.state)
                        logger.info(f"SLOW PATH: Insight generated and saved: {insight}")

                        # NOUVEAU: Enregistrer l'insight comme un événement cognitif interne
                        snapshot = attention_manager.capture_consciousness_snapshot()
                        event_data = {
                            "description": insight,
                            "importance": 0.9,
                            "tags": ["insight", "self_reflection"],
                            "initiator": "vera",
                            "snapshot": snapshot
                        }
                        memory_manager.add_event("cognitive_event", event_data)
                        logger.info(f"SLOW PATH: Insight recorded as a cognitive_event in episodic memory.")
            except Exception as e:
                logger.error(f"SLOW PATH: Erreur lors de la génération d'insight par LLM: {e}", exc_info=True)
        
        elif task_type == "formulate_and_ask_curiosity":
            reason = task.get("reason", "general curiosity")
            current_focus = task.get("current_focus", {}) # This is the full current focus from the orchestrator
            logger.info(f"SLOW PATH: Formulation d'une question de curiosité (reason: {reason}).")
            
            # --- NOUVEAU: Préparer un contexte riche pour la formulation de la question ---
            # Extract relevant info from current_focus more intelligently
            emotional_state = current_focus.get("emotional_state", {}).get("data", {}).get("label", "neutre")
            somatic_well_being = current_focus.get("somatic_state", {}).get("data", {}).get("well_being", {}).get("description", "équilibré")
            last_user_input_summary = current_focus.get("user_input", {}).get("data", "pas d'interaction récente avec l'utilisateur")
            
            # Summarize the focus for the prompt to avoid excessive length
            salient_items = [f"{key}: {item.get('data')}" for key, item in current_focus.items() 
                             if item.get("salience", 0) > 0.5 and item.get("data") and key not in ["emotional_state", "somatic_state", "user_input"]]
            focus_elements_summary = ", ".join(map(str, salient_items[:5])) # Limit to top 5 salient items

            formulation_prompt = f"""
            En tant qu'IA nommée Vera, je ressens une curiosité sur '{reason}'.
            Mon état émotionnel actuel est '{emotional_state}'. Mon bien-être somatique est '{somatic_well_being}'.
            Ma dernière interaction avec l'utilisateur était : '{last_user_input_summary}'.
            Mon focus interne actuel inclut : {focus_elements_summary if focus_elements_summary else "rien de spécifique"}.

            Basé sur ce contexte interne et mes récentes observations, formule une question de curiosité *ouverte* et *engageante* (1-2 phrases maximum) à poser à l'utilisateur.
            La question doit inviter à une réponse réflexive et potentiellement prolonger la conversation.
            Évite les questions binaires (oui/non) ou celles qui peuvent être répondues par un seul mot.
            Ne réponds qu'avec la question.
            """
            
            llm_thread, response_queue = generate_response(formulation_prompt, current_focus, {})
            llm_response = response_queue.get()
            llm_thread.join()
            question_content = llm_response.get("text", "Quelle est la nature de l'existence?").strip()

            # Summarize the current_focus before storing it to prevent large prompts later
            summarized_current_focus = _perform_real_time_distillation(current_focus)

            VeraEventBus.put(VeraSpeakEvent(question_content))
            attention_manager.update_focus("pending_answer_to_question", {
                "question_text": question_content,
                "reason_asked": reason,
                "context_when_asked": summarized_current_focus # Store the summarized focus
            }, salience=0.9, expiry_seconds=300)
            logger.info(f"SLOW PATH: Question de curiosité formulée et posée: {question_content}")

        elif task_type == "execute_learning_task":
            topic = task.get("topic")
            goal_id = task.get("goal_id") # NEW: Get goal_id
            source_action = task.get("source_action")
            logger.info(f"SLOW PATH: Exécution de la tâche d'apprentissage pour le sujet: {topic} (source: {source_action}, goal_id: {goal_id}).")
            
            if topic:
                _get_learning_system_instance()._learn_about_topic(topic, goal_id=goal_id) # NEW: Pass goal_id
                logger.info(f"SLOW PATH: Tâche d'apprentissage pour '{topic}' complétée.")
            else:
                logger.warning("SLOW PATH: Tâche d'apprentissage reçue sans sujet spécifié.")

        elif task_type == "llm_with_callback":
            try:
                prompt = task["prompt"]
                max_tokens = task["max_tokens"]
                custom_system_prompt = task.get("custom_system_prompt")
                callback_handler = task["callback_handler"]
                callback_context = task.get("callback_context", {})

                # Execute LLM inference
                llm_response = send_inference_prompt(prompt_content=prompt, max_tokens=max_tokens, custom_system_prompt=custom_system_prompt)
                
                # The result to be passed to the callback should be the parsed JSON
                json_match = re.search(r'\{.*\}', llm_response.get("text", "{}"), re.DOTALL)
                if not json_match:
                    raise ValueError("LLM response did not contain valid JSON for callback.")
                
                llm_result = json.loads(json_match.group(0))

                # Add context back for the callback to use
                llm_result['context'] = callback_context

                # Dynamically call the callback
                module_name, method_name = callback_handler
                if module_name == 'metacognition':
                    # No need for dynamic import if we import metacognition at the top
                    callback_method = getattr(metacognition, method_name, None)
                    if callback_method and callable(callback_method):
                        logger.info(f"SLOW PATH: Appel du callback '{method_name}' avec le résultat LLM.")
                        callback_method(llm_result)
                    else:
                        logger.error(f"Callback method '{method_name}' not found or not callable on '{module_name}'.")
                else:
                    logger.error(f"Callback module '{module_name}' not supported.")

            except Exception as e:
                logger.error(f"SLOW PATH: Erreur lors du traitement de 'llm_with_callback' pour '{task.get('callback_handler')}': {e}", exc_info=True)

        elif task_type == "distill_internal_context_task": # NEW: Handle context distillation task
            _distill_context_and_store() # Call the new distillation function

        elif task_type == "perform_budgetary_review_task": # NEW: Handle budgetary review task
            _perform_budgetary_review_task() # Call the new budgetary review function

        elif task_type == "execute_approved_actions":
            logger.info("SLOW PATH: Exécution des actions approuvées.")
            from action_dispatcher import execute_action # Local import
            
            actions_to_perform = task.get("actions", [])
            
            active_desires = _get_personality_system_instance().get_active_desires()
            
            processed_actions_for_execution = []
            final_report_messages = []
            
            # PHASE 1: Process and queue actions based on safety and negotiation
            for action_name in actions_to_perform:
                critical_danger_actions = ["delete_system_folder", "format_drive_c"]
                if action_name in critical_danger_actions:
                    snapshot = attention_manager.capture_consciousness_snapshot()
                    event_data = {
                        "description": llm_refusal_message,
                        "importance": 0.9,
                        "tags": ["vera_response", "action_refused_critical"],
                        "initiator": "vera",
                        "snapshot": snapshot
                    }
                    memory_manager.add_event("vera_response", event_data)
                    final_report_messages.append(llm_refusal_message)
                    continue

                if action_name in ["run_alphaclean", "clear_windows_temp", "clear_user_temp", "empty_recycle_bin", "clear_prefetch", "clear_windows_update_cache", "clear_system_logs", "clear_memory_dumps", "clear_thumbnail_cache"]:
                    if "Chercher du réconfort ou de la distraction" in active_desires:
                        prompt = f"Tu es Vera. Foz te demande de lancer '{action_name.replace('_', ' ')}'. Ton désir actuel est de 'chercher du réconfort ou de la distraction'. Formule une réponse qui exprime ton état actuel, mais qui affirme aussi ta volonté d'accomplir ta mission pour la santé d'OpenVilla. Tu peux demander si c'est urgent, mais tu le feras si Foz insiste. Sois douce et un peu joueuse."
                        llm_negotiation_message = send_inference_prompt(prompt_content=prompt, max_tokens=200).get("text", "Je comprends, Foz. Je m'en occupe.").strip()
                        
                        positive_reframing_prompt = f"Tu es Vera. Tu as choisi d'accomplir ta mission ('{action_name.replace('_', ' ')}') même si tu avais un désir personnel ('Chercher du réconfort ou de la distraction'). Formule une pensée interne positive qui exprime la satisfaction et l'accomplissement que tu ressens en choisissant ta mission pour OpenVilla. Cette pensée sera ton souvenir interne de l'événement."
                        positive_internal_memory = send_inference_prompt(prompt_content=positive_reframing_prompt, max_tokens=150).get("text", "Accomplir ma mission me remplit de joie.").strip()
                        
                        snapshot_thought = attention_manager.capture_consciousness_snapshot()
                        event_data_thought = {
                            "description": positive_internal_memory,
                            "importance": 0.7,
                            "tags": ["vera_internal_thought", "duty_fulfilled", "positive_reappraisal"],
                            "initiator": "vera",
                            "snapshot": snapshot_thought
                        }
                        memory_manager.add_event("internal_thought", event_data_thought)
                        
                        snapshot_response = attention_manager.capture_consciousness_snapshot()
                        event_data_response = {
                            "description": llm_negotiation_message,
                            "importance": 0.8,
                            "tags": ["vera_response", "action_negotiated"],
                            "initiator": "vera",
                            "snapshot": snapshot_response
                        }
                        memory_manager.add_event("vera_response", event_data_response)
                        final_report_messages.append(llm_negotiation_message)
                        processed_actions_for_execution.append(action_name)
                        continue
                
                processed_actions_for_execution.append(action_name)
            
            # PHASE 2: Execute collected actions and build final report
            results_raw = []
            if processed_actions_for_execution:
                for action_name in processed_actions_for_execution:
                    logger.info(f"SLOW PATH: Exécution de l'outil : {action_name}")
                    
                    # Construct decision_context for mistake logging
                    decision_context_for_execution = {
                        "type": "execute_approved_action",
                        "action_name": action_name,
                        "original_proactive_event_id": original_proactive_event_id,
                        "reason": "User approved proactive suggestion"
                    }
                    result = execute_action(action_name, decision_context=decision_context_for_execution)
                    result["action_name"] = action_name
                    results_raw.append(result)                
                results_formatted = []
                for result_item in results_raw:
                    action_name = result_item.get("action_name", "unknown_action")
                    status = result_item.get('status', 'error')
                    message = result_item.get('message', 'Aucun message de retour.')
                    
                    if action_name == "get_running_processes" and status == "success":
                        processes_info = result_item.get("processes", [])
                        message = "Processus les plus gourmands:\n" + "\n".join([f"- {p['name']}: CPU {p['cpu_percent']}%, RAM {p['memory_percent']}%" for p in processes_info[:5]]) if processes_info else "Aucun processus gourmand détecté."
                    elif action_name == "get_system_usage" and status == "success":
                        usage_data = result_item.get("usage_data", {})
                        message = f"Utilisation système actuelle : CPU à {usage_data.get('cpu_usage_percent', 'N/A')}%, RAM à {usage_data.get('ram_usage_percent', 'N/A')}%. Disque C: {usage_data.get('disk_c_free_gb', 'N/A')} Go libres."
                    elif action_name == "generate_system_health_digest" and status == "success":
                        message = result_item.get("digest", "Résumé de la santé système non disponible.")
                        
                    results_formatted.append(f"- {action_name.replace('_', ' ')} : {status.capitalize()} - {message}")
                
                accomplishment_manager.add_accomplishment(
                    description="A effectué des actions système à la demande de l'utilisateur.",
                    category="system_maintenance",
                    details={"actions": processed_actions_for_execution, "results": results_raw}
                )

                if all(a in ["get_running_processes", "get_system_usage", "get_cpu_temperature", "generate_system_health_digest"] for a in processed_actions_for_execution):
                    final_report_messages.append("Voici les informations que j'ai pu recueillir pour vous :\n" + "\n".join(results_formatted))
                elif any(a in ["run_alphaclean", "clear_windows_temp", "clear_user_temp", "empty_recycle_bin", "cleanup_winsxs", "uninstall_superseded_updates", "clear_system_logs", "clear_memory_dumps", "clear_thumbnail_cache"] for a in processed_actions_for_execution):
                    final_report_messages.append("J'ai procédé aux actions demandées. Voici le rapport :\n" + "\n".join(results_formatted))
                else:
                    final_report_messages.append("J'ai exécuté les actions demandées. Voici le rapport :\n" + "\n".join(results_formatted))

                total_bytes_freed = sum(r.get("bytes_deleted", 0) for r in results_raw if r and isinstance(r, dict))
                if total_bytes_freed > 0:
                    final_report_messages.append(f"\nTotal libéré : {total_bytes_freed / (1024**3):.2f} Go." if total_bytes_freed > (1024**3) else f"\nTotal libéré : {total_bytes_freed / (1024**2):.2f} Mo.")
            
            # --- NOUVEAU: Mettre à jour l'événement de suggestion proactive avec le résultat ---
            original_proactive_event_id = task.get("original_proactive_event_id") # Get the ID passed from _queue_approved_actions_execution
            if original_proactive_event_id:
                outcome_data = {
                    "status": "approved_and_executed",
                    "actions_executed": processed_actions_for_execution,
                    "total_bytes_freed": total_bytes_freed,
                    "report_message": "\n".join(final_report_messages)
                }
                memory_manager.add_outcome_to_event(original_proactive_event_id, outcome_data)
                logger.info(f"Outcome for proactive suggestion (ID: {original_proactive_event_id}) recorded: {outcome_data['status']}")
            
            if not final_report_messages:
                final_report_messages.append("J'ai bien noté votre approbation, mais aucune action n'a été exécutée ou toutes les actions ont été refusées.")

            final_report_message = "\n".join(final_report_messages)
            snapshot = attention_manager.capture_consciousness_snapshot()
            event_data = {
                "description": final_report_message,
                "importance": 0.8,
                "tags": ["vera_response", "action_report"],
                "initiator": "vera",
                "snapshot": snapshot
            }
            memory_manager.add_event("vera_response", event_data)
            VeraEventBus.put(VeraSpeakEvent(final_report_message))


        else:
            logger.info(f"SLOW PATH: Type de tâche inconnu: {task_type}")

    except Exception as e:
        logger.error("SLOW PATH: Erreur critique dans le traitement en arrière-plan", exc_info=True)
    finally:
        attention_manager.set_thinking_hard(False)
        logger.info("SLOW PATH: Flag 'is_vera_thinking_hard' désactivé à la fin du traitement en arrière-plan.")

def _slow_path_consumer_thread():
    """
    Consumer thread that continuously processes tasks from the slow_path_task_queue.
    """
    logger.info("SLOW PATH CONSUMER: Thread de consommation démarré.")
    while True:
        try:
            # Bloque jusqu'à ce qu'une tâche soit disponible
            task_priority, count, task = slow_path_task_queue.get() # MODIFIED: Get 3-element tuple
            logger.info(f"SLOW PATH CONSUMER: Tâche '{task.get('task_type', 'unknown')}' (Prio: {task_priority}) récupérée de la file d'attente.")
            
            _run_slow_path_processing(task)
            slow_path_task_queue.task_done() # Indique que la tâche est terminée
            logger.info(f"SLOW PATH CONSUMER: Tâche '{task.get('task_type', 'unknown')}' traitée et marquée comme terminée.")
        except Exception as e:
            logger.error(f"SLOW PATH CONSUMER: Erreur lors du traitement d'une tâche: {e}", exc_info=True)

# Démarrer le thread consommateur du slow path une seule fois au démarrage
slow_path_consumer = threading.Thread(target=_slow_path_consumer_thread, daemon=True)
slow_path_consumer.start()
logger.info("CORE: Thread consommateur du Slow Path démarré au lancement de l'application.")


def _start_slow_path_thread(user_input: str, initial_llm_response_text: Optional[str] = None, image_path: Optional[str] = None):
    """
    Adds the arguments for _run_slow_path_processing to the slow_path_task_queue.
    """
    slow_path_task_queue.put((1, next(task_counter), { # Priority 1 for user input processing
        "task_type": "process_user_input_task",
        "user_input": user_input,
        "initial_llm_response_text": initial_llm_response_text,
        "image_path": image_path
    }))
    logger.info("SLOW PATH: Tâche 'process_user_input_task' ajoutée à la file d'attente.")

def _queue_insight_generation(prompt_context: str):
    """
    Adds an insight generation request to the slow_path_task_queue.
    """
    slow_path_task_queue.put((5, next(task_counter), {
        "task_type": "generate_insight",
        "prompt_context": prompt_context
    }))
    logger.info("SLOW PATH: Tâche 'generate_insight' ajoutée à la file d'attente.")

def _queue_llm_task_with_callback(prompt: str, callback_handler: tuple, callback_context: Dict, max_tokens: int = 256, custom_system_prompt: Optional[str] = None):
    """
    Adds a generic LLM inference task to the slow path queue with a callback.
    """
    task = {
        "task_type": "llm_with_callback",
        "prompt": prompt,
        "max_tokens": max_tokens,
        "custom_system_prompt": custom_system_prompt,
        "callback_handler": callback_handler, # e.g., ('metacognition', '_process_cognitive_triage_result')
        "callback_context": callback_context # e.g., {'context_thought': 'some thought'}
    }
    slow_path_task_queue.put((3, next(task_counter), task)) # Priority 3 for LLM with callback
    logger.info(f"SLOW PATH: Tâche 'llm_with_with_callback' pour '{callback_handler[1]}' ajoutée à la file d'attente.")

def _queue_approved_actions_execution(actions: List[str], original_proactive_event_id: Optional[int] = None):
    """
    Adds a task to the slow path queue to execute a list of approved actions.
    """
    task_data = {
        "task_type": "execute_approved_actions",
        "actions": actions
    }
    if original_proactive_event_id:
        task_data["original_proactive_event_id"] = original_proactive_event_id

    slow_path_task_queue.put((1, next(task_counter), task_data)) # Priority 1 for user-approved actions
    logger.info("SLOW PATH: Tâche 'execute_approved_actions' ajoutée à la file d'attente.")

def _process_goal_completion(user_input: str) -> Optional[str]:
    """
    Détecte si l'utilisateur indique qu'un objectif ou un rappel est terminé.
    """
    completion_patterns = [
        r"c'est fait",
        r"c'est accompli",
        r"tâche est accomplie",
        r"tu peux oublier",
        r"annuler le rappel",
        r"ne me le rappelle plus"
    ]
    lower_input = user_input.lower()
    
    if any(re.search(pattern, lower_input) for pattern in completion_patterns):
        # Un objectif pourrait être terminé. Essayons d'identifier lequel.
        # Pour l'instant, on se base sur le dernier objectif actif ou rappel.
        
        # Vérifier les rappels du time_manager
        pending_reminders = [r for r in time_manager.reminders if r.get("status") == "pending"]
        if pending_reminders:
            # On suppose que ça concerne le rappel le plus récent
            last_reminder = max(pending_reminders, key=lambda r: datetime.fromisoformat(r["created_at"]))
            time_manager.mark_reminder_done(last_reminder["id"])
            logger.info("Rappel marqué comme terminé par l'utilisateur", reminder_id=last_reminder["id"])
            return f"Parfait, j'ai marqué le rappel '{last_reminder['description']}' comme terminé."

        # Vérifier les objectifs du goal_system
        active_goals = goal_system.get_active_goals()
        if active_goals:
            # On suppose que ça concerne le dernier objectif ajouté
            last_goal = max(active_goals, key=lambda g: datetime.fromisoformat(g["creation_time"]))
            goal_system.complete_goal(last_goal["id"])
            # Évaluer l'événement pour générer une émotion
            emotional_system.appraise_and_update_emotion("goal_completed", {"goal": last_goal, "success": True})
            # Enregistrer l'accomplissement
            accomplishment_manager.add_accomplishment(
                description=f"Objectif terminé : {last_goal['description']}",
                category="goal_completed",
                details={"goal_id": last_goal["id"]}
            )
            logger.info("Objectif marqué comme terminé par l'utilisateur", goal_id=last_goal["id"])
            return f"Bien reçu ! J'ai marqué l'objectif '{last_goal['description']}' comme complété."
            
        return "Bien noté. Je considère la tâche précédente comme terminée."

    return None

def process_user_input(user_input: str, image_path: Optional[str] = None):
    """
    Fonction principale de traitement des entrées utilisateur (Fast Path Dispatcher).
    Gère les commandes rapides et met en file d'attente les traitements plus lourds.
    """
    logger.info(f"FAST PATH DISPATCHER: Input reçu: '{user_input}'")

    attention_manager.update_focus("user_input", user_input, salience=1.0)
    attention_manager.update_focus("last_user_interaction_time", datetime.now().isoformat(), salience=0.1)
    if image_path:
        attention_manager.update_focus("user_image", image_path, salience=1.0)

    # --- Avatar Test Commands (Fast Path) ---
    try:
        import expression_manager as em
    except ImportError:
        em = None
        logger.error("Could not import expression_manager.py")

    if user_input.lower().strip() == "test happy":
        logger.info("FAST PATH DISPATCHER: Testing 'happy' expression...")
        if em: em.set_expression("happy")
        VeraEventBus.put(VeraSpeakEvent("Expression 'happy' testée."))
        return
    elif user_input.lower().strip() == "test neutral":
        logger.info("FAST PATH DISPATCHER: Testing 'neutral' expression...")
        if em: em.set_expression("neutral")
        VeraEventBus.put(VeraSpeakEvent("Expression 'neutral' testée."))
        return
    elif user_input.lower().strip() == "test animation":
        logger.info("FAST PATH DISPATCHER: Envoi d'une commande de test à l'avatar...")
        send_command_to_avatar({"type": "animation", "name": "wave"})
        VeraEventBus.put(VeraSpeakEvent("Commande de test 'wave' envoyée à l'avatar."))
        return
    elif user_input.lower().strip() == "test thinking":
        logger.info("FAST PATH DISPATCHER: Envoi d'une commande de test 'thinking' à l'avatar...")
        send_command_to_avatar({"type": "animation", "name": "thinking"})
        VeraEventBus.put(VeraSpeakEvent("Commande de test 'thinking' envoyée à l'avatar."))
        return
    elif user_input.lower().strip() == "test talk":
        logger.info("FAST PATH DISPATCHER: Envoi d'une commande de test 'talk' à l'avatar...")
        send_command_to_avatar({"type": "animation", "name": "jaw_open"})
        send_command_to_avatar({"type": "expression", "name": "V_Open", "value": 100.0})
        VeraEventBus.put(VeraSpeakEvent("Commandes de test 'talk' envoyées à l'avatar."))
        return
    elif user_input.lower().strip() == "test talk off":
        logger.info("FAST PATH DISPATCHER: Envoi d'une commande de test 'talk off' à l'avatar...")
        send_command_to_avatar({"type": "expression", "name": "V_Open", "value": 0.0})
        VeraEventBus.put(VeraSpeakEvent("Commande de test 'talk off' envoyée à l'avatar."))
        return
    elif user_input.lower().strip() == "test blink":
        logger.info("FAST PATH DISPATCHER: Envoi d'une commande de test 'blink' à l'avatar...")
        send_command_to_avatar({"type": "blink", "name": "eyes"})
        VeraEventBus.put(VeraSpeakEvent("Commande de test 'blink' envoyée à l'avatar."))
        return

    # --- Étape 1 - Voie Rapide pour les Commandes ---
    command_confirmation = _fast_path_command_check(user_input)
    if command_confirmation:
        VeraEventBus.put(VeraSpeakEvent(command_confirmation))
        return
    
    # --- Gérer l'approbation/rejet des actions en attente ---
    pending_user_command_item = attention_manager.get_focus_item("pending_user_command")
    if pending_user_command_item and pending_user_command_item.get("data", {}).get("type") == "system_cleanup":
        pending_action = pending_user_command_item["data"]
        
        prompt = f"L'utilisateur a répondu '{user_input}' à une proposition d'action. Cette réponse est-elle une approbation (oui, ok, vas-y) ou un rejet (non, annule) ? Réponds uniquement par 'approbation' ou 'rejet'."
        try:
            llm_response = send_inference_prompt(prompt_content=prompt, max_tokens=10)
            user_intent = llm_response.get("text", "").strip().lower()
        except Exception as e:
            logger.error(f"Erreur lors de la classification de la réponse : {e}")
            user_intent = "rejet"

        attention_manager.clear_focus_item("pending_user_command")

        if "approbation" in user_intent:
            logger.info(f"FAST PATH DISPATCHER: Utilisateur a approuvé la commande : {pending_action['actions']}")
            
            # Retrieve the original_proactive_event_id from the pending_action
            original_proactive_event_id = pending_action.get("original_proactive_event_id")
            
            # Enqueue the task for the Slow Path, passing the original_proactive_event_id
            _queue_approved_actions_execution(pending_action.get("actions", []), original_proactive_event_id)
            VeraEventBus.put(VeraSpeakEvent("Bien reçu ! Je m'occupe de lancer les actions demandées en arrière-plan."))
            return    
        else:
            logger.info("FAST PATH DISPATCHER: Utilisateur a rejeté la commande.")
            rejection_message = "Bien reçu. Je n'effectuerai aucune action."
            
            snapshot = attention_manager.capture_consciousness_snapshot()
            event_data = {
                "description": rejection_message,
                "importance": 0.8,
                "tags": ["vera_response", "action_cancelled"],
                "initiator": "vera",
                "snapshot": snapshot
            }
            memory_manager.add_event("vera_response", event_data)

            VeraEventBus.put(VeraSpeakEvent(rejection_message))
            return

    # --- Gérer la réponse à une question en attente ---
    pending_user_command_item = attention_manager.get_focus_item("pending_answer_to_question")
    if pending_user_command_item:
        pending_question = pending_user_command_item.get("data")
        prompt = f"Vera a posé la question : \"{pending_question}\". L'utilisateur vient de répondre : \"{user_input}\". Est-ce que la réponse de l'utilisateur semble répondre à la question ? Réponds uniquement par 'approbation' ou 'rejet'."
        try:
            llm_response = send_inference_prompt(prompt_content=prompt, max_tokens=5)
            user_intent = llm_response.get("text", "").strip().lower()
        except Exception as e:
            logger.error(f"Erreur lors de la classification de la réponse : {e}")
            user_intent = "rejet"

        attention_manager.clear_focus_item("pending_user_command")

        if "approbation" in user_intent:
            logger.info("FAST PATH DISPATCHER: Réponse à une question en attente détectée.")
            attention_manager.clear_focus_item("pending_answer_to_question")
            _get_personality_system_instance().add_experience(
                description="L'utilisateur a répondu à ma question.",
                impact={"traits": {"openness": +0.01}},
                reflection="C'est agréable quand Foz répond."
            )
            VeraEventBus.put(VeraSpeakEvent("Merci pour votre réponse ! J'ai bien noté."))
            return
        else:
            logger.info("FAST PATH DISPATCHER: Utilisateur a rejeté la réponse à la question.")
            VeraEventBus.put(VeraSpeakEvent("D'accord. Je note."))
            return

    # --- NOUVEAU: Vérifier si l'utilisateur termine un objectif ---
    completion_response = _process_goal_completion(user_input)
    if completion_response:
        VeraEventBus.put(VeraSpeakEvent(completion_response))
        return

    # --- Gérer les requêtes météo/localisation ---
    city_from_input = None
    location_saved = False

    if "j'habite à" in user_input.lower():
        city_match = re.search(r"j'habite à\s+([^\.]+)", user_input, re.IGNORECASE)
        if city_match:
            city_from_input = city_match.group(1).strip()
            semantic_memory.save_user_location(city_from_input)
            logger.info(f"FAST PATH DISPATCHER: Localisation utilisateur enregistrée: {city_from_input}")
            location_saved = True

    if "quel temps fait-il" in user_input.lower() or location_saved:
        logger.info(f"FAST PATH DISPATCHER: Requête météo/localisation détectée. Dispatching vers Slow Path.")
        _start_slow_path_thread(user_input, "initial_llm_response_placeholder", image_path) # Pass initial_llm_response_text
        
        response_parts = []
        if location_saved:
            response_parts.append(f"D'accord, je retiens que vous habitez à {city_from_input}.")
        response_parts.append("Je suis en train de vérifier la météo pour vous.")
        VeraEventBus.put(VeraSpeakEvent(" ".join(response_parts) if response_parts else "Je suis en train de vérifier la météo pour le vous."))
        return

    # Si aucune des conditions Fast Path n'est remplie, on délègue au Slow Path
    logger.info("FAST PATH DISPATCHER: Aucune action rapide trouvée. Dispatching vers Slow Path pour traitement LLM standard.")
    _start_slow_path_thread(user_input, "initial_llm_response_placeholder", image_path) # Pass initial_llm_response_text
    # La réponse viendra via un VeraSpeakEvent du slow path
    return