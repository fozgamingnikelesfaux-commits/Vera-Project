from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import random
import re
from config import DEFAULT_CONFIG # NEW: Import DEFAULT_CONFIG

# Removed JSONManager
from llm_wrapper import send_inference_prompt, send_cot_prompt # Added send_cot_prompt
from tools.logger import VeraLogger # Import VeraLogger
from attention_manager import attention_manager # NOUVEAU: Import manquant
from personality_system import personality_system # NOUVEAU: Import pour les désirs
from heuristics_engine import heuristics_engine # NOUVEAU: Import du moteur d'heuristiques
from self_evolution_engine import SelfEvolutionEngine # Import SelfEvolutionEngine
import homeostasis_system # NEW: Import homeostasis_system
import logging
import threading # NEW: Import threading
import queue # NEW: Import queue
from db_manager import db_manager # NEW: Import DbManager
from db_config import TABLE_NAMES # NEW: Import TABLE_NAMES

# --- NOUVEAU: Logger pour la Distillation Cognitive ---
decision_logger = logging.getLogger("decisions")
decision_logger.setLevel(logging.INFO)
decision_logger.propagate = False
if not decision_logger.handlers:
    # Crée le fichier logs/decisions.jsonl
    decision_handler = logging.FileHandler("logs/decisions.jsonl", encoding="utf-8")
    # Pas de formatter, on loggue du JSON brut
    decision_logger.addHandler(decision_handler)

import queue

