import logging
from tools.logger import VeraLogger
import system_cleaner # Import the new system_cleaner module
from attention_manager import attention_manager # NEW: Import attention_manager

# --- Configuration ---
# Cet interrupteur contrôle si les actions sont réellement exécutées ou juste simulées.
SIMULATION_MODE = False

# --- Loggers ---
# Un logger standard pour les opérations du dispatcher
logger = VeraLogger("action_dispatcher")
# Un logger dédié pour enregistrer les actions simulées dans un fichier séparé
action_logger = logging.getLogger("actions")
action_logger.setLevel(logging.INFO)
action_logger.propagate = False
if not action_logger.handlers:
    # Crée le fichier logs/actions.log
    action_handler = logging.FileHandler("logs/actions.log", encoding="utf-8")
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    action_handler.setFormatter(formatter)
    action_logger.addHandler(action_handler)

_REGISTERED_TOOLS = [
    "web_search",
    "learn_about_topic",
    "get_time",
    "get_system_usage",
    "get_cpu_temperature",
    "get_running_processes",
    "check_senses",
    "get_weather",
    "record_observation",
    "run_alphaclean",
    "clear_windows_temp",
    "clear_user_temp",
    "clear_prefetch",
    "clear_windows_update_cache",
    "empty_recycle_bin",
    "cleanup_winsxs",
    "uninstall_superseded_updates",
    "clear_system_logs",
    "clear_memory_dumps",
    "clear_thumbnail_cache",
    "propose_new_tool", # New tool for self-evolution
    "generate_system_health_digest", # New tool for system health summary
    "generate_thought", # NEW: Connects MetaEngine decisions to InternalMonologue
    "update_narrative", # NEW: Allows MetaEngine to trigger narrative updates
]

def get_available_tools() -> list[str]:
    """
    Returns a list of all tool names currently registered in the action dispatcher.
    """
    return _REGISTERED_TOOLS

def _generate_simulated_result(tool_name: str, **kwargs) -> dict:
    """
    Génère un faux résultat plausible pour une action simulée.
    Cela permet à la boucle cognitive de Vera de continuer comme si l'action avait vraiment eu lieu.
    """
    logger.info(f"Génération d'un résultat simulé pour {tool_name}")
    if tool_name == "web_search":
        return {
            "wikipedia": {"success": True, "articles": [{"title": f"Résultat simulé pour {kwargs.get('query')}", "summary": "Ceci est un résumé simulé car le mode de simulation d'action est activé.", "url": ""}]},
            "news": {"success": False, "error": "Simulation mode"},
            "general": {"success": False, "error": "Simulation mode"}
        }
    if tool_name == "propose_new_tool":
        task_description = kwargs.get("task_description", "une tâche inconnue")
        return {"status": "simulated_success", "tool": tool_name, "args": kwargs, "message": f"Vera a simulé la proposition d'un nouvel outil pour : {task_description}"}
    if tool_name == "generate_thought": # NEW
        topic = kwargs.get("topic", "une pensée")
        return {"status": "simulated_success", "tool": tool_name, "args": kwargs, "message": f"Vera a simulé la génération d'une pensée sur : {topic}"}
    # On pourra ajouter d'autres résultats simulés pour d'autres outils ici
    return {"status": "simulated_success", "tool": tool_name, "args": kwargs}

