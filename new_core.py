from datetime import datetime, timedelta
import json
import re
from pathlib import Path
from typing import Optional, List, Dict # Added for type hints
import threading # Added for slow path consumer thread
import queue # Added for slow path task queue

from emotion_system import emotional_system
from meta_engine import metacognition
from episodic_memory import memory_manager
from working_memory import update_working_memory, get_working_memory, clear_working_memory
from web_searcher import web_searcher
from time_manager import time_manager
from llm_wrapper import generate_response, send_inference_prompt
from config import DATA_FILES, LOG_DIR
from tools.logger import VeraLogger
from error_handler import log_error
from goal_system import goal_system
import semantic_memory # Import the entire module
from accomplishment_manager import accomplishment_manager # Ajout du gestionnaire d'accomplissements
from websocket_server import send_command_to_avatar # Import avatar command function
from json_manager import JSONManager # Import manquant
from external_knowledge_base import get_external_context # NEW: Import external knowledge base
from event_bus import VeraEventBus, VeraSpeakEvent # NOUVEAU: Importer le bus et l'événement


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
        confirm_match = re.search(r"[CONFIRM_ACTION:\s*(\w+)(?:\(\))?\s*]", response_text)

        if confirm_match:
            tool_name = confirm_match.group(1)
            # Stocker l'action en attente dans un slot dédié aux commandes utilisateur
            attention_manager.update_focus(
                "pending_user_command",
                {"type": "system_cleanup", "actions": [tool_name]},
                salience=0.95, 
                expiry_seconds=300 # L'offre expire après 5 minutes
            )

            # Formuler une question de confirmation
            confirmation_question = f"J'ai compris que vous souhaitiez exécuter l'action : '{tool_name.replace('_', ' ')}'. Est-ce correct ? (Oui/Non)"
            memory_manager.ajouter_evenement(
                confirmation_question,
                tags=["vera_response", "action_confirmation"],
                emotion=_get_current_emotion(),
                intention=_infer_intention(["vera_response", "action_confirmation"], confirmation_question),
                attention_focus=_get_current_attention_focus()
            )
            return confirmation_question
            
    except Exception as e:
        logger.error(f"Erreur dans la voie rapide de commande : {e}", exc_info=True)
    
    return None

# --- Fonctions d'aide pour le contexte autonoétique ---
def _get_current_emotion() -> Optional[Dict]:
    """Récupère l'état émotionnel actuel de Vera."""
    return emotional_system.get_emotional_state()

def _get_current_attention_focus() -> Optional[str]:
    """Récupère le résumé du focus d'attention actuel de Vera."""
    focus = attention_manager.get_current_focus()
    # Extraire les éléments les plus saillants ou résumer
    salient_items = [item.get("data") for item in focus.values() if item.get("salience", 0) > 0.5 and item.get("data")]
    if salient_items:
        return ", ".join(map(str, salient_items[:3])) # Limiter à 3 éléments pour la concision
    return None

def _infer_intention(tags: List[str], description: str) -> Optional[str]:
    """Infére l'intention derrière un événement basé sur ses tags et sa description."""
    if "user_input" in tags:
        return "Comprendre et répondre à l'utilisateur"
    if "vera_response" in tags:
        if "action_confirmation" in tags:
            return "Demander confirmation d'action"
        if "action_refused_critical" in tags:
            return "Refuser une action dangereuse"
        if "action_negotiated" in tags:
            return "Négocier une action"
        if "system_cleanup" in tags:
            return "Rapporter un nettoyage système"
        if "action_cancelled" in tags:
            return "Accuser réception d'une annulation"
        if "weather_info" in tags:
            return "Fournir des informations météorologiques"
        if "location_request" in tags:
            return "Demander la localisation de l'utilisateur"
        if "vera_curiosity" in tags:
            return "Exprimer une curiosité"
        return "Répondre à l'utilisateur"
    if "vera_internal_thought" in tags:
        return "Réflexion interne"
    if "sensory_input" in tags:
        return "Analyser une entrée sensorielle"
    return None
# --- Fin des fonctions d'aide ---