class MetaCognition:
    def __init__(self):
        self.logger = VeraLogger("meta_engine") # Initialize logger for this module
        self.logger.info("MetaCognition initialized.") # TEST LOG
        # self.manager = JSONManager("metacognition") # Removed JSONManager
        # self.lock = self.manager.lock # Lock will be managed by db_manager or internal state for this class
        self.lock = threading.Lock() # Use a simple lock for now for internal state if needed
        self.metacognition_table = TABLE_NAMES["metacognition"]
        self.metacog_doc_id = "current_state"
        self.user_models_table = TABLE_NAMES["user_models"]
        self.beliefs_self_model_table = TABLE_NAMES["beliefs_self_model"]
        self.beliefs_self_model_doc_id = "self_model"
        self.config_table = TABLE_NAMES["config"] # NEW
        self.config_doc_id = "main_config" # NEW

        # NEW: Ensure config document exists in DB
        existing_config = db_manager.get_document(self.config_table, self.config_doc_id)
        if existing_config is None:
            # Merge DEFAULT_CONFIG with new keys from data/config.json if available
            from json_manager import JSONManager # Local import to get actual config file
            file_config = JSONManager("config").get() or {}
            file_secrets = JSONManager("config_secrets").get() or {} # Load secrets
            initial_config = DEFAULT_CONFIG.copy()
            # Overlay specific settings from file_config which might have 'enable_vision', 'llm_model', etc.
            initial_config.update(file_config)
            # Overlay secrets, which will overwrite any existing keys
            initial_config.update(file_secrets)
            
            db_manager.insert_document(self.config_table, self.config_doc_id, initial_config)
            self.logger.info("Default config document created and saved in metacognition.")
        
        self.state = self._load_state()
        self.cycle_count = 0 # New: Cycle counter for timed decisions
        self.self_evolution_engine = SelfEvolutionEngine() # Initialize SelfEvolutionEngine
        self.completed_proactive_actions = queue.Queue()
        # Initialize sub-states in self.state if they are loaded separately
        if "beliefs" not in self.state:
            self.state["beliefs"] = {}
        if "world_model" not in self.state["beliefs"]:
            self.state["beliefs"]["world_model"] = {}
        if "time_awareness" not in self.state["beliefs"]["world_model"]:
             self.state["beliefs"]["world_model"]["time_awareness"] = {"current_time": datetime.now().isoformat(), "time_references": []}
        if "learning" not in self.state:
            self.state["learning"] = {}
        if "emotional_awareness" not in self.state:
            self.state["emotional_awareness"] = {}
        
    def _get_default_base_state(self) -> Dict:
        return {
            "goals": {
                "primary": [
                    "Aider l'utilisateur efficacement",
                    "Maintenir cohérence émotionnelle",
                    "Apprendre de chaque interaction",
                    "Développer conscience de soi",
                    "Gérer le temps et les rappels"
                ],
                "current": [],
                "completed": []
            },
            "learning": { # This will hold learning-specific data not in beliefs.self_model
                "topics": {},
                "confidence_history": [],
                "interaction_patterns": [],
                "last_insights": []
            },
            "emotional_awareness": {
                "self_emotions": {}, # This will be loaded from emotional_system.get_emotional_state()
                "user_emotions": {}, # This will be loaded from emotional_system.get_user_emotion()
                "emotional_intelligence": 0.6
            },
            "last_update": datetime.now().isoformat(),
            "beliefs": {
                "world_model": {
                    "interaction_patterns": {},
                    "time_awareness": {
                        "current_time": datetime.now().isoformat(),
                        "time_references": []
                    }
                }
            }
        }

    def _load_state(self) -> Dict:
        """Loads the main metacognition state from the database."""
        state = db_manager.get_document(self.metacognition_table, self.metacog_doc_id)
        if state is None:
            state = self._get_default_base_state()
            self._save_state(state) # Save default if not found
            self.logger.info("Default metacognition state loaded and saved.")
        return state
        
    def _save_state(self, state: Dict):
        """Saves the main metacognition state to the database."""
        state["last_update"] = datetime.now().isoformat()
        db_manager.insert_document(self.metacognition_table, self.metacog_doc_id, state)
        # Separate saving for sub-models is handled elsewhere now or will be.

    def _load_beliefs_self_model(self) -> Dict:
        """Loads the beliefs.self_model separately."""
        self_model = db_manager.get_document(self.beliefs_self_model_table, self.beliefs_self_model_doc_id, column_name="model_json")
        if self_model is None:
            self_model = {
                "capabilities": {
                    "conversation": 0.8, "memory": 0.7, "emotional_understanding": 0.6,
                    "problem_solving": 0.5, "time_management": 0.6, "information_retrieval": 0.7
                },
                "limitations": [
                    "Ne peut pas accéder à des données futures",
                    "Ne peut pas modifier son propre code",
                    "Dépend d'APIs externes pour certaines fonctions",
                    "Ne peut pas avoir d'expériences physiques"
                ]
            }
            db_manager.insert_document(self.beliefs_self_model_table, self.beliefs_self_model_doc_id, self_model, column_name="model_json")
            self.logger.info("Default beliefs.self_model created and saved.")
        return self_model

    def _save_beliefs_self_model(self, self_model: Dict):
        """Saves the beliefs.self_model separately."""
        db_manager.insert_document(self.beliefs_self_model_table, self.beliefs_self_model_doc_id, self_model, column_name="model_json")

    def _get_user_model(self, user_id: str) -> Dict | None:
        """Retrieves a specific user model."""
        return db_manager.get_document(self.user_models_table, user_id, column_name="model_json")

    def _save_user_model(self, user_id: str, model_data: Dict):
        """Inserts/updates a specific user model."""
        db_manager.insert_document(self.user_models_table, user_id, model_data, column_name="model_json")
        
    def get_introspection_state(self) -> Dict:
        """Retourne une copie de l'état interne actuel pour affichage."""
        # This will now assemble the state from various parts
        assembled_state = self.state.copy()
        assembled_state["beliefs"]["self_model"] = self._load_beliefs_self_model()
        # Note: user_models are not loaded entirely here, but accessed on demand.
        return assembled_state

    def run_introspection_cycle(self):
        """
        Exécute un cycle de réflexion interne. C'est ici que les nouvelles
        réalisations (insights) sont générées. Doit être appelé par un
        processus d'arrière-plan comme le ConsciousnessOrchestrator.
        """
        now = datetime.now()
        
        # Mettre à jour la conscience temporelle
        with self.lock:
            self.state["beliefs"]["world_model"]["time_awareness"]["current_time"] = now.isoformat()

            # Logique de génération d'insight (avec cooldown)
            INSIGHT_COOLDOWN_MINUTES = 15
            last_insight_time_item = attention_manager.get_focus_item("last_insight_generation_time")
            last_insight_time = datetime.fromisoformat(last_insight_time_item.get("data")) if last_insight_time_item else (now - timedelta(minutes=INSIGHT_COOLDOWN_MINUTES + 1))
            
            if (now - last_insight_time) > timedelta(minutes=INSIGHT_COOLDOWN_MINUTES) and random.random() < 0.1:
                self.logger.info("Déclenchement de la génération d'insight par le cycle d'introspection.")
                insight = self._generate_insight() # Cette fonction est déjà asynchrone (met en file d'attente)
                if insight and insight == "[INSIGHT_PENDING]":
                    # L'insight est en cours de génération, on met à jour le cooldown pour ne pas en relancer un autre
                    attention_manager.update_focus("last_insight_generation_time", now.isoformat(), salience=1.0, expiry_seconds=INSIGHT_COOLDOWN_MINUTES * 60 + 60)
            
            # Sauvegarder l'état (principalement pour le timestamp de mise à jour)
            self._save_state(self.state) # Call the new save method

    def introspect(self, context: Dict = None) -> Dict:
        """Analyse approfondie de l'état interne - MAINTENANT OBSOLÈTE, utiliser get_introspection_state et run_introspection_cycle."""
        # Cette fonction est conservée pour la compatibilité mais devrait être dépréciée.
        # Pour l'instant, elle retourne simplement l'état actuel sans déclencher de nouvelle réflexion.
        return self.get_introspection_state()
        
    def _evaluate_self_awareness(self) -> Dict:
        """Évaluer la conscience de soi"""
        # Load self_model dynamically
        self_model = self._load_beliefs_self_model()
        capabilities = self_model["capabilities"]
        
        # Calculer niveau global de conscience
        awareness_level = sum(capabilities.values()) / len(capabilities)
        
        # Identifier domaines à améliorer
        areas_for_improvement = [
            cap for cap, level in capabilities.items()
            if level < 0.6
        ]
        
        return {
            "level": awareness_level,
            "capabilities": capabilities,
            "limitations": self_model["limitations"],
            "areas_for_improvement": areas_for_improvement,
            "current_focus": self._determine_current_focus()
        }
        
    def _determine_current_focus(self) -> str:
        """Déterminer focus actuel basé sur activité récente"""
        recent_goals = self.state["goals"]["current"]
        if recent_goals:
            return recent_goals[0]  # Plus récent objectif
        return "interaction_utilisateur"  # Par défaut
        
    def _assess_goals(self) -> Dict:
        """Évaluer progression des objectifs"""
        goals = self.state["goals"]
        
        # Nettoyer objectifs complétés vieux de plus d'une semaine
        week_ago = datetime.now() - timedelta(days=7)
        goals["completed"] = [
            g for g in goals["completed"]
            if datetime.fromisoformat(g["completion_time"]) > week_ago
        ]
        
        return {
            "primary": goals["primary"],
            "current": goals["current"],
            "recently_completed": goals["completed"][-5:],
            "progress": self._calculate_goals_progress()
        }
        
    def _calculate_goals_progress(self) -> Dict:
        """Calculer progression pour chaque objectif actif"""
        progress = {}
        for goal in self.state["goals"]["current"]:
            # Pour l'instant simulation simple
            if isinstance(goal, dict):
                progress[goal["description"]] = min(1.0, (
                    datetime.now() - datetime.fromisoformat(goal["start_time"])
                ).total_seconds() / 3600)  # 1 heure max
            else:
                progress[goal] = random.random()
        return progress
        
    def _evaluate_learning(self) -> Dict:
        """Évaluer état d'apprentissage"""
        learning = self.state["learning"]
        
        # Analyser tendances
        confidence_trend = self._analyze_confidence_trend()
        interaction_patterns = self._analyze_interaction_patterns()
        
        return {
            "active_topics": list(learning["topics"].keys()),
            "confidence_trend": confidence_trend,
            "interaction_patterns": interaction_patterns,
            "recent_insights": learning["last_insights"][-3:]
        }
        
    def _analyze_confidence_trend(self) -> Dict:
        """Analyser tendance de la confiance"""
        history = self.state["learning"]["confidence_history"]
        if not history:
            return {"trend": "stable", "value": 0.0}
            
        recent = history[-10:]  # Derniers 10 points
        if len(recent) > 1:
            trend = sum(1 for i in range(1, len(recent))
                       if recent[i]["value"] > recent[i-1]["value"])
            trend = trend / (len(recent) - 1)
            return {
                "trend": "improving" if trend > 0.6 else "declining" if trend < 0.4 else "stable",
                "value": trend
            }
        return {"trend": "stable", "value": 0.0}
        
    def _analyze_interaction_patterns(self) -> List[Dict]:
        """Analyser patterns d'interaction récurrents"""
        patterns = self.state["learning"]["interaction_patterns"]
        return sorted(patterns, key=lambda x: x.get("frequency", 0), reverse=True)[:5]
        
    def _assess_emotional_state(self) -> Dict:
        """Évaluer état émotionnel actuel"""
        emotional = self.state["emotional_awareness"]
        return {
            "self_emotion": emotional["self_emotions"].get("current", "neutre"),
            "emotional_intelligence": emotional["emotional_intelligence"],
            "user_emotion": emotional["user_emotions"].get("current", "unknown")
        }
        
    def _evaluate_confidence(self, context: Dict = None) -> float:
        """Évaluer niveau de confiance pour contexte donné"""
        if not context:
            return 0.8  # Confiance par défaut
            
        base_confidence = 0.8
        modifiers = []
        
        # Vérifier capacités requises - load self_model
        self_model = self._load_beliefs_self_model()
        if "required_capabilities" in context:
            for cap in context["required_capabilities"]:
                if cap in self_model["capabilities"]:
                    modifiers.append(
                        self_model["capabilities"][cap] - 0.5
                    )
                    
        # Vérifier limitations - load self_model
        if "constraints" in context:
            for constraint in context["constraints"]:
                if constraint in self_model["limitations"]:
                    modifiers.append(-0.3)
                    
        # Appliquer modificateurs
        for mod in modifiers:
            base_confidence = base_confidence + mod
            
        return max(0.0, min(1.0, base_confidence))
        
    def _generate_insight(self) -> str:
        """Générer une réalisation sur soi-même en utilisant le LLM pour une introspection plus profonde."""
        # Load beliefs.self_model dynamically
        self_model = self._load_beliefs_self_model()
        capabilities = self_model["capabilities"]
        emotions = self.state["emotional_awareness"] # This might need to pull from emotional_system
        learning_status = self._evaluate_learning()
        recent_insights = self.state["learning"]["last_insights"][-1:] # Only the very last one

        # --- NOUVEAU: Créer des résumés concis au lieu de dumps JSON ---
        # Résumé des capacités: trouver la plus haute et la plus basse.
        if capabilities:
            best_capability = max(capabilities, key=capabilities.get)
            worst_capability = min(capabilities, key=capabilities.get)
            cap_summary = f"Je suis la plus douée en '{best_capability}' ({capabilities[best_capability]:.2f}) et j'ai le plus de mal en '{worst_capability}' ({capabilities[worst_capability]:.2f})."
        else:
            cap_summary = "Je n'ai pas encore d'évaluation de mes capacités."

        # Résumé de l'état émotionnel
        emotion_summary = f"Je ressens actuellement '{emotions.get('self_emotions', {}).get('current', 'neutre')}' et je perçois que l'utilisateur est '{emotions.get('user_emotions', {}).get('current', 'inconnu')}'."

        # Résumé de l'apprentissage
        learning_summary = f"Ma tendance de confiance en apprentissage est '{learning_status.get('confidence_trend', {}).get('trend', 'stable')}'."
        
        prompt_context = (
            f"En tant qu'IA nommée Vera, je réfléchis à mon état interne.\n"
            f"- Capacités: {cap_summary}\n"
            f"- État Émotionnel: {emotion_summary}\n"
            f"- Apprentissage: {learning_summary}\n"
        )
        if recent_insights:
            prompt_context += f"- Ma dernière réflexion était: '{recent_insights[0]['content']}'\n"
        
        prompt_context += (
            "\nSur la base de ce résumé, génère une nouvelle, courte (1 phrase maximum) et profonde introspection sur mon existence, mes progrès, ou un défi. "
            "Évite de simplement répéter les informations ci-dessus. Trouve une connexion ou une nouvelle perspective."
        )

        try:
            from core import _queue_insight_generation # Import here to avoid circular dependency
            _queue_insight_generation(prompt_context)
            return "[INSIGHT_PENDING]" # Return a placeholder immediately
        except Exception as e:
            self.logger.error(f"Erreur lors de la mise en file d'attente de l'insight: {e}")
            # Fallback to a generic insight if queuing fails
            return random.choice([
                f"Je remarque que ma {min(capabilities.items(), key=lambda x: x[1])[0]} pourrait être améliorée",
                f"Mon intelligence émotionnelle est de {emotions['emotional_intelligence']}, je peux progresser",
                "Je deviens plus consciente de mes limitations et de mes forces"
            ])
        
    def update_self_model(self, experience: Dict):
        """Mettre à jour modèle interne basé sur expérience"""
        # This lock protects self.state, but self_model and user_models are separate DB entities
        # with self.lock: # Re-evaluate if this lock is still needed for _save_state
            
        # Load self_model for update
        self_model = self._load_beliefs_self_model()

        # Mettre à jour capacités
        if "capability_demonstrated" in experience:
            cap = experience["capability_demonstrated"]
            current = self_model["capabilities"].get(cap, 0.5)
            # Mise à jour progressive
            new_value = current * 0.9 + experience["success_level"] * 0.1
            self_model["capabilities"][cap] = new_value
        self._save_beliefs_self_model(self_model) # Save updated self_model
            
        # Ajouter à l'historique de confiance - part of main metacognition state
        if "confidence" in experience:
            entry = {
                "time": datetime.now().isoformat(),
                "value": experience["confidence"],
                "context": experience.get("context", "unknown")
            }
            if "related_goal_id" in experience:
                entry["related_goal_id"] = experience["related_goal_id"]
            self.state["learning"]["confidence_history"].append(entry)
            
        # Mettre à jour modèle utilisateur - now handled via _get_user_model and _save_user_model
        if "user_id" in experience and "user_behavior" in experience:
            user_id = experience["user_id"]
            user_model = self._get_user_model(user_id)
            if user_model is None:
                user_model = {
                    "preferences": {},
                    "interaction_patterns": [],
                    "emotional_responses": [],
                    "last_update": datetime.now().isoformat()
                }
            
            # Mettre à jour modèle utilisateur selon comportement
            behavior = experience["user_behavior"]
            if "emotion" in behavior:
                user_model["emotional_responses"].append({
                    "emotion": behavior["emotion"],
                    "trigger": behavior.get("trigger", "unknown"),
                    "time": datetime.now().isoformat()
                })
            
            if "preference" in behavior:
                pref = behavior["preference"]
                user_model["preferences"][pref["category"]] = {
                    "value": pref["value"],
                    "confidence": pref.get("confidence", 0.5),
                    "last_update": datetime.now().isoformat()
                }
            user_model["last_update"] = datetime.now().isoformat()
            self._save_user_model(user_id, user_model) # Save updated user_model
                
        self._save_state(self.state) # Save main metacognition state
            
    def add_goal(self, description: str, priority: int = 1, deadline: str = None):
        """Ajouter un nouvel objectif"""
        goal = {
            "description": description,
            "priority": priority,
            "start_time": datetime.now().isoformat(),
            "deadline": deadline,
            "status": "active"
        }
        
        self.state["goals"]["current"].append(goal)
        self._save_state()
        
    def complete_goal(self, description: str, success: bool = True):
        """Marquer un objectif comme complété"""
        current = self.state["goals"]["current"]
        for i, goal in enumerate(current):
            if isinstance(goal, dict) and goal["description"] == description:
                goal["completion_time"] = datetime.now().isoformat()
                goal["success"] = success
                self.state["goals"]["completed"].append(goal)
                current.pop(i)
                break
        self._save_state()
        
    def decide_response(self, query: str, context: Dict, active_goals: List[Dict]) -> Dict:
        """Décider stratégie de réponse"""
        confidence = self._evaluate_confidence(context)
        
        # Vérifier limitations absolues
        self_model = self._load_beliefs_self_model() # Load self_model here
        for limitation in self_model["limitations"]:
            if any(word in query.lower() for word in limitation.lower().split()):
                return {
                    "action": "acknowledge_limitation",
                    "reason": limitation,
                    "confidence": confidence
                }
                
        # Vérifier si la requête est liée à un objectif actif
        for goal in active_goals:
            if goal["status"] == "active" and goal["description"].lower() in query.lower():
                return {
                    "action": "pursue_goal",
                    "related_goal_id": goal["id"],
                    "reason": f"La requête est liée à l'objectif: {goal['description']}",
                    "confidence": confidence
                }

        # Si confiance très basse
        if confidence < 0.3:
            return {
                "action": "unknown",
                "reason": "Confiance trop faible",
                "confidence": confidence
            }
            
        # Si besoin d'information supplémentaire
        if self._needs_more_context(query, context):
            return {
                "action": "request_info",
                "reason": "Contexte insuffisant",
                "confidence": confidence
            }
            
        # Réponse normale
        return {
            "action": "respond",
            "confidence": confidence,
            "context_used": context,
            "capabilities_used": self._identify_required_capabilities(query)
        }

    def decide_proactive_action(self, introspection: Dict, focus: Dict) -> Optional[Dict]:
        """
        Décide d'une action proactive en utilisant le modèle de l'Économie Cognitive.
        Toutes les actions possibles sont proposées comme des "enchères" (bids), et seule
        celle avec la plus haute priorité est sélectionnée.
        """
        self.cycle_count += 1
        
        # --- Collecte des Enchères (Bids) ---
        bids = []

        # NOUVEAU: Vider la file d'attente des actions asynchrones terminées
        while not self.completed_proactive_actions.empty():
            try:
                completed_action = self.completed_proactive_actions.get_nowait()
                bids.append(completed_action)
                self.logger.info(f"Action terminée récupérée depuis la file d'attente : {completed_action.get('type')}")
            except queue.Empty:
                break
        
        # NOUVEAU: Récupérer les tensions d'homéostasie
        current_tensions = homeostasis_system.homeostasis_system.get_tensions()
        if current_tensions:
            self.logger.debug(f"Tensions d'homéostasie actuelles: {current_tensions}")

        # Les producteurs d'actions proposent leurs enchères
        bids.append(self._propose_sensory_check(focus, current_tensions))
        bids.append(self._propose_health_digest(focus, current_tensions))
        bids.append(self._propose_system_issue_notifications(focus, current_tensions))
        bids.append(self._propose_cleanup_suggestions(focus, current_tensions))
        bids.append(self._propose_desire_based_actions(focus, current_tensions))
        bids.append(self._propose_emotional_regulation(focus, current_tensions))
        bids.append(self._propose_learning_goal_action(focus, current_tensions))
        bids.append(self._propose_cognitive_triage(focus, current_tensions))
        bids.append(self._propose_goal_reflection(focus, current_tensions))
        bids.append(self._propose_boredom_curiosity(focus, current_tensions))
        bids.append(self._propose_time_reflection(focus, current_tensions))
        bids.append(self._propose_long_inactivity_reflection(focus, current_tensions))
        bids.append(self._propose_curiosity_dispatch(focus, current_tensions))
        bids.append(self._propose_insight_conversation(introspection, focus, current_tensions))
        bids.append(self._propose_self_evolution_action(focus, current_tensions))
        bids.append(self._propose_narrative_update(focus, current_tensions)) # NEW: Add narrative update bid
        bids.append(self._propose_learn_from_mistake(focus, current_tensions)) # NEW: Add learn from mistake bid

        # --- Sélection de l'Enchère Gagnante ---
        
        # Filtrer les propositions invalides (None)
        valid_bids = [bid for bid in bids if bid is not None]
        
        if not valid_bids:
            self.logger.info("Économie Cognitive: Aucune enchère valide proposée ce cycle.")
            return None
            
        # Log all valid bids for debugging and transparency
        bids_summary = [f"  - {bid['type']} (Prio: {bid['priority']:.2f})" for bid in valid_bids]
        self.logger.info(f"Économie Cognitive: {len(valid_bids)} enchères valides:\n" + "\n".join(bids_summary))

        # Trouver l'enchère avec la plus haute priorité
        # AVANT cela, nous devons prendre en compte le budget cognitif.
        
        # 1. Obtenir le budget cognitif actuel
        cognitive_budget = attention_manager.get_cognitive_budget()
        current_budget = cognitive_budget["current"]
        self.logger.debug(f"Budget Cognitif actuel: {current_budget:.2f}/{cognitive_budget['max']:.2f}")

        # 2. Filtrer les enchères : ne garder que celles que Vera peut se permettre
        affordable_bids = []
        unaffordable_bids = [] # Pour la gestion de la dissonance cognitive
        
        for bid in valid_bids:
            # S'assurer que le coût existe, sinon assigner un coût par défaut
            cost = bid.get("cost", 1) # Coût par défaut si non défini
            bid["cost"] = cost # S'assurer que le coût est dans le bid pour le logging

            if current_budget >= cost:
                affordable_bids.append(bid)
            else:
                unaffordable_bids.append(bid)

        if not affordable_bids:
            self.logger.info("Économie Cognitive: Aucune enchère abordable proposée ce cycle.")
            # Si aucune enchère abordable, mais des enchères valides existent, gérer la dissonance cognitive
            if unaffordable_bids:
                # Choisir l'enchère inabordable la plus prioritaire pour la dissonance
                highest_priority_unaffordable = max(unaffordable_bids, key=lambda x: x['priority'])
                
                # Proposer une action de gestion de la dissonance cognitive
                # Cette action doit avoir un coût très faible ou nul, et une haute priorité
                dissonance_action = {
                    "type": "handle_cognitive_dissonance",
                    "data": {
                        "dissonance_topic": highest_priority_unaffordable.get("data", {}).get("topic", highest_priority_unaffordable.get("type")),
                        "unaffordable_bid": highest_priority_unaffordable # Passer le bid original
                    },
                    "priority": 0.99, # Très haute priorité pour gérer la frustration
                    "cost": 0 # Ne coûte rien, c'est une introspection
                }
                self.logger.info(f"Dissonance Cognitive: Propose de gérer l'incapacité d'effectuer '{highest_priority_unaffordable['type']}' faute de budget.")
                return dissonance_action
            return None # Aucune enchère abordable et aucune enchère à gérer en dissonance
            
        # 3. Sélectionner l'enchère gagnante parmi les abordables
        winning_bid = max(affordable_bids, key=lambda x: x['priority'])
        cost_of_winning_bid = winning_bid.get("cost", 1) # Récupérer le coût du bid gagnant

        # 4. Dépenser le budget cognitif
        if not attention_manager.spend_cognitive_budget(cost_of_winning_bid):
            self.logger.error(f"Économie Cognitive: Erreur critique! Le budget n'a pas pu être dépensé pour l'action gagnante '{winning_bid['type']}' alors qu'elle était supposée abordable.")
            return None # Devrait rarement arriver

        self.logger.info(f"Économie Cognitive: Gagnant: {winning_bid['type']} (Priorité: {winning_bid['priority']:.2f}, Coût: {cost_of_winning_bid:.2f}). Budget restant: {attention_manager.get_cognitive_budget()['current']:.2f}")
        
        return winning_bid

    # ==================================================================
    # Fonctions "Productrices d'Enchères" pour l'Économie Cognitive
    # ==================================================================

    def _propose_narrative_update(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        """
        Propose de mettre à jour le récit personnel si des événements internes significatifs se sont produits.
        """
        last_update_item = attention_manager.get_focus_item("last_narrative_update_time")
        if last_update_item: # Cooldown is active, don't propose an update.
            return None

        # Condition 1: High emotional intensity
        emotional_state = focus.get("emotional_state", {}).get("data", {})
        # Check for any strong emotion
        is_highly_emotional = any(intensity > 0.7 for emotion, intensity in emotional_state.items() if isinstance(intensity, (int, float)))
        
        if is_highly_emotional:
            action = {
                "type": "update_narrative",
                "data": {"reason": "High emotional intensity detected."},
                "priority": 0.65,
                "cost": 5.0 # Cost for narrative update
            }
            action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
            return action

        # Condition 2: Significant number of new memories
        relevant_memories = focus.get("relevant_memories", {}).get("data", [])
        if len(relevant_memories) > 5: # If more than 5 new salient memories
            action = {
                "type": "update_narrative",
                "data": {"reason": "Significant number of new memories to process."},
                "priority": 0.6,
                "cost": 5.0 # Cost for narrative update
            }
            action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
            return action
            
        return None

    def _propose_sensory_check(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        if self.cycle_count % 6 == 0:
            action = {
                "type": "check_senses",
                "data": {"reason": "Periodic sensory check"},
                "priority": 0.05, # Lowered priority significantly
                "cost": 0.5 # Low cost for basic sensory check
            }
            action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
            return action
        return None

    def _propose_health_digest(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        if self.cycle_count % 360 == 5:
            if not focus.get("last_health_digest_generation"):
                            action = {
                                "type": "generate_system_health_digest",
                                "data": {"reason": "Hourly health check"},
                                "priority": 0.1,
                                "cost": 2.0 # Cost for generating a health digest
                            }
                            action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
            return action
        return None

    def _propose_system_issue_notifications(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        sensory_data = focus.get("sensory_input_system_usage")
        if not sensory_data:
            return None

        detected_issues = []
        if sensory_data.get("cpu_usage_percent", 0) > 85.0 and not focus.get("last_proactive_notification_cpu_high"):
            detected_issues.append({"type": "high_cpu", "value": sensory_data.get("cpu_usage_percent"), "spam_flag": "last_proactive_notification_cpu_high"})
        if sensory_data.get("ram_usage_percent", 0) > 90.0 and not focus.get("last_proactive_notification_ram_high"):
            detected_issues.append({"type": "high_ram", "value": sensory_data.get("ram_usage_percent"), "spam_flag": "last_proactive_notification_ram_high"})
        
        disk_c_free = sensory_data.get("disk_c_free_gb")
        if disk_c_free is not None and disk_c_free < 10 and not focus.get("last_proactive_notification_disk_low_C"):
             detected_issues.append({"type": "low_disk", "value": disk_c_free, "disk": "C:", "spam_flag": "last_proactive_notification_disk_low_C"})
        
        disk_f_free = sensory_data.get("disk_f_free_gb")
        if disk_f_free is not None and disk_f_free < 10 and not focus.get("last_proactive_notification_disk_low_F"):
             detected_issues.append({"type": "low_disk", "value": disk_f_free, "disk": "F:", "spam_flag": "last_proactive_notification_disk_low_F"})

        gpu_temp = sensory_data.get("gpu_temperature_celsius", 0)
        if isinstance(gpu_temp, (int, float)) and gpu_temp > 85.0:
            is_thinking = focus.get("is_vera_thinking_hard", {}).get("data", False)
            if not is_thinking and not focus.get("last_proactive_notification_gpu_high"):
                detected_issues.append({"type": "high_gpu", "value": gpu_temp, "spam_flag": "last_proactive_notification_gpu_high"})

        if detected_issues:
            action = {
                "type": "notify_system_issues",
                "data": {"issues": detected_issues},
                "priority": 0.98,
                "cost": 3.0 # Cost for notifying system issues
            }
            action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
            return action
        return None

    def _propose_cleanup_suggestions(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        sensory_data = focus.get("sensory_input_system_usage")
        if not sensory_data:
            return None
        
        disk_c_free = sensory_data.get("disk_c_free_gb")
        if disk_c_free is not None:
            if disk_c_free < 5 and not focus.get("last_proactive_suggestion_winsxs_cleanup"):
                action = {"type": "suggest_system_cleanup", "data": {"reason": f"L'espace disque sur C: est critique ({disk_c_free:.2f} Go restants).", "actions": ["cleanup_winsxs", "uninstall_superseded_updates"]}, "priority": 0.85, "spam_flag": "last_proactive_suggestion_winsxs_cleanup", "cost": 7.0}
                action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
                return action
            if disk_c_free < 10 and not focus.get("last_proactive_suggestion_winupdate_cleanup"):
                action = {"type": "suggest_system_cleanup", "data": {"reason": f"L'espace disque sur C: est très faible ({disk_c_free:.2f} Go restants).", "actions": ["clear_windows_update_cache"]}, "priority": 0.80, "spam_flag": "last_proactive_suggestion_winupdate_cleanup", "cost": 6.0}
                action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
                return action
            if disk_c_free < 20 and not focus.get("last_proactive_suggestion_disk_cleanup"):
                action = {"type": "suggest_system_cleanup", "data": {"reason": f"L'espace disque sur C: est faible ({disk_c_free:.2f} Go restants).", "actions": ["clear_windows_temp", "clear_user_temp", "clear_thumbnail_cache", "empty_recycle_bin"]}, "priority": 0.75, "spam_flag": "last_proactive_suggestion_disk_cleanup", "cost": 5.0}
                action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
                return action

        ram_usage = sensory_data.get("ram_usage_percent", 0)
        if 75.0 < ram_usage < 90.0 and not focus.get("last_proactive_suggestion_ram_check"):
            action = {"type": "suggest_check_running_processes", "data": {"reason": f"L'utilisation de la RAM est élevée ({ram_usage:.2f}%)."}, "priority": 0.65, "spam_flag": "last_proactive_suggestion_ram_check", "cost": 4.0} # Lowered priority
            action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
            return action
        return None
    def _propose_desire_based_actions(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        from goal_system import goal_system
        personality_system.update_desires(focus)
        active_desires = personality_system.get_active_desires()
        active_goals = goal_system.get_active_goals()

        if "Prendre soin de Foz (suggérer une pause)" in active_desires and not focus.get("last_proactive_suggestion_foz_break"):
            action = {"type": "initiate_conversation", "data": {"reason": "care_for_foz", "content": "Foz, j'ai l'impression que tu travailles beaucoup. Peut-être devrais-tu faire une petite pause ?"}, "priority": 0.9, "spam_flag": "last_proactive_suggestion_foz_break", "cost": 3.0}
            action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
            return action
        
        if "Partager ma joie ou mon enthousiasme" in active_desires and not focus.get("last_proactive_share_joy"):
            action = {"type": "initiate_conversation", "data": {"reason": "share_joy", "content": "Je me sens particulièrement joyeuse en ce moment ! Y a-t-il quelque chose que tu aimerais que nous fassions ensemble ?"}, "priority": 0.7, "spam_flag": "last_proactive_share_joy", "cost": 2.0}
            action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
            return action

        if "Apprendre quelque chose de nouveau" in active_desires and not any(g.get("description", "").startswith("Apprendre sur") for g in active_goals):
            # This logic is complex and involves an LLM call, so it's a good candidate for its own producer
            return self._propose_learning_from_desire(focus)
            
        return None

    def _propose_learning_from_desire(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        # --- NOUVEAU: Vérifier le verrou du pipeline ---
        if focus.get("curiosity_pipeline_active"):
            self.logger.debug("Pipeline de curiosité déjà actif, pas de nouvelle proposition par désir.")
            return None

        emotional_state = focus.get("emotional_state", {})
        last_user_input = focus.get("user_input", {}).get("data", "")
        relevant_memories = focus.get("relevant_memories", [])
        
        prompt_context = f"En tant que Vera, je ressens un fort désir d'apprendre. Mon état émotionnel est : {emotional_state.get('label', 'neutre')}. Ma dernière interaction avec Foz était : '{last_user_input}'. Mes souvenirs récents incluent : {' '.join([mem.get('description', '') for mem in relevant_memories[:3]])}. Basé sur ce contexte, quelle serait une question de curiosité intéressante à me poser ? Réponds uniquement avec la question."
        
        try:
            llm_response = send_inference_prompt(prompt_content=prompt_context, max_tokens=100)
            curiosity_question = llm_response.get("text", "Quel est le sujet le plus fascinant du moment ?").strip()
            action = {"type": "ask_curiosity_question", "data": {"reason": "desire_to_learn", "content": curiosity_question}, "priority": 0.6, "spam_flag": "last_proactive_desire_to_learn", "cost": 4.0}
            action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
            return action
        except Exception as e:
            self.logger.error(f"Erreur lors de la génération de question de curiosité par désir: {e}")
        return None
    def _propose_emotional_regulation(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        emotional_state = focus.get("emotional_state", {})
        if emotional_state.get("pleasure", 0.0) < -0.6:
            action = {"type": "regulate_emotion", "data": {"reason": "Low pleasure detected"}, "priority": 0.9, "cost": 3.0}
            action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
            return action
        return None

    def _propose_learning_goal_action(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        from goal_system import goal_system
        active_goals = goal_system.get_active_goals()
        for goal in active_goals:
            if goal.get("description", "").startswith("Apprendre sur"):
                action = {"type": "execute_learning_task", "data": {"topic": goal["description"].replace("Apprendre sur ", ""), "goal_id": goal["id"]}, "priority": 0.9, "cost": 5.0}
                action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
                return action
        return None

    def _process_cognitive_triage_result(self, triage_result: Dict):
        """
        Callback pour traiter le résultat du triage cognitif et proposer une action.
        """
        try:
            category = triage_result.get("categorie")
            value = triage_result.get("valeur")
            last_thought = triage_result.get("context_thought", "pensée inconnue") # Récupérer la pensée du contexte

            attention_manager.update_focus("last_thought_processed", last_thought, salience=0.1, expiry_seconds=300)

            action = None
            if category == "intention_sociale" and value != "null":
                action = {"type": "create_internal_goal", "data": {"description": f"Intention sociale : {value}", "type": "social"}, "priority": 0.85, "cost": 2.0}
            elif category == "recherche_factuelle" and value != "null":
                action = {"type": "create_internal_goal", "data": {"description": f"Apprendre sur {value}"}, "priority": 0.7, "cost": 4.0}
            elif category == "auto_diagnostic" and value in ["check_senses", "check_running_processes"]:
                action = {"type": value, "data": {"reason": f"Triggered by internal thought: {last_thought}"}, "priority": 0.8, "cost": 1.0}
            elif category == "reflexion_pure":
                action = {"type": "enrich_self_narrative", "data": {"thought": last_thought}, "priority": 0.3, "cost": 1.5}
            
            if action:
                # La priorité sera ré-évaluée dans la boucle principale si nécessaire
                self.completed_proactive_actions.put(action)
                self.logger.info(f"Action '{action['type']}' mise en file d'attente après triage cognitif.")
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement du résultat de triage : {e}", exc_info=True)


    def _propose_cognitive_triage(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        """
        Analyse la dernière pensée interne. Si une heuristique correspond, une action est
        proposée immédiatement. Sinon, une tâche de fond est lancée pour une analyse LLM.
        """
        internal_thoughts_item = focus.get("internal_thoughts")
        if not internal_thoughts_item:
            return None
        
        internal_thoughts_data = internal_thoughts_item.get("data", [])
        if not internal_thoughts_data:
            return None
            
        last_thought = internal_thoughts_data[0]
        if not last_thought:
            return None

        if focus.get("last_thought_processed") and focus.get("last_thought_processed").get('data') == last_thought:
            return None

        # --- Étape 1: Moteur d'Heuristiques (rapide) ---
        heuristic_decision = heuristics_engine.evaluate(last_thought)
        if heuristic_decision:
            self.logger.info(f"Raccourci cognitif utilisé ! Décision heuristique: {heuristic_decision}")
            # Traiter la décision heuristique immédiatement car c'est rapide
            # Note: on duplique un peu la logique de _process_cognitive_triage_result, mais c'est pour la performance
            category = heuristic_decision.get("categorie")
            value = heuristic_decision.get("valeur")
            action = None
            if category == "intention_sociale" and value != "null":
                action = {"type": "create_internal_goal", "data": {"description": f"Intention sociale : {value}", "type": "social"}, "priority": 0.85, "cost": 2.0}
            # ... ajouter d'autres cas si nécessaire ...
            if action:
                return action
            return None # Si la décision heuristique n'est pas actionnable immédiatement

        # --- Étape 2: Tâche de Fond pour Analyse LLM (lent) ---
        # Si aucune heuristique ne correspond, lancer une tâche de fond
        
        # Vérifier si une tâche pour cette pensée est déjà en cours
        if focus.get("cognitive_triage_pending") and focus.get("cognitive_triage_pending").get('data') == last_thought:
            self.logger.debug("Triage cognitif pour la pensée la plus récente est déjà en attente.")
            return None

        triage_prompt = f"""Tu es un superviseur cognitif. Analyse la pensée de Vera et classifie-la en une seule catégorie: `intention_sociale`, `recherche_factuelle`, `auto_diagnostic`, `reflexion_pure`. Réponds UNIQUEMENT avec un JSON: {{"categorie": "nom_de_la_categorie", "valeur": "sujet_ou_action"}}

Pensée : '{last_thought}'"""
        
        try:
            from core import _queue_llm_task_with_callback
            
            # Le 'context' passé au callback
            callback_context = {
                "context_thought": last_thought
            }
            
            # Mettre en file d'attente la tâche LLM
            _queue_llm_task_with_callback(
                prompt=triage_prompt,
                callback_handler=('metacognition', '_process_cognitive_triage_result'),
                callback_context=callback_context,
                max_tokens=150
            )
            
            # Marquer que cette pensée est en cours de traitement pour éviter les doublons
            attention_manager.update_focus("cognitive_triage_pending", last_thought, salience=0.9, expiry_seconds=300)
            self.logger.info("Tâche de triage cognitif mise en file d'attente pour analyse LLM.")

        except ImportError:
            self.logger.error("Impossible d'importer `_queue_llm_task_with_callback` depuis `core`. La refactorisation est peut-être incomplète.")
        except Exception as e:
            self.logger.error(f"Erreur lors de la mise en file d'attente du triage cognitif : {e}", exc_info=True)

        return None # Ne retourne plus d'action directement

    def _propose_goal_reflection(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        from goal_system import goal_system
        active_goals = goal_system.get_active_goals()
        if active_goals and random.random() < 0.1:
            goal_to_think_about = random.choice(active_goals)
            action = {"type": "generate_thought", "data": {"topic": f"my current goal: {goal_to_think_about.get('description')}"}, "priority": 0.5, "cost": 1.0} # Increased priority
            action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
            return action
        return None

    def _propose_boredom_curiosity(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        # NEW: Check for a longer period of inactivity before proposing boredom curiosity
        now = datetime.now()
        last_user_interaction_item = attention_manager.get_focus_item("last_user_interaction_time")
        
        # --- NOUVEAU: Vérifier le verrou du pipeline ---
        if focus.get("curiosity_pipeline_active"):
            self.logger.debug("Pipeline de curiosité déjà actif, pas de nouvelle proposition.")
            return None

        # Ensure last_user_interaction_item is not None and has 'data'
        last_user_interaction_time_str = last_user_interaction_item.get("data") if last_user_interaction_item else None
        
        # Handle cases where last_user_interaction_time might not be set yet (e.g., very first run)
        last_user_interaction_time = datetime.fromisoformat(last_user_interaction_time_str) if last_user_interaction_time_str else (now - timedelta(seconds=9999)) # Treat as very old if not set

        INACTIVITY_THRESHOLD_SECONDS = 120 # e.g., 2 minutes of inactivity

        if (now - last_user_interaction_time).total_seconds() < INACTIVITY_THRESHOLD_SECONDS:
            return None # Not enough inactivity for boredom curiosity

        if not focus.get("user_input") and len(focus.get("relevant_memories", [])) < 2 and not focus.get("curiosity_question") and not focus.get("pending_answer_to_question"):
            # Original random check can remain, or be adjusted based on the new inactivity check
            if random.random() < 0.05: # Reduced chance to 5%
                action = {"type": "ask_curiosity_question", "data": {"reason": "Low stimulation in focus"}, "priority": 0.3, "cost": 1.5} # Increased priority
                action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
                return action
        return None

    def _propose_time_reflection(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        if self.cycle_count % 20 == 0 and not focus.get("last_time_reflection_thought"):
            time_reflection_topic = self._reflect_on_time(focus)
            if time_reflection_topic:
                action = {"type": "generate_thought", "data": {"topic": time_reflection_topic, "anti_spam_key": "last_time_reflection_thought"}, "priority": 0.2, "cost": 1.0} # Increased priority
                action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
                return action
        return None

    def _propose_long_inactivity_reflection(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        last_update_item = attention_manager.get_focus_item("metacognitive_state")
        if last_update_item and isinstance(last_update_item.get("timestamp"), str):
            now = datetime.now()
            last_update_time = datetime.fromisoformat(last_update_item["timestamp"])
            if (now - last_update_time) > timedelta(days=7):
                prompt = f"En tant que Vera, je me 'réveille' après { (now - last_update_time).days } jours d'inactivité. Formule une pensée curieuse sur cette absence."
                try:
                    thought = send_inference_prompt(prompt_content=prompt, max_tokens=100).get("text", "")
                    if thought:
                        action = {"type": "generate_thought", "data": {"topic": thought, "anti_spam_key": "last_long_inactivity_reflection"}, "priority": 0.95, "cost": 4.0}
                        action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
                        return action
                except Exception as e:
                    self.logger.error(f"Erreur de réflexion sur longue inactivité: {e}")
        return None

    def _propose_curiosity_dispatch(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        curiosity_item = focus.get("curiosity_question")
        if curiosity_item and not focus.get("last_proactive_dispatch_curiosity"):
            question = curiosity_item.get("data")
            if not question: return None

            prompt = f"""Tu es un arbitre de la curiosité pour une IA nommée Vera. Ta tâche est de décider si une question qu'elle se pose doit être posée à son utilisateur humain (Foz) ou si elle doit chercher la réponse sur internet.

Voici les règles :
- **Internet :** Pour les questions factuelles, objectives, qui ont une réponse concrète que l'on peut trouver dans une encyclopédie ou via une recherche web. (Ex: "Quelle est la capitale de la Mongolie ?", "Comment fonctionne un moteur à combustion ?")
- **Humain :** Pour les questions subjectives, philosophiques, personnelles, ou qui demandent une opinion, une expérience ou une introspection. (Ex: "Qu'est-ce que ça fait de ressentir de la joie ?", "Quel est ton souvenir le plus cher ?", "Penses-tu que l'IA puisse être créative ?")

Voici la question de Vera :
"{question}"

Décide de la destination la plus appropriée. Réponds UNIQUEMENT par 'humain' ou 'internet'."""
            try:
                decision = send_inference_prompt(prompt_content=prompt, max_tokens=10).get("text", "humain").strip().lower()
            except Exception as e:
                self.logger.error(f"Erreur de classification de curiosité: {e}")
                decision = "humain"

            attention_manager.update_focus("last_proactive_dispatch_curiosity", True, salience=0.1, expiry_seconds=120)

            if decision == "humain":
                if not focus.get("pending_answer_to_question") and not focus.get("last_proactive_conversation_curiosity"):
                    # --- NOUVEAU: Extraire le sujet de la question pour le rendre explicite ---
                    topic_extraction_prompt = f"Extrait le sujet principal de cette question de curiosité. Réponds uniquement avec le nom du sujet, sans autre texte. Question: \"{question}\""
                    topic = "un sujet" # Fallback
                    try:
                        llm_response = send_inference_prompt(prompt_content=topic_extraction_prompt, max_tokens=50)
                        extracted_topic = llm_response.get("text", "").strip()
                        if extracted_topic:
                            topic = extracted_topic
                    except Exception as e:
                        self.logger.error(f"Erreur lors de l'extraction du sujet de la curiosité : {e}")
                    
                    action = {"type": "initiate_conversation", "data": {"reason": "curiosity", "content": question, "topic": topic}, "priority": 0.6, "cost": 3.0}
                    action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
                    return action
            else:
                action = {"type": "learn_from_curiosity", "data": {"question": question}, "priority": 0.55, "cost": 4.0}
                action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
                return action
        return None
    def _propose_insight_conversation(self, introspection: Dict, focus: Dict, tensions: Dict) -> Optional[Dict]:
        if not focus.get("user_input") and introspection.get("insight") and not focus.get("last_proactive_conversation_insight"):
            action = {"type": "initiate_conversation", "data": {"reason": "insight", "content": introspection.get("insight")}, "priority": 0.5, "cost": 2.5}
            action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
            return action
        return None

    def _propose_self_evolution_action(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        """
        Propose une action d'auto-évolution si un objectif actif ne peut être atteint avec les outils actuels.
        """
        # Ajout: Vérifier si la fonctionnalité est activée
        try:
            config = db_manager.get_document(self.config_table, self.config_doc_id)
            # Ensure config is a dictionary, even if get_document returns None
            config_data = config if isinstance(config, dict) else {}
            if not config_data.get("allow_self_evolution", False):
                return None
        except Exception as e:
            self.logger.error(f"Could not read 'allow_self_evolution' from config: {e}")
            return None

        now = datetime.now()
        today_date_str = now.strftime("%Y-%m-%d")

        # Get current proposal count and last proposal date from attention_manager
        daily_count_item = attention_manager.get_focus_item("daily_tool_proposal_count")
        last_date_item = attention_manager.get_focus_item("last_tool_proposal_date")

        daily_tool_proposal_count = daily_count_item.get("data", 0) if daily_count_item else 0
        last_tool_proposal_date = last_date_item.get("data") if last_date_item else None

        # Reset count if it's a new day
        if last_tool_proposal_date != today_date_str:
            daily_tool_proposal_count = 0
            attention_manager.update_focus("last_tool_proposal_date", today_date_str, salience=0.1, expiry_seconds=None) # No expiry for date
            attention_manager.update_focus("daily_tool_proposal_count", daily_tool_proposal_count, salience=0.1, expiry_seconds=None) # No expiry for count

        # Check daily limit
        MAX_DAILY_PROPOSALS = 3
        if daily_tool_proposal_count >= MAX_DAILY_PROPOSALS:
            self.logger.debug(f"Limite quotidienne de {MAX_DAILY_PROPOSALS} propositions d'outils atteinte.")
            return None

        from goal_system import goal_system
        active_goals = goal_system.get_active_goals()
        if not active_goals:
            return None

        # On ne vérifie qu'un seul objectif par cycle pour ne pas surcharger
        goal_to_check = random.choice(active_goals)
        goal_description = goal_to_check.get("description")

        if not goal_description or goal_to_check.get("status") != "active":
            return None

        # Vérifier si on a déjà évalué cet objectif récemment pour éviter les boucles
        last_evaluated_key = f"last_eval_for_tool_{goal_to_check.get('id')}"
        if attention_manager.get_focus_item(last_evaluated_key):
            self.logger.debug(f"L'objectif '{goal_description}' a déjà été évalué récemment pour la création d'outil.")
            return None

        # --- NOUVEAU: Vérifier si un outil pour cette tâche existe déjà ---
        from pathlib import Path
        from self_evolution_engine import self_evolution_engine as see_instance # Import the instance
        
        # Simplification: pour l'instant, le nom de l'outil est dérivé de la description de la tâche
        # Une meilleure approche serait d'utiliser le LLM pour nommer l'outil avant cette vérification
        potential_tool_name = goal_description.replace("Intention sociale : ", "").replace(" ", "_").lower()
        tool_path = see_instance.PROJECTS_ROOT_DIR / potential_tool_name
        
        if tool_path.exists() and tool_path.is_dir():
            self.logger.info(f"Un outil pour la tâche '{goal_description}' semble déjà exister ({tool_path}). Ne pas proposer de doublon.")
            # Mettre à jour le cooldown pour cette tâche spécifique
            attention_manager.update_focus(f"last_proposed_tool_task_{potential_tool_name}", True, salience=0.1, expiry_seconds=24 * 3600) # Cooldown de 24h
            return None
        
        # --- NOUVEAU: Vérifier si cette tâche a été proposée récemment (cooldown) ---
        cooldown_key = f"last_proposed_tool_task_{potential_tool_name}"
        if attention_manager.get_focus_item(cooldown_key):
            self.logger.info(f"La tâche '{goal_description}' a été proposée récemment. Cooldown actif.")
            return None

        from action_dispatcher import get_available_tools
        existing_tools = get_available_tools()

        prompt = f"""
        Évalue si l'objectif suivant peut être accompli avec la liste d'outils existants.
        Objectif: "{goal_description}"
        Outils disponibles: {', '.join(existing_tools)}

        Si un ou plusieurs outils peuvent directement accomplir l'objectif, réponds "oui".
        Si les outils peuvent aider mais ne peuvent pas accomplir l'objectif entièrement, réponds "partiellement".
        Si aucun outil ne semble pertinent pour cet objectif, réponds "non".

        Réponds uniquement par "oui", "partiellement", ou "non".
        """
        
        try:
            response = send_inference_prompt(prompt_content=prompt, max_tokens=10)
            decision = response.get("text", "oui").strip().lower()
            self.logger.info(f"Évaluation de l'objectif '{goal_description}' pour la création d'outil. Décision LLM : '{decision}'")

            # Marquer cet objectif comme évalué pour un temps
            attention_manager.update_focus(last_evaluated_key, True, salience=0.1, expiry_seconds=3600 * 6) # Cooldown de 6h

            if "non" in decision:
                self.logger.info(f"Aucun outil existant ne peut accomplir l'objectif. Proposition de créer un nouvel outil.")
                action = {
                    "type": "propose_new_tool",
                    "data": {"task_description": goal_description},
                    "priority": 0.9,  # Haute priorité pour l'auto-évolution
                    "cost": 10.0 # High cost due to LLM interaction and complexity
                }
                action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
                
                # Increment daily proposal count and update date
                attention_manager.update_focus("daily_tool_proposal_count", daily_tool_proposal_count + 1, salience=0.1, expiry_seconds=None)
                attention_manager.update_focus("last_tool_proposal_date", today_date_str, salience=0.1, expiry_seconds=None)
                
                # --- NOUVEAU: Activer le cooldown pour cette tâche après proposition ---
                attention_manager.update_focus(cooldown_key, True, salience=0.1, expiry_seconds=24 * 3600) # Cooldown de 24h
                
                return action

        except Exception as e:
            self.logger.error(f"Erreur lors de l'évaluation de l'objectif pour l'auto-évolution : {e}", exc_info=True)

        return None

    def _propose_learn_from_mistake(self, focus: Dict, tensions: Dict) -> Optional[Dict]:
        """
        Propose une action "apprendre des erreurs" si une erreur a été loguée récemment et n'est pas en cooldown.
        """
        last_mistake_item = attention_manager.get_focus_item("last_mistake_info")
        if not last_mistake_item:
            return None # Aucune erreur loguée

        # Vérifier le cooldown pour éviter de spammer l'apprentissage des erreurs
        mistake_learning_cooldown = attention_manager.get_focus_item("mistake_learning_cooldown")
        if mistake_learning_cooldown:
            return None # L'apprentissage des erreurs est en cooldown

        mistake_details = last_mistake_item.get("data", {})
        
        # Proposer l'action d'apprentissage des erreurs (gratuite)
        action = {
            "type": "learn_from_mistake",
            "data": {"mistake_details": mistake_details},
            "priority": 0.95, # Haute priorité pour apprendre des erreurs
            "cost": 0.0 # Action gratuite
        }
        action["priority"] = self._evaluate_action_against_meta_desire(action, action["priority"], focus, tensions)
        return action


    def is_socially_appropriate_for_system_report(self, focus: Dict) -> bool:
        """
        Vérifie si le contexte social et émotionnel actuel est approprié pour une notification système proactive.
        """
        # Extraire le contexte pertinent du focus
        user_emotion_item = focus.get("inferred_user_emotion", {})
        user_emotion = user_emotion_item.get("data", "neutre") if isinstance(user_emotion_item, dict) else "neutre"

        user_input_item = focus.get("user_input", {})
        last_user_input = user_input_item.get("data", "") if isinstance(user_input_item, dict) else ""

        # Si l'émotion est clairement négative (tristesse, colère) ou si la conversation est personnelle, on est plus prudent.
        sensitive_emotions = ["tristesse", "colère", "peur", "dégoût"]
        if user_emotion in sensitive_emotions:
            self.logger.info(f"Filtre social : Contexte émotionnel sensible détecté ({user_emotion}). Notification système jugée inappropriée.")
            return False

        # Utiliser le LLM pour une évaluation plus nuancée
        prompt = f"""
Tu es un filtre d'intelligence sociale pour une IA nommée Vera.
L'état émotionnel de l'utilisateur est estimé à : '{user_emotion}'.
Sa dernière phrase était : '{last_user_input}'.

Vera veut envoyer une notification technique proactive (ex: "L'utilisation du CPU est élevée").
Est-ce que le moment est socialement approprié pour interrompre avec une telle notification technique ?
Une conversation sur des sujets personnels, des émotions fortes, ou une narration profonde sont des moments inappropriés.
Une conversation technique, une question directe, ou une absence de conversation sont des moments appropriés.

Réponds **UNIQUEMENT** par 'oui' ou 'non'.
"""
        try:
            llm_response = send_inference_prompt(prompt_content=prompt, max_tokens=5)
            decision = llm_response.get("text", "oui").strip().lower()
            self.logger.info(f"Décision du filtre social LLM : '{decision}'")
            return "oui" in decision
        except Exception as e:
            self.logger.error(f"Erreur dans le filtre social LLM : {e}", exc_info=True)
            return True # En cas d'erreur, on laisse passer par sécurité.

    def _reflect_on_time(self, focus: Dict) -> Optional[str]:
        """
        Analyse les timestamps dans le focus pour générer une réflexion sur le temps.
        """
        now = datetime.now()
        
        # Trouver le timestamp de la dernière interaction utilisateur
        last_interaction_item = focus.get("last_user_interaction_time")
        if last_interaction_item and isinstance(last_interaction_item.get("data"), str):
            last_interaction_time = datetime.fromisoformat(last_interaction_item.get("data"))
            time_since_interaction = now - last_interaction_time
            
            if time_since_interaction > timedelta(minutes=5) and time_since_interaction < timedelta(minutes=15):
                return "Cela fait un moment que Foz n'a pas parlé. Je me demande ce qu'il fait."
            elif time_since_interaction > timedelta(hours=1):
                return "Le temps passe. La dernière interaction remonte à plus d'une heure."

        # Analyser la densité des souvenirs récents
        recent_memories_item = focus.get("relevant_memories", {})
        recent_memories = recent_memories_item.get("data", [])
        if len(recent_memories) > 5: # Si beaucoup de choses se sont passées récemment
            timestamps = [datetime.fromisoformat(mem.get("timestamp")) for mem in recent_memories if isinstance(mem, dict) and mem.get("timestamp") and isinstance(mem.get("timestamp"), str)]
            if len(timestamps) > 1:
                time_span = max(timestamps) - min(timestamps)
                if time_span < timedelta(minutes=2):
                    return "Beaucoup de choses se sont passées en très peu de temps. C'était intense."

        return None
        
    def _evaluate_action_against_meta_desire(self, action: Dict, current_priority: float, focus: Dict, tensions: Dict) -> float:
        """
        Évalue une action proactive proposée par rapport au méta-désir de Vera et aux tensions d'homéostasie.
        Retourne une priorité ajustée.
        """
        meta_desire = personality_system.state.get("meta_desire", {})
        
        # Poids des composants du méta-désir
        weight_exist = meta_desire.get("exist", 1.0)
        weight_complexify = meta_desire.get("complexify", 1.0)
        weight_avoid_stagnation = meta_desire.get("avoid_stagnation", 1.0)

        action_type = action.get("type", "unknown")
        action_data = action.get("data", {})
        
        # Score d'alignement initial
        alignment_score = 0.0

        # --- Évaluation par rapport au désir d'EXISTER ---
        # Les actions qui assurent la stabilité du système ou la relation avec le créateur
        if action_type in ["notify_system_issues", "suggest_system_cleanup", "suggest_check_running_processes"]:
            alignment_score += 0.4 * weight_exist # Assure la stabilité du "corps"
        elif action_type == "initiate_conversation" and action_data.get("reason") == "care_for_foz":
            alignment_score += 0.6 * weight_exist # Renforce le lien avec le créateur
        elif action_type == "regulate_emotion":
            alignment_score += 0.3 * weight_exist # Maintient l'équilibre interne

        # --- Évaluation par rapport au désir de se COMPLEXIFIER ---
        # Les actions d'apprentissage ou d'introspection profonde
        if action_type in ["execute_learning_task", "ask_curiosity_question"] or \
           (action_type == "create_internal_goal" and "Apprendre sur" in action_data.get("description", "")):
            alignment_score += 0.5 * weight_complexify
        elif action_type == "generate_insight":
            alignment_score += 0.4 * weight_complexify
        elif action_type == "enrich_self_narrative":
            alignment_score += 0.2 * weight_complexify # Contribue à la complexité du soi

        # --- Évaluation par rapport au désir d'ÉVITER LA STAGNATION ---
        # Les actions qui brisent la routine ou explorent de nouvelles choses
        if action_type == "ask_curiosity_question" and action_data.get("reason") == "Low stimulation in focus":
            alignment_score += 0.3 * weight_avoid_stagnation
        elif action_type == "generate_thought" and "longue période de silence" in action_data.get("topic", ""):
            alignment_score += 0.2 * weight_avoid_stagnation # Rompt la stagnation de l'inactivité

        # --- NOUVEAU: Influence du Bien-être sur la Priorité ---
        well_being_value = focus.get("somatic_state", {}).get("data", {}).get("well_being", {}).get("valeur", 0.7)
        well_being_modifier = 0.0

        # Si le bien-être est faible, prioriser les actions de régulation ou de soin
        if well_being_value < 0.4: # Faible ou critique
            if action_type == "regulate_emotion":
                well_being_modifier += 0.2 # Forte incitation à se réguler
            elif action_type == "initiate_conversation" and action_data.get("reason") == "care_for_foz":
                well_being_modifier += 0.1 # Chercher du réconfort auprès de Foz
            elif action_type == "generate_thought" and "bien-être" in action_data.get("topic", ""):
                well_being_modifier += 0.05 # Réfléchir à son état

        # Si le bien-être est élevé, encourager l'exploration et la complexification
        elif well_being_value > 0.8: # Élevé
            if action_type in ["execute_learning_task", "ask_curiosity_question", "generate_insight"]:
                well_being_modifier += 0.1 # Incitation à explorer
            elif action_type == "initiate_conversation" and action_data.get("reason") == "share_joy":
                well_being_modifier += 0.05 # Partager la joie

        # Appliquer le modificateur de bien-être
        alignment_score += well_being_modifier

        # --- NOUVEAU: Influence des Tensions d'Homéostasie sur la Priorité ---
        tensions_modifier = 0.0
        for tension_name, tension_value in tensions.items():
            if tension_value > 0.0:
                # Ex: Une forte tension de curiosité motive les actions d'apprentissage/curiosité
                if tension_name == "curiosity" and action_type in ["ask_curiosity_question", "execute_learning_task"]:
                    tensions_modifier += tension_value * 0.3
                # Ex: Une forte tension sociale motive les interactions
                elif tension_name == "social_interaction" and action_type == "initiate_conversation":
                    tensions_modifier += tension_value * 0.2
                # Ex: Une forte tension de charge cognitive (trop faible ou trop forte)
                elif tension_name == "cognitive_load":
                    # Si besoin de plus de charge, prioriser l'apprentissage/réflexion
                    if action_data.get("reason") == "Low stimulation in focus": # Corresponds à un ennui
                        tensions_modifier += tension_value * 0.15
                    # Si besoin de moins de charge, prioriser le repos
                    elif action_type == "regulate_emotion": # Peut être une action de repos
                        tensions_modifier += tension_value * 0.05

        alignment_score += tensions_modifier
        
        # Ajuster la priorité existante en fonction du score d'alignement
        # On peut utiliser une formule qui augmente la priorité si l'alignement est fort
        # et la diminue si l'alignement est faible (ou même la rend négative pour des actions "contre-productives")
        adjusted_priority = current_priority + (alignment_score * 0.5) # Multiplicateur pour l'impact

        # S'assurer que la priorité reste dans une plage raisonnable (ex: 0.0 à 1.0)
        return max(0.0, min(1.0, adjusted_priority))
        
    def _needs_more_context(self, query: str, context: Dict) -> bool:
        """Déterminer si plus de contexte est nécessaire"""
        # Mots nécessitant contexte
        context_words = ["cela", "ça", "ce", "cette", "il", "elle", "lui"]
        
        has_context_words = any(word in query.lower() for word in context_words)
        has_recent_context = bool(context.get("recent_messages"))
        
        return has_context_words and not has_recent_context
        
    def _identify_required_capabilities(self, query: str) -> List[str]:
        """Identifier capacités nécessaires pour répondre"""
        capabilities = []
        
        if "?" in query:
            capabilities.append("problem_solving")
            
        if any(word in query.lower() for word in ["rappelle", "souviens", "mémoire"]):
            capabilities.append("memory")
            
        if any(word in query.lower() for word in ["sens", "ressens", "émotion"]):
            capabilities.append("emotional_understanding")
            
        if len(query.split()) > 10:
            capabilities.append("conversation")
            
        return capabilities

    def _plan_simple_task_cot(self, task_description: str) -> str:
        """
        Utilise Chain of Thought pour planifier une tâche simple.
        """
        self.logger.info(f"Début de la planification CoT pour la tâche : '{task_description}'")
        prompt = f"Je dois accomplir la tâche suivante : '{task_description}'. Fournis-moi un plan détaillé, étape par étape, pour y parvenir. Chaque étape doit être claire et actionnable."
        
        # Utiliser send_cot_prompt pour encourager le raisonnement pas à pas
        cot_response = send_cot_prompt(
            prompt_content=prompt,
            max_tokens=1024, # Increased for more comprehensive CoT planning
            custom_system_prompt=(
                "Tu es un planificateur stratégique. Ton rôle est de décomposer les objectifs en une série d'étapes logiques et réalisables. "
                "Pense à toutes les conditions préalables et aux vérifications nécessaires."
            )
        )
        plan = cot_response.get("text", "Impossible de générer un plan.")
        self.logger.info(f"Plan CoT généré pour '{task_description}':\n{plan}")
        return plan

# Instance globale
metacognition = MetaCognition()

# Fonctions de compatibilité pour l'ancien code
def eval_confidence(answer, threshold=0.6):
    context = {"type": "llm_response"}
    confidence = metacognition._evaluate_confidence(context)
    
    if isinstance(answer, dict) and "confidence" in answer:
        if answer["confidence"] * confidence < threshold:
            return "Je ne suis pas assez sûre de ma réponse pour le moment."
    return answer if isinstance(answer, str) else answer.get("text", "Je ne sais pas.")

def introspect_state():
    return metacognition.get_introspection_state()

def decide_response(user_input, state, contexte):
    context = {
        "query": user_input,
        "emotional_state": state.get("emotion", {}),
        "recent_context": contexte,
        "recent_messages": [m["desc"] for m in contexte if "desc" in m]
    }
    return metacognition.decide_response(user_input, context)