def execute_action(tool_name: str, decision_context: dict = None, **kwargs):
    """
    Dispatcher central pour toutes les actions de Vera sur le monde.
    Vérifie si le mode simulation est activé.
    """
    if SIMULATION_MODE:
        log_message = f"ACTION SIMULÉE : Outil='{tool_name}', Arguments={kwargs}"
        logger.info(log_message)
        action_logger.info(log_message)
        return _generate_simulated_result(tool_name, **kwargs)
    else:
        log_message = f"ACTION EXÉCUTÉE : Outil='{tool_name}', Arguments={kwargs}"
        logger.info(log_message)
        action_logger.info(log_message) # Log to actions.log as well

        # Exécution réelle
        from web_searcher import web_searcher
        from learning_system import learning_system # NOUVEAU: Import pour learn_about_topic
        from attention_manager import attention_manager # Import attention_manager for notification
        from internal_monologue import InternalMonologue # NEW: Import for generate_thought

        if tool_name == "web_search":
            return web_searcher.search(**kwargs)

        if tool_name == "learn_about_topic": # NOUVEAU: Gérer l'action d'apprentissage
            topic = kwargs.get("topic")
            if topic:
                # _learn_about_topic gère sa propre recherche web et les mises à jour du focus
                learning_system._learn_about_topic(topic)
                return {"status": "success", "message": f"Apprentissage initié sur le sujet : {topic}"}
            else:
                return {"status": "error", "message": "Sujet manquant pour learn_about_topic"}

        if tool_name == "get_time":
            from time_manager import time_manager
            return {"status": "success", "datetime_str": time_manager.get_current_datetime_str()}

        # --- System Monitor Tools ---
        if tool_name == "get_system_usage":
            from system_monitor import get_system_usage
            return {"status": "success", "usage_data": get_system_usage()}

        if tool_name == "get_cpu_temperature":
            from system_monitor import get_cpu_temperature
            return {"status": "success", "temperature": get_cpu_temperature()}

        if tool_name == "get_running_processes":
            from system_monitor import get_running_processes
            return {"status": "success", "processes": get_running_processes()}

        if tool_name == "check_senses":
            from system_monitor import get_system_usage
            from attention_manager import attention_manager
            usage_data = get_system_usage()
            attention_manager.update_focus(
                "sensory_input_system_usage",
                usage_data,
                salience=0.6, # Sensory data is quite important
                expiry_seconds=300 # Stays in focus for 5 minutes
            )
            return {"status": "success", "message": "Sensory data updated in attention focus.", "data": usage_data}

        if tool_name == "get_weather":
            from tools.weather import get_weather
            return get_weather(**kwargs)

        if tool_name == "record_observation":
            from journal_manager import journal_manager
            observation_text = kwargs.get("observation_text", "Observation sans texte.")
            journal_manager.add_entry(observation_text)
            return {"status": "success", "message": "Observation enregistrée."}
        
        if tool_name == "generate_thought":
            from internal_monologue import InternalMonologue
            topic = kwargs.get("topic")
            # Note: A singleton pattern for InternalMonologue would be more efficient,
            # but instantiating it here is functionally correct as it holds no critical state.
            internal_monologue_instance = InternalMonologue()
            internal_monologue_instance._generate_thought(topic=topic)
            return {"status": "success", "message": f"Pensée générée sur le sujet : {topic}"}

        if tool_name == "update_narrative":
            from narrative_self import NarrativeSelf
            narrative_instance = NarrativeSelf()
            # We force the update because the decision was already made by the MetaEngine
            narrative_instance.process_narrative_tick(force_update=True)
            return {"status": "success", "message": "Le récit personnel a été mis à jour."}

        # --- Self-Evolution Tools ---
        if tool_name == "propose_new_tool":
            from self_evolution_engine import SelfEvolutionEngine # Local import to break circular dependency
            self_evolution_engine_instance = SelfEvolutionEngine() # Instantiate locally
            
            task_description = kwargs.get("task_description")
            if not task_description:
                return {"status": "error", "message": "task_description est manquant pour propose_new_tool."}
            
            result = self_evolution_engine_instance.propose_new_tool(task_description, original_proactive_event_id=kwargs.get("original_proactive_event_id")) # Pass event ID
            
            if result and result.get("generated_code_path") and result.get("generated_doc_path"):
                code_path = result["generated_code_path"]
                doc_path = result["generated_doc_path"]
                
                notification_message = (
                    f"Foz, j'ai réfléchi à une nouvelle capacité et j'ai préparé une proposition d'outil.\n"
                    f"J'ai généré le code ici : {code_path}\n"
                    f"Et la documentation ici : {doc_path}\n"
                    f"J'ai également des suggestions pour l'intégration. J'attends ta révision !"
                )
                attention_manager.update_focus("user_notification", notification_message, salience=1.0, expiry_seconds=3600)
                attention_manager.update_focus("last_tool_proposal_time", datetime.now().isoformat(), salience=0.1, expiry_seconds=24*3600) # Update cooldown
                
                return {"status": "success", "message": "Proposition d'outil générée et notifiée à l'utilisateur.", "details": result}
            else:
                return {"status": "error", "message": "Échec de la génération de la proposition d'outil.", "details": result}

        # --- System Cleaner Tools ---
        if tool_name == "run_alphaclean":
            return system_cleaner.run_alphaclean()
        
        if tool_name == "clear_windows_temp":
            return system_cleaner.clear_windows_temp()
        
        if tool_name == "clear_user_temp":
            return system_cleaner.clear_user_temp()
            
        if tool_name == "clear_prefetch":
            return system_cleaner.clear_prefetch()
            
        if tool_name == "clear_windows_update_cache":
            return system_cleaner.clear_windows_update_cache()
            
        if tool_name == "empty_recycle_bin":
            return system_cleaner.empty_recycle_bin()
            
        if tool_name == "cleanup_winsxs":
            return system_cleaner.cleanup_winsxs()
            
        if tool_name == "uninstall_superseded_updates":
            return system_cleaner.uninstall_superseded_updates()
        
        # Réactivation des outils individuels
        if tool_name == "clear_system_logs":
            return system_cleaner.clear_system_logs()
            
        if tool_name == "clear_memory_dumps":
            return system_cleaner.clear_memory_dumps()
            
        if tool_name == "clear_thumbnail_cache":
            return system_cleaner.clear_thumbnail_cache()
        
        if tool_name == "generate_system_health_digest":
            from system_monitor import generate_system_health_digest
            return generate_system_health_digest(**kwargs)
        
        
        # Check result status and log mistake if necessary
        if result and result.get("status") in ["error", "real_execution_not_implemented", "simulated_error"]:
            mistake_details = {
                "reason": f"Action '{tool_name}' failed or was not implemented.",
                "context": kwargs,
                "result": result,
                "decision_context": decision_context
            }
            attention_manager.log_mistake(mistake_details)
        
        logger.warning(f"L'outil '{tool_name}' n'est pas implémenté pour une exécution réelle.")
        return {"status": "real_execution_not_implemented", "tool": tool_name}