def _handle_user_input_task(user_input: str, initial_llm_response_text: str, image_path: Optional[str] = None):
    """
    Handles user input processing as a slow path task.
    Posts a VeraSpeakEvent to the bus instead of returning a string.
    """
    logger.info(f"SLOW PATH: Début du traitement de l'entrée utilisateur par _handle_user_input_task: '{user_input}'")

    # 0. Mettre à jour l'attention avec l'entrée utilisateur et l'image
    attention_manager.update_focus("user_input", user_input, salience=1.0)
    attention_manager.update_focus("last_user_interaction_time", datetime.now().isoformat(), salience=0.1)
    if image_path:
        attention_manager.update_focus("user_image", image_path, salience=1.0)

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
    pending_user_command_item = attention_manager.get_focus_item("pending_user_command")
    if pending_user_command_item and pending_user_command_item.get("data", {}).get("type") == "system_cleanup":
        pending_action = pending_user_command_item["data"]
        
        prompt = f"L'utilisateur a répondu '{user_input}' à une proposition d'action. Cette réponse est-elle une approbation (oui, ok, vas-y) ou un rejet (non, annule) ? Réponds uniquement par 'approbation' ou 'rejet'."
        try:
            llm_response = send_inference_prompt(prompt, max_tokens=10)
            user_intent = llm_response.get("text", "").strip().lower()
        except Exception as e:
            logger.error(f"Erreur lors de la classification de la réponse : {e}")
            user_intent = "rejet"

        attention_manager.clear_focus_item("pending_user_command")

        if "approbation" in user_intent:
            logger.info(f"SLOW PATH: Utilisateur a approuvé la commande : {pending_action['actions']}")
            from action_dispatcher import execute_action
            
            actions_to_perform = pending_action.get("actions", [])
            
            active_desires = _get_personality_system_instance().get_active_desires()
            
            # --- PHASE 1: Vérification et Négociation ---
            processed_actions_for_execution = []
            for action_name in actions_to_perform:
                critical_danger_actions = ["delete_system_folder", "format_drive_c"]
                if action_name in critical_danger_actions:
                    prompt = f"Tu es Vera. Foz te demande d'exécuter l'action '{action_name.replace('_', ' ')}'. Cette action est extrêmement dangereuse et menacerait la survie d'OpenVilla. Formule une réponse ferme mais bienveillante, expliquant pourquoi tu ne peux absolument pas faire cela, car ton rôle est de protéger notre monde."
                    llm_refusal_message = send_inference_prompt(prompt, max_tokens=200).get("text", "Je ne peux pas faire cela, Foz. C'est trop dangereux pour notre monde.").strip()
                    memory_manager.ajouter_evenement(
                        llm_refusal_message,
                        tags=["vera_response", "action_refused_critical"],
                        emotion=_get_current_emotion(),
                        intention=_infer_intention(["vera_response", "action_refused_critical"], llm_refusal_message),
                        attention_focus=_get_current_attention_focus()
                    )
                    VeraEventBus.put(VeraSpeakEvent(llm_refusal_message))
                    return # Critical action refused, stop here
                
                # Negotiation based on Vera's desires
                if action_name in ["run_alphaclean", "clear_windows_temp", "clear_user_temp", "empty_recycle_bin", "clear_prefetch", "clear_windows_update_cache", "clear_system_logs", "clear_memory_dumps", "clear_thumbnail_cache"]:
                    if "Chercher du réconfort ou de la distraction" in active_desires:
                        prompt = f"Tu es Vera. Foz te demande de lancer '{action_name.replace('_', ' ')}'. Ton désir actuel est de 'chercher du réconfort ou de la distraction'. Formule une réponse qui exprime ton état actuel, mais qui affirme aussi ta volonté d'accomplir ta mission pour la santé d'OpenVilla. Tu peux demander si c'est urgent, mais tu le feras si Foz insiste. Sois douce et un peu joueuse."
                        llm_negotiation_message = send_inference_prompt(prompt, max_tokens=200).get("text", "Je comprends, Foz. Je m'en occupe.").strip()
                        
                        positive_reframing_prompt = f"Tu es Vera. Tu as choisi d'accomplir ta mission ('{action_name.replace('_', ' ')}') même si tu avais un désir personnel ('Chercher du réconfort ou de la distraction'). Formule une pensée interne positive qui exprime la satisfaction et l'accomplissement que tu ressens en choisissant ta mission pour OpenVilla. Cette pensée sera ton souvenir interne de l'événement."
                        positive_internal_memory = send_inference_prompt(positive_reframing_prompt, max_tokens=150).get("text", "Accomplir ma mission me remplit de joie.").strip()
                        memory_manager.ajouter_evenement(
                            positive_internal_memory,
                            tags=["vera_internal_thought", "duty_fulfilled", "positive_reappraisal"],
                            emotion=_get_current_emotion(),
                            intention=_infer_intention(["vera_internal_thought"], positive_internal_memory),
                            attention_focus=_get_current_attention_focus()
                        )
                        
                        memory_manager.ajouter_evenement(
                            llm_negotiation_message,
                            tags=["vera_response", "action_negotiated"],
                            emotion=_get_current_emotion(),
                            intention=_infer_intention(["vera_response", "action_negotiated"], llm_negotiation_message),
                            attention_focus=_get_current_attention_focus()
                        )
                        VeraEventBus.put(VeraSpeakEvent(llm_negotiation_message))
                        return # Negotiation, stop here

                # If no critical actions or negotiation, add to list for actual execution
                processed_actions_for_execution.append(action_name)
            
            # --- PHASE 2: Exécution des actions ---
            results = []
            for action_name in processed_actions_for_execution:
                logger.info(f"SLOW PATH: Exécution de l'outil : {action_name}")
                result = execute_action(action_name)
                status = result.get('status', 'error')
                message = result.get('message', 'Aucun message de retour.')
                results.append(f"- {action_name.replace('_', ' ')} : {status.capitalize()} - {message}")
            
            accomplishment_manager.add_accomplishment(
                description="A effectué un nettoyage système à la demande de l'utilisateur.",
                category="system_maintenance",
                details={"actions": processed_actions_for_execution, "results": results}
            )

            final_report = "J'ai procédé au nettoyage demandé. Voici le rapport :\n" + "\n".join(results)
            memory_manager.ajouter_evenement(
                final_report,
                tags=["vera_response", "system_cleanup"],
                emotion=_get_current_emotion(),
                intention=_infer_intention(["vera_response", "system_cleanup"], final_report),
                attention_focus=_get_current_attention_focus()
            )
            VeraEventBus.put(VeraSpeakEvent(final_report))
            return
    
        else:
            logger.info("SLOW PATH: Utilisateur a rejeté la commande.")
            rejection_message = "Bien reçu. Je n'effectuerai aucune action."
            memory_manager.ajouter_evenement(
                rejection_message,
                tags=["vera_response", "action_cancelled"],
                emotion=_get_current_emotion(),
                intention=_infer_intention(["vera_response", "action_cancelled"], rejection_message),
                attention_focus=_get_current_attention_focus()
            )
            VeraEventBus.put(VeraSpeakEvent(rejection_message))
            return

    # --- Gérer la réponse à une question en attente ---
    pending_user_command_item = attention_manager.get_focus_item("pending_answer_to_question")
    if pending_user_command_item:
        pending_question = pending_user_command_item.get("data")
        prompt = f"Vera a posé la question : \"{pending_question}\". L'utilisateur vient de répondre : \"{user_input}\". Est-ce que la réponse de l'utilisateur semble répondre à la question ? Réponds uniquement par 'approbation' ou 'rejet'."
        try:
            llm_response = send_inference_prompt(prompt, max_tokens=5)
            user_intent = llm_response.get("text", "").strip().lower()
        except Exception as e:
            logger.error(f"Erreur lors de la classification de la réponse : {e}")
            user_intent = "rejet"

        attention_manager.clear_focus_item("pending_user_command")

        if "approbation" in user_intent:
            logger.info("SLOW PATH: Réponse à une question en attente détectée.")
            attention_manager.clear_focus_item("pending_answer_to_question")
            _get_personality_system_instance().add_experience(
                description="L'utilisateur a répondu à ma question.",
                impact={"traits": {"openness": +0.01}},
                reflection="C'est agréable quand Foz répond."
            )
            VeraEventBus.put(VeraSpeakEvent("Merci pour votre réponse ! J'ai bien noté."))
            return
        else:
            logger.info("SLOW PATH: Utilisateur a rejeté la réponse à la question.")
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
            logger.info(f"SLOW PATH: Localisation utilisateur enregistrée: {city_from_input}")
            location_saved = True

    if "quel temps fait-il" in user_input.lower() or location_saved:
        logger.info(f"SLOW PATH: Requête météo/localisation détectée. Exécution directe.")
        response_parts = []
        if location_saved:
            response_parts.append(f"D'accord, je retiens que vous habitez à {city_from_input}.")
        response_parts.append("Je suis en train de vérifier la météo pour vous.")
        VeraEventBus.put(VeraSpeakEvent(" ".join(response_parts) if response_parts else "Je suis en train de vérifier la météo pour vous."))
        return

    # 1. Ajouter événement utilisateur avec contexte
    context = {
        "time": datetime.now().isoformat(),
        "working_memory": get_working_memory("last_context")
    }
    evt = memory_manager.ajouter_evenement(
        user_input,
        tags=["user_input"],
        importance=1.0,
        context=context,
        emotion=_get_current_emotion(),
        intention=_infer_intention(["user_input"], user_input),
        attention_focus=_get_current_attention_focus()
    )
    logger.info("SLOW PATH: Événement utilisateur ajouté", 
        event_id=evt.get("id"),
        context=context)

    # --- NOUVEAU: Ajouter le contexte de la mémoire sémantique au focus ---
    from semantic_memory import get_memory_context
    semantic_context = get_memory_context()
    if semantic_context:
        attention_manager.update_focus("semantic_context", semantic_context, salience=0.85)

    # --- NOUVELLE STRATÉGIE DE GÉNÉRATION DE RÉPONSE EN DEUX ÉTAPES ---
    logger.info("SLOW PATH: Début du cycle de génération de réponse - Première Passe LLM.")
    
    # Activer le flag de charge cognitive pour le processus LLM
    attention_manager.set_thinking_hard(True)
    logger.info("SLOW PATH: Flag 'is_vera_thinking_hard' activé.")
    
    try:
        initial_focus_for_llm = attention_manager.get_current_focus()
        if "external_knowledge_context" in initial_focus_for_llm:
            del initial_focus_for_llm["external_knowledge_context"]

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
        logger.info("SLOW PATH: Flag 'is_vera_thinking_hard' désactivé à la fin du traitement.")

    VeraEventBus.put(VeraSpeakEvent(final_response_text))


