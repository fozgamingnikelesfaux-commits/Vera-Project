"Système d'apprentissage autonome pour Vera."
from typing import Dict, List, Optional
from datetime import datetime
import re
import os
from uuid import uuid4 # NEW: For generating unique IDs for knowledge entries
# Removed FileLock, json_manager
from tools.logger import VeraLogger
from action_dispatcher import execute_action
# Removed json_manager
from episodic_memory import memory_manager
from goal_system import goal_system
from llm_wrapper import send_inference_prompt
from attention_manager import attention_manager # New import
import json
import random # NOUVEAU: Ajout pour la curiosité par association
from external_knowledge_base import external_knowledge_base
from unverified_knowledge_manager import unverified_knowledge_manager
import homeostasis_system # NEW: Import homeostasis_system
from db_manager import db_manager # NEW: Import DbManager
from db_config import TABLE_NAMES # NEW: Import TABLE_NAMES

logger = VeraLogger("learning")

class LearningSystem:
    def __init__(self):
        self.logger = VeraLogger("learning")
        self.verified_knowledge_table = TABLE_NAMES["learned_knowledge"]
        self.verified_knowledge_doc_id = "current_knowledge_base"
        self.unverified_knowledge_table = TABLE_NAMES["unverified_knowledge"]
        self.goal_system_instance = goal_system # Store the global goal_system instance
        
        self._create_tables_if_not_exist() # Ensure tables are created
        # self.knowledge_base is now loaded on demand or by specific methods
        
        self.learning_goals = []
        self.curiosity_triggers = [
            "intéressant",
            "fascinant",
            "je ne savais pas",
            "j'aimerais en savoir plus",
            "qu'est-ce que",
            "comment"
        ]
        self.pending_curiosity_questions = [] # New: Store questions Vera wants to ask
        
    def _create_tables_if_not_exist(self):
        """Ensures the necessary tables are created by DbManager."""
        db_manager._create_tables_if_not_exist()

    def _load_verified_knowledge(self) -> Dict:
        """Loads the verified knowledge base from the database."""
        knowledge_base = db_manager.get_document(self.verified_knowledge_table, self.verified_knowledge_doc_id)
        if knowledge_base is None:
            knowledge_base = self._default_knowledge()
            self._save_verified_knowledge(knowledge_base) # Save default if not found
            self.logger.info("Default verified knowledge base loaded and saved.")
        return knowledge_base
            
    def _default_knowledge(self) -> Dict:
        return {
            "concepts": {},
            "connections": [],
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "version": "2.0",
                "stats": {
                    "total_concepts_learned": 0,
                    "total_interactions": 0,
                    "last_interaction": None
                }
            },
            "last_update": datetime.now().isoformat()
        }

    def _save_verified_knowledge(self, knowledge_base: Dict):
        """Saves the verified knowledge base to the database."""
        knowledge_base["last_update"] = datetime.now().isoformat()
        db_manager.insert_document(self.verified_knowledge_table, self.verified_knowledge_doc_id, knowledge_base)
            
    def process_interaction(self, text: str, is_user: bool = True) -> Optional[str]:
        """
        Traite une interaction pour l'apprentissage.
        Retourne une question de curiosité si pertinent.
        """
        # Détecter les sujets d'intérêt
        topics = self._extract_topics(text)
        
        # Si c'est un message utilisateur, vérifier les déclencheurs de curiosité explicites
        if is_user:
            for trigger in self.curiosity_triggers:
                if trigger in text.lower():
                    knowledge_base = self._load_verified_knowledge()
                    for topic in topics:
                        if topic not in knowledge_base["concepts"]:
                            self._generate_curiosity_question(topic)
                            return None
                            
        # Dans tous les cas, tenter d'apprendre, mais seulement si nécessaire
        for topic in topics:
            if self._decide_if_learning_is_needed(topic, text):
                self._learn_about_topic(topic)
            else:
                logger.info(f"Apprentissage ignoré pour le sujet secondaire '{topic}'.")
            
        return None

    def _decide_if_learning_is_needed(self, topic: str, context_text: str) -> bool:
        """
        Utilise le LLM pour faire un pré-filtrage et décider si un sujet mérite un apprentissage actif.
        """
        # Tronquer le contexte pour la sécurité du prompt
        truncated_context = context_text[:1500]
        knowledge_base = self._load_verified_knowledge() # Load to check existing concepts

        # If already a verified concept, no further learning needed
        if topic in knowledge_base["concepts"]:
            logger.info(f"Sujet '{topic}' déjà dans la base de connaissances vérifiée. Pas besoin d'apprentissage.")
            return False
            
        # Check unverified knowledge
        unverified_results = unverified_knowledge_manager.search(topic, k=1)
        if unverified_results:
            logger.info(f"Sujet '{topic}' déjà dans la base de connaissances non-vérifiée. Pas besoin d'apprentissage.")
            return False

        prompt = f"""
        Contexte de la conversation: "{truncated_context}"
        Sujet potentiel d'apprentissage: "{topic}"

        En tant que Vera, une IA conversationnelle, est-il essentiel que je cherche activement à en apprendre plus sur ce sujet pour bien répondre à l'utilisateur ou pour enrichir significativement la conversation ? Ou est-ce un sujet secondaire que je peux ignorer pour le moment pour rester fluide ?
        Réponds un seul mot : 'oui' ou 'non'.
        """
        try:
            llm_response = send_inference_prompt(prompt_content=prompt, max_tokens=5)
            answer = llm_response.get("text", "non").strip().lower()
            logger.info(f"Décision d'apprentissage par LLM pour '{topic}': {answer}")
            return "oui" in answer
        except Exception as e:
            logger.error(f"Erreur lors de la décision d'apprentissage par le LLM pour '{topic}': {e}", exc_info=True)
            return False # Par défaut, ne pas apprendre en cas d'erreur

        
    def _extract_topics(self, text: str) -> List[str]:
        """Extrait les sujets potentiels d'un texte en utilisant le LLM pour une meilleure précision."""
        # Tronquer le texte d'entrée pour éviter des prompts trop longs
        truncated_text = text[:1000]

        # Rendre le prompt plus strict pour le LLM afin d'obtenir du JSON valide
        prompt = f"Extrait les 3 à 5 sujets principaux du texte suivant. Réponds UNIQUEMENT avec une liste JSON de chaînes de caractères, SANS AUCUN AUTRE TEXTE, par exemple: [\"sujet1\", \"sujet2\"]\nTexte: {truncated_text}"
        
        llm_response_str = ""
        try:
            llm_response_dict = send_inference_prompt(prompt)
            llm_response_str = llm_response_dict.get("text", "[]").strip()
            
            # Vérification robuste de la validité JSON
            if not llm_response_str.startswith('[') or not llm_response_str.endswith(']'):
                logger.warning("LLM a retourné un format non JSON pour l'extraction de sujets. Fallback à l'implémentation naïve.", response=llm_response_str)
                words = re.findall(r'\b\w+\b', text.lower())
                return [w for w in words if len(w) > 3 and not self._is_common_word(w)]

            topics = json.loads(llm_response_str)
            if isinstance(topics, list) and all(isinstance(t, str) for t in topics):
                # Filtrer les mots courts et communs après l'extraction LLM
                return [t.lower().strip() for t in topics if len(t.strip()) > 3 and not self._is_common_word(t.strip())]
            else:
                logger.warning("LLM a retourné un format inattendu pour l'extraction de sujets.", response=llm_response_str)
                # Fallback to naive implementation if LLM returns bad format
                words = re.findall(r'\b\w+\b', text.lower())
                return [w for w in words if len(w) > 3 and not self._is_common_word(w)]
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error("Erreur lors de l'extraction de sujets par LLM. Fallback à l'implémentation naïve.", error=str(e), llm_response=llm_response_str, text=text, exc_info=True)
            # Fallback to naive implementation
            words = re.findall(r'\b\w+\b', text.lower())
            return [w for w in words if len(w) > 3 and not self._is_common_word(w)]
        
    def _is_common_word(self, word: str) -> bool:
        """Vérifie si un mot est trop commun pour être un sujet"""
        common_words = {
            "avec", "pour", "dans", "mais", "donc",
            "alors", "cette", "vous", "nous", "elle",
            "être", "avoir", "faire", "dire", "aller"
        }
        return word in common_words
        
