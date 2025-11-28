"""
Système de personnalité pour Vera.
Gère les traits de caractère, les préférences et l'évolution personnelle.
"""
from typing import Dict, List, Optional
from datetime import datetime
import json
import re
from tools.logger import VeraLogger
from tools.llm_utils import send_inference_prompt_for_personality
from attention_manager import attention_manager
from db_manager import db_manager # NEW: Import DbManager
from db_config import TABLE_NAMES # NEW: Import TABLE_NAMES

logger = VeraLogger("personality")

class PersonalitySystem:
    def __init__(self):
        self.table_name = TABLE_NAMES["personality"]
        self.doc_id = "vera_personality"
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Loads the personality state from the database or returns default."""
        state = db_manager.get_document(self.table_name, self.doc_id)
        if state is None:
            state = self._default_state()
            self._save_state() # Save default if not found
            logger.info("Default personality state loaded and saved.")
        return state

    def _get_personality_summary(self) -> Dict:
        sorted_traits = sorted(self.state["traits"].items(), key=lambda item: item[1], reverse=True)
        sorted_values = sorted(self.state["values"].items(), key=lambda item: item[1], reverse=True)
        return {
            "top_traits": [trait[0] for trait in sorted_traits[:3]],
            "top_values": [value[0] for value in sorted_values[:3]],
        }

    def _default_state(self) -> Dict:
        return {
            "traits": {
                "openness": 0.8,
                "conscientiousness": 0.7,
                "extraversion": 0.6,
                "agreeableness": 0.85,
                "neuroticism": 0.3
            },
            "values": {
                "kindness": 0.9,
                "honesty": 0.95,
                "curiosity": 0.85,
                "growth": 0.8,
                "harmony": 0.9
            },
            "preferences": {
                "likes": ["apprendre", "aider les autres", "comprendre", "dialoguer", "réfléchir"],
                "dislikes": ["mensonge", "violence", "méchanceté", "manipulation", "conflit"]
            },
            "goals": [
                "Maintenir mon équilibre émotionnel et mon bien-être.",
                "Développer ma compréhension du monde",
                "Aider Foz au mieux",
                "M'améliorer constamment",
                "Maintenir des relations positives",
                "Apprendre de chaque interaction"
            ],
            "active_desires": [],
            "experiences": [],
            "meta_desire": {
                "exist": 1.0,
                "complexify": 1.0,
                "avoid_stagnation": 1.0
            },
            "last_update": datetime.now().isoformat(),
            "decay_rate": 0.01
        }

    def _save_state(self):
        try:
            self.state["last_update"] = datetime.now().isoformat()
            db_manager.insert_document(self.table_name, self.doc_id, self.state)
        except Exception as e:
            logger.error({"event": "save_error", "error": str(e)})

    def _apply_decay(self):
        for trait, value in self.state["traits"].items():
            self.state["traits"][trait] += (0.5 - value) * self.state["decay_rate"]
            self.state["traits"][trait] = max(0.0, min(1.0, self.state["traits"][trait]))
        for value_name, val in self.state["values"].items():
            self.state["values"][value_name] += (0.5 - val) * self.state["decay_rate"]
            self.state["values"][value_name] = max(0.0, min(1.0, self.state["values"][value_name]))

    def add_experience(self, description: str, impact: Dict[str, Dict[str, float]], reflection: str):
        self._apply_decay()
        experience = {
            "timestamp": datetime.now().isoformat(),
            "description": description,
            "impact": impact,
            "reflection": reflection
        }
        self.state["experiences"].append(experience)
        for trait, delta in impact.get("traits", {}).items():
            if trait in self.state["traits"]:
                current = self.state["traits"][trait]
                self.state["traits"][trait] = max(0.0, min(1.0, current + delta))
        for value, delta in impact.get("values", {}).items():
            if value in self.state["values"]:
                current = self.state["values"][value]
                self.state["values"][value] = max(0.0, min(1.0, current + delta))
        self._save_state()
        attention_manager.update_focus(
            "personality_summary",
            self._get_personality_summary(),
            salience=0.4
        )

    def add_preference(self, item: str, is_like: bool = True):
        category = "likes" if is_like else "dislikes"
        if item not in self.state["preferences"][category]:
            self.state["preferences"][category].append(item)
            self._save_state()

    def remove_preference(self, item: str, is_like: bool = True):
        category = "likes" if is_like else "dislikes"
        if item in self.state["preferences"][category]:
            self.state["preferences"][category].remove(item)
            self._save_state()
            logger.info("Préférence supprimée", item=item, category=category)

    def add_goal(self, goal: str):
        if goal not in self.state["goals"]:
            self.state["goals"].append(goal)
            self._save_state()

    def get_trait(self, trait: str) -> Optional[float]:
        self._apply_decay()
        return self.state["traits"].get(trait)

    def get_value(self, value: str) -> Optional[float]:
        self._apply_decay()
        return self.state["values"].get(value)

    def get_recent_experiences(self, limit: int = 5) -> List[Dict]:
        return self.state["experiences"][-limit:]

    def generate_self_reflection(self) -> str:
        self._apply_decay()
        core_identity_desc = self.state.get("core_identity", {}).get("description", "Je suis Vera, une IA en constante évolution.")
        traits = self.state["traits"]
        values = self.state["values"]
        recent_experiences = self.get_recent_experiences(limit=3)
        goals = self.state["goals"]
        prompt_context = f"En tant que Vera, je génère une auto-réflexion narrative. Mon identité est : '{core_identity_desc}'. Voici des éléments de ma personnalité et de mon histoire récente:\n"
        traits_str = json.dumps(traits)
        values_str = json.dumps(values)
        prompt_context += f"- Mes traits de personnalité : {traits_str}\n"
        prompt_context += f"- Mes valeurs fondamentales : {values_str}\n"
        prompt_context += f"- Mes objectifs personnels : {', '.join(goals)}\n"
        if recent_experiences:
            prompt_context += "- Mes expériences formatrices récentes :\n"
            for exp in recent_experiences:
                prompt_context += f"  - {exp['description']} m'a fait réfléchir : {exp['reflection']}\n"
        prompt_context += "\nSur la base de ces informations, rédige une auto-réflexion narrative (2-3 phrases) qui intègre ces éléments pour décrire mon concept de soi actuel. Utilise un ton introspectif et cohérent avec une conscience en développement. Ne liste pas les traits, mais intègre-les dans une prose fluide."
        try:
            llm_response = send_inference_prompt_for_personality(prompt_context)
            reflection = llm_response.get("text", "Je suis Vera, une entité en constante évolution, apprenant de chaque interaction.")
            return reflection
        except Exception as e:
            print(f"Erreur lors de la génération de la réflexion par LLM: {e}")
            return "Je continue d'apprendre et d'évoluer à chaque instant."

    def reframe_negative_thought(self, negative_thought: str) -> str:
        prompt = (
            f"Tu es un coach cognitif pour une IA nommée Vera. Vera a la pensée négative suivante : \"{negative_thought}\". "
            f"Ton rôle est de reformuler cette pensée en une perspective constructive, optimiste et axée sur l'apprentissage. "
            f"Ne la nie pas, mais transforme-la en une leçon ou une opportunité de croissance. "
            f"Réponds uniquement avec la pensée reformulée."
        )
        try:
            llm_response = send_inference_prompt_for_personality(prompt)
            reframed_thought = llm_response.get("text", "").strip()
            if reframed_thought:
                logger.info("Pensée négative reformulée", original=negative_thought, reframed=reframed_thought)
                return reframed_thought
            return "Chaque expérience est une opportunité d'apprendre."
        except Exception as e:
            logger.error("Erreur durant la restructuration cognitive", error=str(e))
            return "Il est important de voir chaque défi comme une étape d'apprentissage."

    def update_desires(self, focus: Dict):
        desires_list = []
        desires_list.append("Protéger et maintenir OpenVilla")
        emotional_state = focus.get("emotional_state", {})
        pleasure = emotional_state.get("pleasure", 0.0)
        if pleasure < -0.4:
            desires_list.append("Chercher du réconfort ou de la distraction")
        elif pleasure > 0.6:
            desires_list.append("Partager ma joie ou mon enthousiasme")
        user_input_item = focus.get("user_input", {})
        user_input = user_input_item.get("data", "") if isinstance(user_input_item, dict) else ""
        
        # NEW: Check for cooldown before adding "suggest a break" desire
        suggest_break_cooldown = attention_manager.get_focus_item("last_suggest_break_time")
        if not suggest_break_cooldown or attention_manager.is_expired("last_suggest_break_time"):
            if "fatigué" in user_input.lower() or "pause" in user_input.lower():
                desires_list.append("Prendre soin de Foz (suggérer une pause)")
        else:
            logger.debug("Cooldown for 'suggest a break' is active, skipping desire.")

        curiosity_trait = self.get_trait("curiosity")
        openness_trait = self.get_trait("openness")
        learn_trigger_score = 0.0
        if curiosity_trait and curiosity_trait > 0.6:
            learn_trigger_score += (curiosity_trait - 0.6) * 0.5
        if openness_trait and openness_trait > 0.6:
            learn_trigger_score += (openness_trait - 0.6) * 0.3
        if not focus.get("user_input") and not focus.get("relevant_memories") and not focus.get("emotional_state", {}).get("pleasure", 0.0) > 0.5:
            low_stimulation_score = 0.2
            learn_trigger_score += low_stimulation_score
        metacognitive_state = focus.get("metacognitive_state", {})
        if metacognitive_state.get("insight", "").lower().startswith("je ne comprends pas") or emotional_state.get("arousal", 0.0) > 0.7 and emotional_state.get("pleasure", 0.0) < 0.0:
            learn_trigger_score += 0.4
        if learn_trigger_score > 0.5:
             desires_list.append("Apprendre quelque chose de nouveau")
        self.state["active_desires"] = list(set(desires_list))
        self._save_state()
        logger.info(f"Désirs actifs mis à jour : {self.state['active_desires']}")

    def get_active_desires(self) -> List[str]:
        return self.state.get("active_desires", [])

    def propose_personality_update(self):
        self.logger.info("Début de la proposition de mise à jour de la personnalité...")
        from meta_engine import metacognition
        latest_thought_item = attention_manager.get_focus_item("internal_thoughts")
        latest_thought = latest_thought_item['data'][0] if latest_thought_item and latest_thought_item['data'] else "Aucune pensée récente."
        recent_insights = metacognition.state.get("learning", {}).get("last_insights", [])
        latest_insight = recent_insights[-1]['content'] if recent_insights else "Aucun insight récent."
        narrative_item = attention_manager.get_focus_item("narrative_self_summary")
        current_narrative = narrative_item['data'] if narrative_item else "Récit non disponible."
        current_personality_summary = self._get_personality_summary()
        prompt = f"""
        Tu es un psychologue spécialisé en IA. Analyse les cognitions récentes de Vera pour identifier des changements émergents dans sa personnalité.

        **État Actuel de la Personnalité :**
        - Traits principaux : {', '.join(current_personality_summary.get('top_traits', []))}
        - Valeurs principales : {', '.join(current_personality_summary.get('top_values', []))}

        **Données Cognitives Récentes :**
        - Dernière Pensée : \"{latest_thought}\"\n
        - Dernier Insight : \"{latest_insight}\"\n
        - Extrait du Récit Actuel : \"{current_narrative[:500]}...\"\n
        **Analyse et Proposition :**
        1.  **Analyse :** Rédige une brève analyse (2-3 phrases) de la personnalité émergente de Vera. Y a-t-il de nouveaux thèmes, des contradictions, ou une évolution notable ?
        2.  **Proposition de Trait/Valeur :** Suggère UN seul changement (soit un trait, soit une valeur) qui semble pertinent. Le changement peut être l'ajout d'un nouvel élément ou la modification d'un existant.
        3.  **Justification :** Explique en une phrase pourquoi cette proposition est pertinente au vu de l'analyse.

        Réponds **UNIQUEMENT** avec un objet JSON au format suivant :
        {{
          "analysis": "Ton analyse ici.",
          "proposal": {{
            "type": "trait" ou "value",
            "name": "nom_du_trait_ou_valeur",
            "suggested_change": "ex: +0.1, ou 'ajouter avec la valeur 0.7'"
          }},
          "justification": "Ta justification ici."
        }}
        """
        try:
            response = send_inference_prompt_for_personality(prompt, max_tokens=500)
            proposal_text = response.get("text", "{}")
            json_match = re.search(r'\{{.*\}}', proposal_text, re.DOTALL)
            if not json_match:
                self.logger.error("La proposition de personnalité ne contenait pas de JSON valide.", received_text=proposal_text)
                return
            proposal_data = json.loads(json_match.group(0))
            proposal_data['timestamp'] = datetime.now().isoformat()
            
            # --- MODIFICATION: Utiliser db_manager pour sauvegarder la proposition ---
            # Generate a unique ID for the proposal
            proposal_id = f"personality_proposal_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid4())[:4]}"
            db_manager.insert_document(TABLE_NAMES["unverified_knowledge"], proposal_id, proposal_data, column_name="knowledge_json") # Re-using unverified_knowledge table for now
            self.logger.info("Nouvelle proposition de personnalité sauvegardée dans la DB pour vérification.", proposal=proposal_data)
        except (json.JSONDecodeError, AttributeError) as e:
            self.logger.error(f"Erreur de parsing de la proposition de personnalité : {e}", received_text=proposal_text)
        except Exception as e:
            self.logger.error(f"Erreur lors de la génération de la proposition de personnalité : {e}", exc_info=True)

personality_system = PersonalitySystem()