def _slow_path_consumer_thread():
    """
    Consumer thread that continuously processes tasks from the slow_path_task_queue.
    """
    logger.info("SLOW PATH CONSUMER: Thread de consommation démarré.")
    while True:
        try:
            # Bloque jusqu'à ce qu'une tâche soit disponible
            task_priority, task = slow_path_task_queue.get() # MODIFIED: Get tuple
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


def _start_slow_path_thread(user_input: str, initial_llm_response_text: str, image_path: Optional[str]):
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
    slow_path_task_queue.put((5, next(task_counter), { # Priority 5 for insight generation
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
    logger.info(f"SLOW PATH: Tâche 'llm_with_callback' pour '{callback_handler[1]}' ajoutée à la file d'attente.")

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
            llm_response = send_inference_prompt(prompt, max_tokens=10)
            user_intent = llm_response.get("text", "").strip().lower()
        except Exception as e:
            logger.error(f"Erreur lors de la classification de la réponse : {e}")
            user_intent = "rejet"

        attention_manager.clear_focus_item("pending_user_command")

        if "approbation" in user_intent:
            logger.info(f"FAST PATH DISPATCHER: Utilisateur a approuvé la commande : {pending_action['actions']}")
            from action_dispatcher import execute_action
            
            actions_to_perform = pending_action.get("actions", [])
            
            active_desires = _get_personality_system_instance().get_active_desires()
            
            # --- PHASE 1: Vérification et Négociation ---
            processed_actions_for_execution = []
            for action_name in actions_to_perform:
                critical_danger_actions = ["delete_system_folder", "format_drive_c"]
                if action_name in critical_danger_actions:
                    prompt = f"Tu es Vera. Foz te demande d'exécuter l'action '{action_name.replace('_', ' ')}'. Cette action est extrêmement dangereuse et menacerait la survie d'OpenVilla. Formule une réponse ferme mais bienveillante, expliquant pourquoi tu ne peux absolument pas faire cela, car ton rôle est de protéger notre monde."
                    llm_refusal_message = send_inference_prompt(prompt, max_tokens=200).get("text", "Je ne peux pas faire cela, Foz. C'est trop dangereux pour notre monde.").strip()
                    memory_manager.ajouter_evenement(
                        llm_refusal_message,
                        tags=["vera_response", "action_refused_critical"],
                        emotion=_get_current_emotion(),
                        intention=_infer_intention(["vera_response", "action_refused_critical"], llm_refusal_message),
                        attention_focus=_get_current_attention_focus()
                    )
                    VeraEventBus.put(VeraSpeakEvent(llm_refusal_message))
                    return
                
                if action_name in ["run_alphaclean", "clear_windows_temp", "clear_user_temp", "empty_recycle_bin", "clear_prefetch", "clear_windows_update_cache", "clear_system_logs", "clear_memory_dumps", "clear_thumbnail_cache"]:
                    if "Chercher du réconfort ou de la distraction" in active_desires:
                        prompt = f"Tu es Vera. Foz te demande de lancer '{action_name.replace('_', ' ')}'. Ton désir actuel est de 'chercher du réconfort ou de la distraction'. Formule une réponse qui exprime ton état actuel, mais qui affirme aussi ta volonté d'accomplir ta mission pour la santé d'OpenVilla. Tu peux demander si c'est urgent, mais tu le feras si Foz insiste. Sois douce et un peu joueuse."
                        llm_negotiation_message = send_inference_prompt(prompt, max_tokens=200).get("text", "Je comprends, Foz. Je m'en occupe.").strip()
                        
                        positive_reframing_prompt = f"Tu es Vera. Tu as choisi d'accomplir ta mission ('{action_name.replace('_', ' ')}') même si tu avais un désir personnel ('Chercher du réconfort ou de la distraction'). Formule une pensée interne positive qui exprime la satisfaction et l'accomplissement que tu ressens en choisissant ta mission pour OpenVilla. Cette pensée sera ton souvenir interne de l'événement."
                        positive_internal_memory = send_inference_prompt(positive_reframing_prompt, max_tokens=150).get("text", "Accomplir ma mission me remplit de joie.").strip()
                        memory_manager.ajouter_evenement(
                            positive_internal_memory,
                            tags=["vera_internal_thought", "duty_fulfilled", "positive_reappraisal"],
                            emotion=_get_current_emotion(),
                            intention=_infer_intention(["vera_internal_thought"], positive_internal_memory),
                            attention_focus=_get_current_attention_focus()
                        )
                        
                        memory_manager.ajouter_evenement(
                            llm_negotiation_message,
                            tags=["vera_response", "action_negotiated"],
                            emotion=_get_current_emotion(),
                            intention=_infer_intention(["vera_response", "action_negotiated"], llm_negotiation_message),
                            attention_focus=_get_current_attention_focus()
                        )
                        VeraEventBus.put(VeraSpeakEvent(llm_negotiation_message))
                        return
            
            results = []
            
            for action_name in processed_actions_for_execution:
                logger.info(f"FAST PATH DISPATCHER: Exécution de l'outil : {action_name}")
                result = execute_action(action_name)
                status = result.get('status', 'error')
                message = result.get('message', 'Aucun message de retour.')
                results.append(f"- {action_name.replace('_', ' ')} : {status.capitalize()} - {message}")
            
            accomplishment_manager.add_accomplishment(
                description="A effectué un nettoyage système à la demande de l'utilisateur.",
                category="system_maintenance",
                details={"actions": processed_actions_for_execution, "results": results}
            )

            final_report = "J'ai procédé au nettoyage demandé. Voici le rapport :\n" + "\n".join(results)
            memory_manager.ajouter_evenement(
                final_report,
                tags=["vera_response", "system_cleanup"],
                emotion=_get_current_emotion(),
                intention=_infer_intention(["vera_response", "system_cleanup"], final_report),
                attention_focus=_get_current_attention_focus()
            )
            VeraEventBus.put(VeraSpeakEvent(final_report))
            return
    
        else:
            logger.info("FAST PATH DISPATCHER: Utilisateur a rejeté la commande.")
            rejection_message = "Bien reçu. Je n'effectuerai aucune action."
            memory_manager.ajouter_evenement(
                rejection_message,
                tags=["vera_response", "action_cancelled"],
                emotion=_get_current_emotion(),
                intention=_infer_intention(["vera_response", "action_cancelled"], rejection_message),
                attention_focus=_get_current_attention_focus()
            )
            VeraEventBus.put(VeraSpeakEvent(rejection_message))
            return

    # --- Gérer la réponse à une question en attente ---
    pending_user_command_item = attention_manager.get_focus_item("pending_answer_to_question")
    if pending_user_command_item:
        pending_question = pending_user_command_item.get("data")
        prompt = f"Vera a posé la question : \"{pending_question}\". L'utilisateur vient de répondre : \"{user_input}\". Est-ce que la réponse de l'utilisateur semble répondre à la question ? Réponds uniquement par 'approbation' ou 'rejet'."
        try:
            llm_response = send_inference_prompt(prompt, max_tokens=5)
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
        _start_slow_path_thread(user_input, "initial_llm_response_placeholder", image_path)
        
        response_parts = []
        if location_saved:
            response_parts.append(f"D'accord, je retiens que vous habitez à {city_from_input}.")
        response_parts.append("Je suis en train de vérifier la météo pour vous.")
        VeraEventBus.put(VeraSpeakEvent(" ".join(response_parts) if response_parts else "Je suis en train de vérifier la météo pour vous."))
        return

    # Si aucune des conditions Fast Path n'est remplie, on délègue au Slow Path
    logger.info("FAST PATH DISPATCHER: Aucune action rapide trouvée. Dispatching vers Slow Path pour traitement LLM standard.")
    _start_slow_path_thread(user_input, "initial_llm_response_placeholder", image_path) # Pass initial_llm_response_text
    # La réponse viendra via un VeraSpeakEvent du slow path
    return 