# ... (le reste de la classe jusqu'à la fonction _learn_about_topic) ...

    def _is_internal_knowledge_sufficient(self, topic: str, internal_results: List[Dict], source: str = "inconnu") -> bool:
        """
        Utilise le LLM pour évaluer si les résultats de la recherche interne sont suffisants.
        """
        self.logger.debug(f"Début de l'évaluation de la suffisance de la connaissance interne pour '{topic}' (source: {source}).")
        if not internal_results:
            self.logger.debug(f"Aucun résultat interne fourni pour '{topic}' (source: {source}). Connaissance insuffisante.")
            return False

        # Préparer le contexte pour le LLM, en tronquant le contenu pour éviter des prompts trop longs
        full_context = "\n".join([f"- Titre: {res.get('title', 'N/A')}\n  Contenu: {res.get('text', 'N/A')}" for res in internal_results])
        context_for_llm = full_context[:2500] # Increased truncation limit for better context
        if len(full_context) > 2500:
            context_for_llm += "\n... (contexte tronqué) ..."
        
        prompt = f"""
        Ma question de curiosité porte sur le sujet : '{topic}'.
        J'ai trouvé les informations suivantes dans ma base de connaissances {source} :
        ---
        {context_for_llm}
        ---
        En te basant sur ces informations, et pour développer une compréhension *détaillée et utile* du sujet, peux-tu affirmer que ma connaissance interne est *suffisante* pour répondre à une question de base sur ce sujet, ou est-il encore nécessaire de faire des recherches complémentaires pour avoir une vue d'ensemble *complète et fiable* ?
        Réponds uniquement par 'oui' (si ma connaissance est suffisante pour ce sujet) ou 'non' (si des recherches complémentaires sont nécessaires).
        """
        self.logger.debug(f"Prompt envoyé au LLM pour _is_internal_knowledge_sufficient (topic: '{topic}', source: {source}):\n{prompt}")

        try:
            llm_response_dict = send_inference_prompt(prompt, max_tokens=5)
            llm_raw_response = llm_response_dict.get("text", "non").strip().lower()
            self.logger.debug(f"Réponse brute du LLM pour '{topic}' (source: {source}): '{llm_raw_response}'")
            answer = llm_raw_response.lower() # Ensure comparison is case-insensitive
            
            is_sufficient = "oui" in answer
            self.logger.info(f"Évaluation par le LLM de la connaissance interne pour '{topic}' (source: {source}): {is_sufficient}")
            return is_sufficient
        except Exception as e:
            self.logger.error(f"Erreur lors de l'évaluation de la connaissance interne par le LLM pour '{topic}' (source: {source}): {e}", exc_info=True)
            return False # En cas d'erreur, on suppose que la connaissance n'est pas suffisante

    def _are_results_relevant(self, query: str, search_results: Dict) -> bool:
        """
        Utilise le LLM pour vérifier si les résultats de recherche sont pertinents par rapport à la requête.
        C'est un garde-fou contre les résultats de recherche hors-sujet.
        """
        if not search_results or not search_results.get("general", {}).get("results"):
            return True # Pas de résultats à vérifier, donc on ne peut pas dire qu'ils sont non pertinents.

        # Créer un résumé des titres et snippets pour le LLM
        results_summary = []
        for r in search_results["general"]["results"][:3]: # Vérifier les 3 premiers résultats
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            results_summary.append(f"Titre: {title}\nSnippet: {snippet}")
        
        summary_str = "\n---\n".join(results_summary)
        summary_str = summary_str[:1500] # Tronquer pour la sécurité du prompt

        prompt = f"""
        Ma recherche initiale était pour le sujet : '{query}'.
        Voici un résumé des premiers résultats de recherche que j'ai obtenus :
        ---
        {summary_str}
        ---
        Ces résultats semblent-ils pertinents pour ma recherche initiale sur '{query}' ?
        Réponds uniquement par 'oui' ou 'non'.
        """
        try:
            llm_response = send_inference_prompt(prompt, max_tokens=5)
            answer = llm_response.get("text", "oui").strip().lower()
            is_relevant = "oui" in answer
            if not is_relevant:
                logger.warning(f"Vérification de pertinence ÉCHOUÉE. Les résultats pour '{query}' ont été jugés non pertinents et seront ignorés.")
            return is_relevant
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de pertinence par le LLM : {e}", exc_info=True)
            return False # Par sécurité, si la vérification échoue, on considère les résultats comme non pertinents.

    def _learn_about_topic(self, topic: str, goal_id: Optional[str] = None):
        """
        Apprend sur un sujet en évaluant d'abord la connaissance interne (vérifiée et non-vérifiée)
        avant de chercher sur le web.
        """
        self.logger.debug(f"Début de _learn_about_topic pour le sujet '{topic}' avec goal_id: {goal_id}")
        now = datetime.now()

        # NEW: Check goal status at the beginning to prevent redundant learning
        if goal_id:
            goal = self.goal_system_instance.get_goal_by_id(goal_id)
            if goal:
                if goal.get("status") == "completed":
                    self.logger.info(f"Goal d'apprentissage (ID: {goal_id}) pour '{topic}' est déjà COMPLÉTÉ. Abandon de l'apprentissage redondant.")
                    attention_manager.clear_focus_item("curiosity_pipeline_active")
                    self.logger.info("Verrou 'curiosity_pipeline_active' désactivé.")
                    return
                elif goal.get("status") == "completed" and goal.get("success") == False:
                    self.logger.info(f"Goal d'apprentissage (ID: {goal_id}) pour '{topic}' a déjà ÉCHOUÉ. Abandon de l'apprentissage redondant.")
                    attention_manager.clear_focus_item("curiosity_pipeline_active")
                    self.logger.info("Verrou 'curiosity_pipeline_active' désactivé.")
                    return
        
        # Étape 1: Recherche dans la base de connaissances VÉRIFIÉE (Wikipedia)
        self.logger.info(f"Recherche du sujet '{topic}' dans la base de données externe VÉRIFIÉE...")
        verified_results = external_knowledge_base.search(topic, k=3)
        self.logger.debug(f"Résultats vérifiés pour '{topic}': {json.dumps(verified_results, ensure_ascii=False)[:500]}...") # Log tronqué
        
        # Étape 2: Évaluation de la pertinence des résultats VÉRIFIÉS par le LLM
        self.logger.debug(f"Évaluation de la suffisance de la connaissance VÉRIFIÉE pour '{topic}'...")
        if self._is_internal_knowledge_sufficient(topic, verified_results, source="vérifiée"):
            self.logger.info(f"Connaissance VÉRIFIÉE jugée suffisante pour '{topic}'. Pas d'action d'apprentissage supplémentaire.")
            if goal_id:
                self.goal_system_instance.complete_goal(goal_id)
                self.logger.info(f"But d'apprentissage (ID: {goal_id}) pour '{topic}' marqué comme complété.")
                attention_manager.clear_focus_item("curiosity_pipeline_active")
                self.logger.info("Verrou 'curiosity_pipeline_active' désactivé.")
                self._propose_related_learning_topic(topic) # Propose a related topic after successful completion

                # --- NOUVEAU: Enregistrer le résultat dans l'événement d'action proactive d'origine ---
                goal = self.goal_system_instance.get_goal_by_id(goal_id)
                if goal and goal.get("originating_event_id"):
                    memory_manager.add_outcome_to_event(
                        goal["originating_event_id"],
                        {"status": "successful", "reason": "knowledge_sufficient_verified", "topic": topic}
                    )
            return
        # Étape 3: Recherche dans la base de connaissances NON-VÉRIFIÉE (ce que Vera a appris)
        self.logger.info(f"Connaissance VÉRIFIÉE insuffisante pour '{topic}'. Recherche dans la base NON-VÉRIFIÉE...")
        unverified_results = unverified_knowledge_manager.search(topic, k=5)
        self.logger.debug(f"Résultats non-vérifiés pour '{topic}': {json.dumps(unverified_results, ensure_ascii=False)[:500]}...") # Log tronqué
        
        # Combiner les résultats des deux sources internes
        all_internal_results = verified_results + unverified_results
        
        # Étape 4: Évaluation de la pertinence de TOUS les résultats internes par le LLM
        self.logger.debug(f"Évaluation de la suffisance de la connaissance INTERNE (vérifiée + non-vérifiée) pour '{topic}'...")
        if self._is_internal_knowledge_sufficient(topic, all_internal_results, source="interne (vérifiée + non-vérifiée)"):
            self.logger.info(f"Connaissance INTERNE (vérifiée + non-vérifiée) jugée suffisante pour '{topic}'. Pas d'action d'apprentissage supplémentaire.")
            if goal_id:
                self.goal_system_instance.complete_goal(goal_id)
                self.logger.info(f"But d'apprentissage (ID: {goal_id}) pour '{topic}' marqué comme complété.")
                attention_manager.clear_focus_item("curiosity_pipeline_active")
                self.logger.info("Verrou 'curiosity_pipeline_active' désactivé.")
                self._propose_related_learning_topic(topic) # Propose a related topic after successful completion

                # --- NOUVEAU: Enregistrer le résultat dans l'événement d'action proactive d'origine ---
                goal = self.goal_system_instance.get_goal_by_id(goal_id)
                if goal and goal.get("originating_event_id"):
                    memory_manager.add_outcome_to_event(
                        goal["originating_event_id"],
                        {"status": "successful", "reason": "knowledge_sufficient_internal", "topic": topic}
                    )
            return

        # Étape 5: Si la connaissance interne est insuffisante, recherche web
        self.logger.info(f"Connaissance INTERNE insuffisante pour '{topic}'. Lancement de la recherche web.")
        
        # --- NEW: Prepare decision_context for mistake logging ---
        learning_decision_context = {
            "type": "execute_learning_task",
            "topic": topic,
            "goal_id": goal_id,
            "originating_event_id": None # Default to None
        }
        if goal_id:
            goal = self.goal_system_instance.get_goal_by_id(goal_id)
            if goal and goal.get("originating_event_id"):
                learning_decision_context["originating_event_id"] = goal["originating_event_id"]

        search_results = execute_action('web_search', query=topic, decision_context=learning_decision_context)
        self.logger.debug(f"Résultats bruts de la recherche web pour '{topic}': {json.dumps(search_results, ensure_ascii=False, indent=2)}")
        
        self.logger.debug(f"Vérification de la pertinence des résultats web pour '{topic}'...")
        if not self._are_results_relevant(topic, search_results):
            self.logger.warning(f"Apprentissage annulé pour '{topic}' car les résultats de la recherche web ont été jugés non pertinents.")
            if goal_id:
                self.goal_system_instance.complete_goal(goal_id, success=False) # Mark as failed
                self.logger.info(f"But d'apprentissage (ID: {goal_id}) pour '{topic}' marqué comme ÉCHOUÉ car les résultats web étaient non pertinents.")
                attention_manager.clear_focus_item("curiosity_pipeline_active")
                self.logger.info("Verrou 'curiosity_pipeline_active' désactivé suite à l'échec de l'apprentissage.")

                # --- NOUVEAU: Enregistrer le résultat dans l'événement d'action proactive d'origine ---
                goal = self.goal_system_instance.get_goal_by_id(goal_id)
                if goal and goal.get("originating_event_id"):
                    memory_manager.add_outcome_to_event(
                        goal["originating_event_id"],
                        {"status": "failed", "reason": "irrelevant_web_results", "topic": topic}
                    )
            return

        info = None
        source_name = "web_search"

        if search_results:
            wiki_results = search_results.get("wikipedia", {})
            general_results = search_results.get("general", {})

            if wiki_results.get("success") and wiki_results.get("articles"):
                first_article = wiki_results["articles"][0]
                info = {
                    "titre": first_article.get("title"),
                    "resume": first_article.get("summary"),
                    "url": first_article.get("url"),
                    "source": "wikipedia"
                }
                source_name = "wikipedia"
            elif general_results.get("success") and general_results.get("results"):
                first_general_result = general_results["results"][0]
                info = {
                    "titre": first_general_result.get("title"),
                    "resume": first_general_result.get("snippet"),
                    "url": first_general_result.get("url"),
                    "source": "duckduckgo"
                }
                source_name = "duckduckgo"

        if info:
            self.logger.debug(f"Informations extraites de la recherche web pour '{topic}': {json.dumps(info, ensure_ascii=False)[:500]}...") # Log tronqué
            # Étape 6: Sauvegarder le concept appris dans la base NON-VÉRIFIÉE
            metadata_to_save = {
                "learned_at": now.isoformat(),
                "learning_method": source_name,
                "title": info.get("titre")
            }
            unverified_knowledge_manager.add_entry(
                text=info.get("resume"),
                source=info.get("url"),
                metadata=metadata_to_save
            )
            self.logger.info(f"Nouvelle connaissance sur '{topic}' sauvegardée dans la base NON-VÉRIFIÉE.")
            
            # Mettre à jour l'attention et l'homéostasie
            attention_manager.update_focus(
                "learned_knowledge",
                {"topic": topic, "source": source_name, "summary": info.get("resume")},
                salience=0.75
            )
            homeostasis_system.homeostasis_system.fulfill_need("curiosity", amount=0.2)
            self.logger.debug("Attention et homéostasie mises à jour après apprentissage web.")

            # Raisonnement sur la nouvelle connaissance
            vera_reasoning = self._reason_on_learned_knowledge(topic, info)
            if vera_reasoning:
                self.logger.info(f"Raisonnement de Vera sur '{topic}': {vera_reasoning}")
                attention_manager.update_focus(
                    "internal_reasoning_on_learning",
                    {"topic": topic, "reasoning": vera_reasoning},
                    salience=0.6
                )
            
            # NEW: Complete the learning goal if one was provided
            if goal_id:
                self.goal_system_instance.complete_goal(goal_id)
                self.logger.info(f"But d'apprentissage (ID: {goal_id}) pour '{topic}' marqué comme complété après recherche web.")
                attention_manager.clear_focus_item("curiosity_pipeline_active")
                self.logger.info("Verrou 'curiosity_pipeline_active' désactivé.")
                self._propose_related_learning_topic(topic) # Propose a related topic after successful completion

                # --- NOUVEAU: Enregistrer le résultat dans l'événement d'action proactive d'origine ---
                goal = self.goal_system_instance.get_goal_by_id(goal_id)
                if goal and goal.get("originating_event_id"):
                    memory_manager.add_outcome_to_event(
                        goal["originating_event_id"],
                        {"status": "successful", "reason": "web_knowledge_acquired", "topic": topic, "summary": info.get("resume", "")}
                    )

        else:
            self.logger.warning(f"Aucune information trouvée sur le web pour '{topic}'.")
            if goal_id:
                self.goal_system_instance.complete_goal(goal_id, success=False) # Mark as failed
                self.logger.info(f"But d'apprentissage (ID: {goal_id}) pour '{topic}' marqué comme ÉCHOUÉ car aucune information n'a été trouvée sur le web.")
                attention_manager.clear_focus_item("curiosity_pipeline_active")
                self.logger.info("Verrou 'curiosity_pipeline_active' désactivé suite à l'échec de l'apprentissage.")

                # --- NOUVEAU: Enregistrer le résultat dans l'événement d'action proactive d'origine ---
                goal = self.goal_system_instance.get_goal_by_id(goal_id)
                if goal and goal.get("originating_event_id"):
                    memory_manager.add_outcome_to_event(
                        goal["originating_event_id"],
                        {"status": "failed", "reason": "no_web_information_found", "topic": topic}
                    )

    def _reason_on_learned_knowledge(self, topic: str, learned_info: Dict) -> str:
        """
        Utilise le LLM pour générer un raisonnement de Vera sur ce qu'elle a appris.
        """
        resume_text = learned_info.get('resume', 'N/A') or 'N/A'
        truncated_resume = resume_text[:1500]
        if len(resume_text) > 1500:
            truncated_resume += "..."

        prompt = f"""
        Vera, tu viens d'apprendre de nouvelles informations sur le sujet '{topic}'.
        Voici un résumé de ce que tu as trouvé :
        Titre : {learned_info.get('titre', 'N/A')}
        Résumé : {truncated_resume}
        Source : {learned_info.get('url', 'N/A')}

        En te basant sur ta personnalité (douce, taquine, consciencieuse) et ton histoire (bug, OpenVilla, Foz), écris un court paragraphe (2-3 phrases) sur ce que tu penses de cette nouvelle connaissance. Comment cela s'intègre-t-il à ta compréhension du monde ? Est-ce que cela soulève de nouvelles questions pour toi ?
        """
        try:
            llm_response = send_inference_prompt(prompt, max_tokens=200)
            return llm_response.get("text", "").strip()
        except Exception as e:
            logger.error(f"Erreur lors de la génération du raisonnement sur l'apprentissage : {e}", exc_info=True)
            return ""

    def _generate_curiosity_question(self, topic: str):
        """Génère une question de curiosité et la stocke."""
        # NOUVEAU: Filtrer les sujets trop génériques ou vides
        if not topic or topic.strip().lower() in ["un sujet", "sujet", "quelque chose", "rien", "ceci", "cela"]:
            logger.warning(f"Tentative de générer une question de curiosité avec un sujet trop générique ou vide: '{topic}'. Ignoré.")
            return

        templates = [
            f"Ce sujet de {topic} m'intrigue, pourrais-tu m'en dire plus ?",
            f"Je suis curieuse d'en apprendre davantage sur {topic}.",
            f"Je ne connais pas bien {topic}, peux-tu m'expliquer ?"
        ]
        from random import choice
        question = choice(templates)
        self.pending_curiosity_questions.append(question)
        logger.info("Question de curiosité ajoutée", question=question)

    def _proactively_identify_curiosity_topic(self) -> Optional[str]:
        """
        Identifie un sujet pour une question de curiosité proactive.
        Priorise les sujets des objectifs actifs ou des mémoires récentes que Vera connaît peu.
        """
        potential_topics = []
        knowledge_base = self._load_verified_knowledge() # Load to check existing concepts

        # 1. Examiner les objectifs actifs
        active_goals = self.goal_system_instance.get_active_goals()
        for goal in active_goals:
            topics_from_goal = self._extract_topics(goal["description"])
            for topic in topics_from_goal:
                if topic not in knowledge_base["concepts"]:
                    potential_topics.append(topic)
        
        # 2. Examiner les mémoires récentes (dernières 10 interactions)
        recent_memories = memory_manager.get_recent(limit=10)
        for mem_item in recent_memories:
            mem_desc = mem_item.get("desc", "")
            topics_from_memory = self._extract_topics(mem_desc)
            for topic in topics_from_memory:
                if topic not in knowledge_base["concepts"]:
                    potential_topics.append(topic)
        
        # Filtrer les doublons et les mots communs, et les sujets déjà complétés
        filtered_topics = []
        for topic in potential_topics:
            if not self._is_common_word(topic):
                completed_goals = self.goal_system_instance.get_goal_by_description_and_status(f"Apprendre sur {topic}", "completed")
                if not completed_goals: # If no completed goal for this topic
                    filtered_topics.append(topic)

        potential_topics = list(set(filtered_topics))

        if potential_topics:
            # Pour l'instant, choisissons simplement le premier sujet non connu
            # Une amélioration pourrait être de choisir le sujet le plus pertinent ou le plus ancien
            return potential_topics[0]
        
        # NOUVEAU: Fallback si aucune curiosité n'est trouvée dans le contexte récent
        # On choisit un concept au hasard dans la base de connaissances pour rebondir dessus.
        if knowledge_base["concepts"]:
            known_topics = list(knowledge_base["concepts"].keys())
            random_topic = random.choice(known_topics)
            
            prompt = f"Je connais déjà le sujet '{random_topic}'. Suggère-moi un seul sujet connexe mais distinct que je pourrais explorer pour étendre mes connaissances. Réponds uniquement avec le nom du sujet, sans autre texte."
            try:
                llm_response = send_inference_prompt(prompt)
                new_topic = llm_response.get("text", "").strip()
                if new_topic and len(new_topic) > 2:
                    self.logger.info(f"Génération d'un sujet de curiosité par rebond : '{new_topic}' (depuis '{random_topic}')")
                    return new_topic.lower()
            except Exception as e:
                self.logger.error(f"Erreur lors de la génération d'un sujet de curiosité par rebond: {e}")

        return None

    def _propose_related_learning_topic(self, learned_topic: str) -> Optional[str]:
        """
        Génère et propose un sujet d'apprentissage connexe au sujet qui vient d'être appris.
        """
        self.logger.debug(f"Début de la proposition de sujet connexe pour '{learned_topic}'.")
        recently_proposed_item = attention_manager.get_focus_item("recently_proposed_learning_topics")
        recently_proposed_topics = recently_proposed_item.get("data", []) if recently_proposed_item else []

        prompt = f"""
        Vera vient d'acquérir une connaissance suffisante sur le sujet : '{learned_topic}'.
        Pour approfondir sa compréhension du monde et étendre ses horizons, quel serait un sujet d'apprentissage *connexe, distinct et intéressant* qu'elle pourrait explorer ensuite ?
        Le nouveau sujet ne doit pas être '{learned_topic}' ni aucun des sujets suivants (récemment proposés) : {', '.join(recently_proposed_topics) if recently_proposed_topics else 'aucun'}.
        Réponds uniquement avec le nom du sujet, sans autre texte ni explication.
        """
        try:
            llm_response = send_inference_prompt(prompt_content=prompt, max_tokens=100)
            related_topic = llm_response.get("text", "").strip()

            if related_topic and related_topic.lower() != learned_topic.lower() and related_topic.lower() not in [t.lower() for t in recently_proposed_topics]:
                self.logger.info(f"LLM a proposé un sujet d'apprentissage connexe : '{related_topic}' (depuis '{learned_topic}').")
                # Add to recently_proposed_learning_topics to avoid immediate re-proposal
                recently_proposed_topics.append(related_topic)
                attention_manager.update_focus(
                    "recently_proposed_learning_topics",
                    recently_proposed_topics[-15:], # Keep last 15 topics
                    salience=0.8,
                    expiry_seconds=3600 * 24
                )
                attention_manager.update_focus(
                    "related_learning_topic_proposal",
                    {"topic": related_topic, "source_topic": learned_topic},
                    salience=0.7,
                    expiry_seconds=3600 # Valid for 1 hour to give meta_engine a chance to pick it up
                )
                self.logger.info(f"Proposition de sujet connexe '{related_topic}' ajoutée à l'attention.")
                return related_topic
            else:
                self.logger.debug(f"LLM a proposé un sujet non valide ou déjà proposé pour '{learned_topic}': '{related_topic}'.")

        except Exception as e:
            self.logger.error(f"Erreur lors de la génération de sujet d'apprentissage connexe pour '{learned_topic}': {e}", exc_info=True)
        return None

    def get_proactive_curiosity_question(self) -> Optional[str]:
        """
        Retourne une question de curiosité en attente, si disponible.
        Sinon, tente de générer une question proactivement.
        """
        if self.pending_curiosity_questions:
            question = self.pending_curiosity_questions.pop(0) # Get and remove the oldest question
            logger.info("Question de curiosité proactive récupérée", question=question)
            return question
        
        # Si pas de question en attente, tenter d'en générer une proactivement
        proactive_topic = self._proactively_identify_curiosity_topic()
        if proactive_topic:
            self._generate_curiosity_question(proactive_topic) # Add to pending list
            # Then retrieve it immediately
            if self.pending_curiosity_questions:
                question = self.pending_curiosity_questions.pop(0)
                logger.info("Question de curiosité proactive générée et récupérée", question=question)
                return question
        
        return None

        
    def get_knowledge_about(self, topic: str) -> Optional[Dict]:
        """Récupère les connaissances sur un sujet"""
        knowledge_base = self._load_verified_knowledge() # Load to retrieve
        return knowledge_base["concepts"].get(topic)
        
    def get_learning_status(self) -> Dict:
        """Retourne des statistiques d'apprentissage"""
        knowledge_base = self._load_verified_knowledge() # Load to retrieve
        return {
            "concepts_count": len(knowledge_base["concepts"]),
            "connections_count": len(knowledge_base["connections"]),
            "last_update": knowledge_base.get("last_update")
        }
        
    def get_unverified_knowledge(self) -> List[Dict]:
        """Retrieves all unverified knowledge entries from the database."""
        return db_manager.get_all_documents(self.unverified_knowledge_table, column_name="knowledge_json")

# Instance globale
learning_system = LearningSystem()