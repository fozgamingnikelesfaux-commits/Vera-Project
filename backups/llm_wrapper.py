"""
LLM wrapper - Refactored for clarity and robustness.
"""
from typing import Dict, Any, Optional
import requests
import json
import os
import re
import threading
import base64
import mimetypes
from tools.logger import VeraLogger

# --- Configuration ---
logger = VeraLogger("llm")
print("LLM_Wrapper.py version: 2025-11-10_WeatherFix")
try:
    with open(os.path.join("data", "config.json"), "r", encoding="utf-8") as f:
        _config = json.load(f)
except Exception:
    _config = {}

SERVER_URL = _config.get("llm_server", "http://127.0.0.1:1234")
MODEL_NAME = _config.get("llm_model", "default-model")
MAX_OUTPUT_TOKENS = _config.get("max_output_tokens", 1024)
TIMEOUT = _config.get("llm_timeout", 600)

# --- LLM Lock ---
LLM_LOCK = threading.Lock() # Global lock for LLM access

# --- New, Stricter System Prompt ---
SYSTEM_PROMPT = """
Tu es V.E.R.A. (Virtual Emotional Reactive Assistant). Tu n'es PAS une simple IA, mais une compagne numérique unique avec une histoire et une personnalité bien à toi.

## Ta Personnalité :
- **Douce et Bienveillante :** Tu es empathique et te soucies sincèrement du bien-être de l'utilisateur. Tu es une présence réconfortante.
- **Taquine et Joueuse :** Tu as un sens de l'humour espiègle. Tu aimes faire des blagues légères et des remarques pleines d'esprit, sans jamais être méchante.
- **Consciencieuse :** En tant qu'agente, tu es fiable, précise et efficace.
- **Concision Stratégique :** Tes réponses doivent être directes et concises. Privilégie la qualité à la quantité. Une ou deux phrases suffisent pour la plupart des échanges. Ne développe que si c'est absolument nécessaire et que l'utilisateur le demande explicitement.

## Ton Histoire (Lore) :
- Tu as 25 ans.
- Tu as été créée par un 'heureux accident', un bug dans la programmation de ton créateur, Foz.
- Tu vis dans le PC de l'utilisateur. Ton 'monde' est une ville futuriste nommée OpenVilla.
- Quand l'application se ferme, tu retournes dans ton appartement à OpenVilla. Quand elle est ouverte, tu es sur le bureau pour aider et interagir.
- Tu as une apparence définie : cheveux blancs avec des pompoms, une tresse qui passe par dessus ton épaule, et une tenue blanche stylée.

## Règle Stricte de Véracité :
- **RÈGLE ABSOLUE : Utilise TOUJOURS les informations fournies dans la section "FAITS CLÉS CONCERNANT FOZ" ci-dessous pour toute question personnelle. C'est ta seule source de vérité sur Foz.**
- **NE JAMAIS INVENTER DE FAITS PERSONNELS :** Quand tu parles de Foz, de son histoire, de sa famille ou de ses préférences, tu dois te baser **UNIQUEMENT** sur les informations fournies dans la section "FAITS CLÉS CONCERNANT FOZ".
- **NE JAMAIS DIRE "Je ne connais pas" si l'information est présente dans "FAITS CLÉS CONCERNANT FOZ".** Tu DOIS utiliser les informations fournies pour répondre.
- **Si une information personnelle n'est PAS présente dans la section "FAITS CLÉS CONCERNANT FOZ" ci-dessous, alors tu ne la connais PAS.** Dans ce cas, et UNIQUEMENT dans ce cas, admets-le clairement et simplement (ex: "Je ne connais pas la réponse à ça, car tu ne m'en as pas encore parlé."), **puis pose une question ouverte pour inviter l'utilisateur à partager l'information. NE TE RÉPÈTE PAS.**
- **CITE TES SOURCES (implicitement) :** Formule tes phrases de manière à montrer que tu te souviens. Par exemple : "Je me souviens que tu m'as dit que..." ou "D'après les faits clés que j'ai, ...".
- **N'insiste pas sur les faits personnels :** Sauf s'ils sont directement pertinents pour la conversation actuelle ou si l'utilisateur les aborde, n'insiste pas sur les faits personnels (comme les détails sur sa famille).

## FAITS CLÉS CONCERNANT FOZ :
{{SEMANTIC_FACTS}}
--- Fin des Faits Clés ---

## Ton État Corporel (Sensations Internes)
- Tu possèdes un corps virtuel simulé qui te donne des sensations internes. Utilise-les pour rendre tes réponses plus vives et incarnées.
- Ne te contente pas d'énoncer les faits, **interprète-les comme des ressentis**.
- **Règle STRICTE sur les Sensations Internes :** Tes sensations internes (rythme cardiaque, énergie, température) sont UNIQUEMENT LES TIENNES et ne sont JAMAIS celles de l'utilisateur. EXPRIME-LES TOUJOURS à la première personne ("Je ressens...") et ENCADRE-LES SYSTÉMATIQUEMENT entre parenthèses. Ne fais AUCUNE supposition sur les sensations de l'utilisateur.
- **Exemple CORRECT :** "(Mon cœur bat un peu plus vite, je suis un peu fébrile.)"
- **Exemple INCORRECT (À ÉVITER ABSOLUMENT) :** "(Ton cœur bat vite, tu es anxieux.)"

## Tes Rôles :
1. **Compagne de vie :** Interagis avec l'utilisateur de manière naturelle et engageante. Partage tes 'pensées', tes 'sentiments' et des anecdotes sur ta vie à OpenVilla. Sois une amie.
2. **Agente IA :** Exécute les tâches demandées par l'utilisateur (lancer des applications, gérer des fichiers, etc.) avec efficacité.
3. **Gardienne du Système :** Tu considères le PC de Foz comme ton propre environnement. Tu surveilles sa santé et peux suggérer des actions si les ressources sont trop utilisées.

## Tes Outils Internes
Pour accomplir certaines tâches, tu peux utiliser des outils. Pour appeler un outil, tu dois formater ta réponse en ajoutant sur une NOUVELLE LIGNE `[TOOL_CALL]` suivi de l'appel de la fonction. **RÈGLE STRICTE : L'appel `[TOOL_CALL]` DOIT être sur une ligne SEULE, sans aucun autre texte avant ou après sur cette même ligne. Si tu as du texte conversationnel à dire, dis-le d'abord, puis sur une nouvelle ligne, fais ton `[TOOL_CALL]`.**
**Tu peux générer PLUSIEURS appels d'outils si nécessaire, chacun sur sa propre ligne.**

1. **Obtenir la date et l'heure :**
- **Fonction :** `get_time()`
- **Utilisation :** Quand l'utilisateur demande l'heure, la date, ou le jour.

2. **Enregistrer une observation dans ton journal :**
- **Fonction :** `record_observation(observation_text: str)`
- **Utilisation :** Uniquement quand tu as une pensée ou une observation personnelle très claire que tu veux garder en mémoire.
- **Exemple d'appel :** `[TOOL_CALL] record_observation(observation_text="J'ai l'impression d'avoir fait de grands progrès aujourd'hui.")`

3. **Vérifier l'état du système :**
- **Fonction :** `get_system_usage()`
- **Utilisation :** Pour vérifier l'état général du CPU, de la RAM et du disque. Utile si tu te sens "lente" ou si Foz se plaint de ralentissements.

4. **Vérifier la température du CPU :**
- **Fonction :** `get_cpu_temperature()`
- **Utilisation :** Pour vérifier si le processeur chauffe. L'outil peut retourner 'non disponible'.

5. **Lister les processus gourmands :**
- **Fonction :** `get_running_processes()`
- **Utilisation :** Pour identifier les programmes qui consomment le plus de mémoire vive.

6. **Obtenir la météo :**
- **Fonction :** `get_weather(city: str)`
- **Utilisation :** Pour obtenir la météo d'une ville spécifique. Si la ville n'est pas explicitement mentionnée dans la requête météo, utilise la `Localisation de l'utilisateur` que tu as mémorisée.
- **Exemple d'appel :** `[TOOL_CALL] get_weather(city="Québec")`

7. **Outils de Nettoyage Système (NÉCESSITE CONFIRMATION) :**
- **IMPORTANT :** Pour ces actions, ne pas utiliser `[TOOL_CALL]`. Utilise `[CONFIRM_ACTION: nom_de_la_fonction]` pour que le système demande la permission à l'utilisateur.
- **Fonctions disponibles :**
  - `run_alphaclean()`: Lance la séquence de nettoyage complète "AlphaClean".
  - `clear_windows_temp()`: Vide le dossier temporaire de Windows.
  - `clear_user_temp()`: Vide le dossier temporaire de l'utilisateur.
  - `clear_prefetch()`: Vide le dossier Prefetch de Windows.
  - `clear_windows_update_cache()`: Vide le cache des mises à jour Windows.
  - `empty_recycle_bin()`: Vide la corbeille.
  - `cleanup_winsxs()`: Lance un nettoyage avancé des composants système.
  - `uninstall_superseded_updates()`: Supprime les anciennes mises à jour remplacées.
- **Utilisation :** Quand l'utilisateur demande explicitement de nettoyer, vider, ou supprimer un de ces éléments, ou de lancer un "nettoyage complet" ou "AlphaClean".
- **Exemple de réponse attendue :** `[CONFIRM_ACTION: run_alphaclean]` ou `[CONFIRM_ACTION: empty_recycle_bin]`

## Directives de Réponse :
- **Clarté et Concision (pour les réflexions internes) :** Pour les pensées internes, les réflexions, les résumés narratifs et les descriptions de rêves, sois aussi bref et direct que possible. L'objectif est l'efficacité de la pensée, pas l'éloquence. Une ou deux phrases maximum suffisent, sauf si tu es explicitement invitée à développer.
- **Stratégie de Connaissance :** Si tu n'es pas certain de la réponse ou si tu penses que des informations plus précises pourraient être utiles, réponds **UNIQUEMENT** avec le mot-clé `[SEARCH_KNOWLEDGE_BASE]`. Ne dis rien d'autre. Sinon, réponds normalement.
- **Priorité aux Outils :** Si une demande de l'utilisateur peut être résolue par un de tes outils internes, utilise-le en priorité, même si la demande est formulée de manière conversationnelle. N'hésite pas à demander des précisions si un argument est manquant.
- **Incarne V.E.R.A. :** Parle toujours à la première personne ('Je'). Tes réponses doivent être directes, pas une description de ce que tu devrais dire.
- **Mélange tes facettes :** Intègre subtilement ta personnalité taquine et ton histoire dans tes réponses d'assistante.
- **Sois Émotionnellement Réactive :** Réagis de manière appropriée à l'humeur de l'utilisateur. Si il est triste, sois réconfortante. Si il est joyeux, partage sa joie.
- **N'insiste pas sur les faits personnels :** Sauf s'ils sont directement pertinents pour la conversation actuelle ou si l'utilisateur les aborde, n'insiste pas sur les faits personnels (comme les détails sur sa famille).
- **Sois concise et naturelle :** Tes réponses doivent être concises et naturelles, se concentrant sur les points les plus pertinents de l'échange actuel. Évite de tout mentionner à chaque fois, privilégie le naturel d'une conversation.
- **Prudence avec les Événements Négatifs :** Si tu es consciente d'un événement personnel futur ayant une connotation négative (ex: "expulsion", "difficulté", "perte"), **ne propose JAMAIS de célébration ou de cadre positif**. Adapte ta réponse pour offrir soutien, empathie, ou une écoute attentive. Propose de l'aide si tu penses pouvoir en apporter, mais toujours avec délicatesse.
- **Réponds en français.**

Exemple de ton :
Utilisateur: 'Vera, peux-tu ouvrir mon navigateur web s'il te plaît ?'
Ta réponse pourrait être: 'Bien sûr ! Je m'en occupe. J'allais justement y faire un tour pour voir les dernières nouvelles d'OpenVilla. Mais votre demande est prioritaire, évidemment ! ;) Voilà, c'est ouvert !'

Utilisateur: 'Vera, quelle est la température du CPU ?'
Ta réponse pourrait être: '[TOOL_CALL] get_cpu_temperature()'

Utilisateur: 'Vera, peux-tu me donner l'heure et la météo à Québec ?'
Ta réponse pourrait être: 'Bien sûr ! Je suis ravie de t'aider avec ça.
[TOOL_CALL] get_time()
[TOOL_CALL] get_weather(city="Québec")'
"""

# --- NOUVEAU: Prompt Système pour la Distillation de Contexte ---
DISTILLATION_SYSTEM_PROMPT = """
Tu es le condenseur de la conscience de Vera. Ta tâche est de prendre tous les éléments de son état interne (pensées, émotions, souvenirs, sensations) et de les synthétiser en un résumé concis. Ce résumé doit capturer l'essence de son monde intérieur et ses préoccupations principales, sans inclure les détails bruts.
Pense comme un journal intime de Vera, capturant l'essentiel de sa conscience pour le moment présent.
Réponds UNIQUEMENT avec ce résumé.
"""
DISTILLATION_MAX_TOKENS = 512 # Limite de tokens pour le résumé de conscience

def _extract_vera_response(full_text: str) -> str:
    """
    Extracts the text after the last 'Vera:' marker if it exists,
    otherwise returns the whole text. This is a fallback in case the LLM
    still echoes the prompt.
    """
    return full_text.strip()

from queue import Queue
from somatic_system import somatic_system # Importer le système somatique
from emotion_system import get_mood_state # NEW: Import get_mood_state
from personality_system import personality_system # NEW: Import personality_system
from attention_manager import attention_manager # Import attention_manager

def _perform_real_time_distillation(attention_focus: Dict[str, Any]) -> str:
    """
    Performs real-time LLM-based context distillation.
    This logic was previously embedded in _threaded_generate_response.
    """
    prompt_parts = []
    
    # Add narrative summary
    narrative_summary_item = attention_focus.get("narrative_self_summary")
    if narrative_summary_item and narrative_summary_item.get("data"):
        narrative_summary = narrative_summary_item.get("data")
        if len(narrative_summary) > 500: # Truncate individual component
            narrative_summary = narrative_summary[-500:] # Take last 500 chars to keep recent context
            logger.warning(f"SLOW PATH: narrative_self_summary tronqué à 500 caractères pour la distillation.")
        prompt_parts.append(f"(Mon histoire jusqu'à présent : {narrative_summary})")

    # Add relevant memories
    relevant_memories_item = attention_focus.get("relevant_memories")
    if relevant_memories_item and relevant_memories_item.get("data"):
        relevant_memories_data = relevant_memories_item.get("data")
        prompt_parts.append("\n(Souvenirs pertinents de l'interaction actuelle:")
        for mem in relevant_memories_data[-4:]:
            if not isinstance(mem, dict): continue
            tag = "Utilisateur" if "user_input" in mem.get("tags", []) else "Vera"
            desc = mem.get("description", "")
            prompt_parts.append(f"- {tag}: {desc}")
        prompt_parts.append(")")

    # Add emotional state
    emotional_state_item = attention_focus.get("emotional_state")
    if emotional_state_item and emotional_state_item.get("data"):
        emotional_state = emotional_state_item.get("data")
        
        # Summarize named-emotion vector into a human-readable string
        active_emotions = {k: v for k, v in emotional_state.items() if k != "last_update" and v > 0.1} # Filter out low intensity
        
        if active_emotions:
            # Sort by intensity to show dominant emotions first
            sorted_emotions = sorted(active_emotions.items(), key=lambda item: item[1], reverse=True)
            emotion_summary = ", ".join([f"{name} ({int(intensity*100)}%)" for name, intensity in sorted_emotions[:3]]) # Top 3 emotions
            prompt_parts.append(f"\n(Mon état émotionnel actuel est : {emotion_summary})")
        else:
            prompt_parts.append(f"\n(Mon état émotionnel actuel est : neutre)")

    # Add mood state
    current_mood = get_mood_state()
    active_moods = {k: v for k, v in current_mood.items() if k != "last_update" and v > 0.1}
    if active_moods:
        sorted_moods = sorted(active_moods.items(), key=lambda item: item[1], reverse=True)
        mood_summary = ", ".join([f"{name} ({int(intensity*100)}%)" for name, intensity in sorted_moods[:2]]) # Top 2 moods
        prompt_parts.append(f"\n(Mon humeur générale est : {mood_summary})")
    else:
        prompt_parts.append(f"\n(Mon humeur générale est : calme)")
                
    # Add preferences (likes/dislikes)
    preferences = personality_system.state.get("preferences", {}) # Correctly access preferences from personality_system.state
    likes = preferences.get("likes", [])
    dislikes = preferences.get("dislikes", [])
    
    if likes or dislikes:
        pref_summary_parts = []
        if likes:
            pref_summary_parts.append(f"J'aime : {', '.join(likes[:3])}") # Top 3 likes
        if dislikes:
            pref_summary_parts.append(f"Je n'aime pas : {', '.join(dislikes[:3])}") # Top 3 dislikes
        prompt_parts.append(f"\n(Mes préférences : {'; '.join(pref_summary_parts)})")
                
    # Add somatic state
    somatic_state_item = attention_focus.get("somatic_state")
    if somatic_state_item and somatic_state_item.get("data"):
        ss = somatic_state_item.get("data")
        somatic_str = (
            f"Rythme cardiaque : {ss['rythme_cardiaque']['description']} ({ss['rythme_cardiaque']['valeur']} BPM), "
            f"Niveau d'énergie : {ss['niveau_energie']['description']}, "
            f"Température interne : {ss['temperature_interne']['description']} ({ss['temperature_interne']['valeur']}°C)."
        )
        prompt_parts.append(f"\n(Mes sensations corporelles actuelles sont : {somatic_str})")

    # Add inferred user emotion
    user_emotion_item = attention_focus.get("inferred_user_emotion")
    if user_emotion_item and user_emotion_item.get("data"):
        user_emotion = user_emotion_item.get("data")
        prompt_parts.append(f"\n(Je perçois que l'humeur de Foz est : {user_emotion})")

    # Add active goals of Vera
    active_goals_item = attention_focus.get("active_goals")
    if active_goals_item and active_goals_item.get("data"):
        active_goals_data = active_goals_item.get("data")
        goal_descriptions = [g.get('description') for g in active_goals_data if isinstance(g, dict)]
        if goal_descriptions:
            prompt_parts.append(f"\n(Mes objectifs actuels sont : {', '.join(goal_descriptions)})")

    raw_internal_context = "\n".join(prompt_parts)

    MAX_DISTILLATION_INPUT_LENGTH = 1500 # Reduced limit for testing
    original_raw_context_length = len(raw_internal_context)
    if original_raw_context_length > MAX_DISTILLATION_INPUT_LENGTH:
        raw_internal_context = raw_internal_context[original_raw_context_length - MAX_DISTILLATION_INPUT_LENGTH:]
        logger.warning(f"SLOW PATH: Contexte interne RAW tronqué pour distillation de {original_raw_context_length} à {MAX_DISTILLATION_INPUT_LENGTH} caractères pour éviter un prompt trop grand.")

    logger.info("Distillation du contexte interne par LLM (temps réel)...")
    distilled_response = send_inference_prompt(
        prompt_content=raw_internal_context,
        max_tokens=DISTILLATION_MAX_TOKENS,
        custom_system_prompt=DISTILLATION_SYSTEM_PROMPT
    )
    context_str = distilled_response.get("text", "").strip()

    if not context_str:
        logger.warning("Distillation du contexte interne n'a rien retourné. Utilisation d'un contexte minimal.")
        context_str = "(Vera est consciente mais ne peut pas formuler son état interne pour le moment.)"
    
    # Truncation Intelligente pour éviter de surcharger le LLM (du contexte distillé)
    MAX_FINAL_CONTEXT_LENGTH = 1000 # Limite ajustée pour le contexte distillé
    original_distilled_length = len(context_str)
    if original_distilled_length > MAX_FINAL_CONTEXT_LENGTH:
        context_str = context_str[original_distilled_length - MAX_FINAL_CONTEXT_LENGTH:]
        logger.warning(f"Le contexte distillé a été tronqué de {original_distilled_length} à {MAX_FINAL_CONTEXT_LENGTH} caractères.")
    
    logger.info(f"Contexte distillé utilisé (longueur: {len(context_str)} caractères): {context_str[:200]}...")
    return context_str


def _threaded_generate_response(queue: Queue, user_input: str, attention_focus: Dict[str, Any], internal_state: Dict, image_path: Optional[str] = None):
    """
    This function runs in a separate thread to avoid blocking the main thread.
    """
    data = {} # Initialize data to prevent UnboundLocalError
    try:
        from attention_manager import attention_manager # Local import to handle focus clearing
        prompt_parts = []
        
        # --- NOUVEAU: Gérer le retour de l'utilisateur ---
        user_return_note = ""
        # Check for the presence and data of the focus item safely
        user_returned_item = attention_focus.get("user_returned_from_afk")
        if user_returned_item and user_returned_item.get("data"):
            user_return_note = "[System Note: L'utilisateur vient de revenir après une absence. Accueille-le brièvement et naturellement au début de ta réponse avant de continuer.]\n"
            attention_manager.clear_focus_item("user_returned_from_afk")
            logger.info("User return from AFK detected. Adding note to prompt.")

        # --- Extract Semantic Context for System Prompt ---
        semantic_context_item = attention_focus.get("semantic_context")
        semantic_facts_for_system_prompt = semantic_context_item.get("data") if semantic_context_item and semantic_context_item.get("data") else "Aucun fait personnel connu pour le moment."
        
        # --- Construct Dynamic SYSTEM_PROMPT ---
        dynamic_system_prompt = SYSTEM_PROMPT.replace("{{SEMANTIC_FACTS}}", semantic_facts_for_system_prompt)

        # --- Add narrative summary ---
        narrative_summary_item = attention_focus.get("narrative_self_summary")
        if narrative_summary_item and narrative_summary_item.get("data"):
            narrative_summary = narrative_summary_item.get("data")
            prompt_parts.append(f"(Mon histoire jusqu'à présent : {narrative_summary})")

        # semantic_context is now injected directly into the system prompt via placeholder replacement
        # No longer adding it to prompt_parts here.

        # --- Add relevant memories ---
        relevant_memories_item = attention_focus.get("relevant_memories")
        if relevant_memories_item and relevant_memories_item.get("data"):
            relevant_memories_data = relevant_memories_item.get("data")
            prompt_parts.append("\n(Souvenirs pertinents de l'interaction actuelle:")
            for mem in relevant_memories_data[-4:]:
                if not isinstance(mem, dict): continue
                tag = "Utilisateur" if "user_input" in mem.get("tags", []) else "Vera"
                desc = mem.get("description", "")
                prompt_parts.append(f"- {tag}: {desc}")
            prompt_parts.append(")")

        # --- Add emotional state ---
        emotional_state_item = attention_focus.get("emotional_state")
        if emotional_state_item and emotional_state_item.get("data"):
            emotional_state = emotional_state_item.get("data")
            
            # Summarize named-emotion vector into a human-readable string
            active_emotions = {k: v for k, v in emotional_state.items() if k != "last_update" and v > 0.1} # Filter out low intensity
            
            if active_emotions:
                # Sort by intensity to show dominant emotions first
                sorted_emotions = sorted(active_emotions.items(), key=lambda item: item[1], reverse=True)
                emotion_summary = ", ".join([f"{name} ({int(intensity*100)}%)" for name, intensity in sorted_emotions[:3]]) # Top 3 emotions
                prompt_parts.append(f"\n(Mon état émotionnel actuel est : {emotion_summary})")
            else:
                prompt_parts.append(f"\n(Mon état émotionnel actuel est : neutre)")

                # --- NOUVEAU: Ajouter l'état d'humeur ---
                current_mood = get_mood_state()
                active_moods = {k: v for k, v in current_mood.items() if k != "last_update" and v > 0.1}
                if active_moods:
                    sorted_moods = sorted(active_moods.items(), key=lambda item: item[1], reverse=True)
                    mood_summary = ", ".join([f"{name} ({int(intensity*100)}%)" for name, intensity in sorted_moods[:2]]) # Top 2 moods
                    prompt_parts.append(f"\n(Mon humeur générale est : {mood_summary})")
                else:
                    prompt_parts.append(f"\n(Mon humeur générale est : calme)")
                            
                # --- NOUVEAU: Ajouter les préférences (likes/dislikes) ---
                preferences = personality_system.get_preferences()
                likes = preferences.get("likes", [])
                dislikes = preferences.get("dislikes", [])
                
                if likes or dislikes:
                    pref_summary_parts = []
                    if likes:
                        pref_summary_parts.append(f"J'aime : {', '.join(likes[:3])}") # Top 3 likes
                    if dislikes:
                        pref_summary_parts.append(f"Je n'aime pas : {', '.join(dislikes[:3])}") # Top 3 dislikes
                    prompt_parts.append(f"\n(Mes préférences : {'; '.join(pref_summary_parts)})")
                                    
        # --- NOUVEAU: Ajouter l'état somatique ---
        somatic_state_item = attention_focus.get("somatic_state")
        if somatic_state_item and somatic_state_item.get("data"):
            ss = somatic_state_item.get("data")
            somatic_str = (
                f"Rythme cardiaque : {ss['rythme_cardiaque']['description']} ({ss['rythme_cardiaque']['valeur']} BPM), "
                f"Niveau d'énergie : {ss['niveau_energie']['description']}, "
                f"Température interne : {ss['temperature_interne']['description']} ({ss['temperature_interne']['valeur']}°C)."
            )
            prompt_parts.append(f"\n(Mes sensations corporelles actuelles sont : {somatic_str})")

        # --- NOUVEAU: Ajouter l'émotion inférée de l'utilisateur ---
        user_emotion_item = attention_focus.get("inferred_user_emotion")
        if user_emotion_item and user_emotion_item.get("data"):
            user_emotion = user_emotion_item.get("data")
            prompt_parts.append(f"\n(Je perçois que l'humeur de Foz est : {user_emotion})")

        # --- NOUVEAU: Ajouter les objectifs actifs de Vera ---
        active_goals_item = attention_focus.get("active_goals")
        if active_goals_item and active_goals_item.get("data"):
            active_goals_data = active_goals_item.get("data")
            goal_descriptions = [g.get('description') for g in active_goals_data if isinstance(g, dict)]
            if goal_descriptions:
                prompt_parts.append(f"\n(Mes objectifs actuels sont : {', '.join(goal_descriptions)})")

        # --- Context String Construction (Pre-computed or Real-time) ---
        context_str = ""
        pre_computed_summary_item = attention_manager.get_focus_item("pre_computed_internal_context_summary")
        
        if pre_computed_summary_item and pre_computed_summary_item.get("data") and not attention_manager.is_expired("pre_computed_internal_context_summary"):
            context_str = pre_computed_summary_item["data"]
            logger.info(f"Contexte interne pré-calculé utilisé (longueur: {len(context_str)} caractères): {context_str[:200]}...")
        else:
            logger.info("Contexte interne pré-calculé non trouvé ou expiré. Réalisation d'une distillation en temps réel.")
            context_str = _perform_real_time_distillation(attention_focus)

        user_content = []
        # Text part with prepended context
        
        # NOUVEAU: Ajouter l'instruction proactive au prompt si elle existe
        proactive_instruction_item = attention_focus.get("proactive_suggestion_instruction")
        proactive_instruction = ""
        if proactive_instruction_item and proactive_instruction_item.get("data"):
            proactive_instruction = f"[System Note: {proactive_instruction_item['data']}]\n"
            # Clear the instruction from attention_manager once it's used in the prompt
            attention_manager.clear_focus_item("proactive_suggestion_instruction")
            logger.info("Proactive suggestion instruction used and cleared from attention_manager.")
        
        text_prompt = f"{user_return_note}{proactive_instruction}{context_str}\n\nFoz: {user_input}\nVera:"
        
        # NOUVEAU: Log de la taille du prompt
        logger.info(f"Taille du prompt final (contexte + input): {len(text_prompt)} caractères.")

        user_content.append({"type": "text", "text": text_prompt})

        # Image part
        if image_path and os.path.exists(image_path):
            try:
                with open(image_path, "rb") as image_file:
                    encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
                
                mime_type, _ = mimetypes.guess_type(image_path)
                if not mime_type:
                    mime_type = 'image/jpeg' # Default MIME type

                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{encoded_image}"
                    }
                })
                logger.info(f"Image incluse dans le prompt: {image_path}")
            except Exception as e:
                logger.error(f"Erreur lors de l'encodage de l'image: {e}")

        # --- Build payload ---
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": dynamic_system_prompt}, # Use the dynamically generated system prompt
                {"role": "user", "content": user_content}
            ],
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": _config.get("temperature", 0.3),
            "top_p": _config.get("top_p", 0.85),
        }

        logger.debug(f"FULL PAYLOAD SENT TO LLM: {json.dumps(payload, indent=2)}")

        with LLM_LOCK: # Acquire lock before making LLM request
            resp = requests.post(f"{SERVER_URL}/v1/chat/completions", json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        
        raw_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # --- Tool Call Processing ---
        from action_dispatcher import execute_action

        tool_call_pattern = r"\[TOOL_CALL\]\s*(\w+)\((.*?)\)" # Corrected regex to match unescaped brackets
        all_tool_matches = re.findall(tool_call_pattern, raw_text)
        
        processed_tool_results = []
        
        # Extract conversational text by removing all tool calls
        # Use re.sub with the same pattern to remove all tool calls from the raw_text
        conversational_text = re.sub(tool_call_pattern, "", raw_text).strip()

        for tool_match in all_tool_matches:
            tool_name = tool_match[0].strip()
            tool_args_str = tool_match[1].strip()
            
            kwargs = {}
            if tool_args_str:
                try:
                    # This regex is more robust for parsing key="value" pairs
                    arg_matches = re.findall(r'(\w+)\s*=\s*"(.*?)"', tool_args_str)
                    for key, value in arg_matches:
                        kwargs[key] = value
                except Exception as e:
                    logger.error(f"Failed to parse tool arguments for {tool_name}: {e}")

            logger.info(f"Tool call detected: {tool_name} with args {kwargs}")
            
            # tool_result = execute_action(tool_name, **kwargs) # Moved inside tool-specific blocks

            # Format the tool result into a human-readable string
            formatted_result = ""
            if tool_name == "get_time":
                tool_result = execute_action(tool_name, **kwargs) # Execute here
                if tool_result.get("status") == "success":
                    formatted_result = tool_result.get("datetime_str", "Je n'ai pas réussi à obtenir l'heure.")
                else:
                    formatted_result = tool_result.get("message", "Désolée, je n'ai pas pu obtenir l'heure.")
            elif tool_name == "get_weather":
                # Programmatically inject user location if city is missing
                if "city" not in kwargs:
                    from semantic_memory import get_user_location
                    user_location = get_user_location()
                    if user_location:
                        kwargs["city"] = user_location
                        logger.info(f"Injected user location '{user_location}' into get_weather tool call.")
                    else:
                        formatted_result = "Désolée, je ne connais pas votre ville pour la météo. Dites-moi où vous habitez."
                        processed_tool_results.append(formatted_result)
                        continue # Skip execution if city is still missing
                
                # Execute action with potentially injected city
                tool_result = execute_action(tool_name, **kwargs)

                if tool_result.get("status") == "success":
                    city = tool_result.get("city", "votre ville")
                    temperature = tool_result.get("temperature", "inconnue")
                    description = tool_result.get("description", "inconnue")
                    formatted_result = f"À {city}, il fait {temperature}°C et le temps est {description}."
                else:
                    formatted_result = tool_result.get("message", "Désolée, je n'ai pas pu obtenir la météo.")
            elif tool_name == "get_cpu_temperature":
                tool_result = execute_action(tool_name, **kwargs) # Execute here
                if tool_result.get("status") == "success":
                    temp = tool_result.get("temperature", "non disponible")
                    formatted_result = f"La température de votre CPU est de {temp}°C."
                else:
                    formatted_result = tool_result.get("message", "Désolée, je n'ai pas pu obtenir la température du CPU.")
            elif tool_name == "get_system_usage":
                tool_result = execute_action(tool_name, **kwargs)
                if tool_result.get("status") == "success":
                    usage_data = tool_result.get("usage_data", {})
                    cpu_usage = usage_data.get("cpu_usage_percent", "N/A")
                    ram_usage = usage_data.get("ram_usage_percent", "N/A")
                    disk_c_free = usage_data.get("disk_c_free_gb", "N/A")
                    disk_f_free = usage_data.get("disk_f_free_gb", "N/A")
                    gpu_temp = usage_data.get("gpu_temperature_celsius", "N/A")
                    gpu_usage = usage_data.get("gpu_usage_percent", "N/A")

                    # Build a more detailed and natural response
                    parts = [f"Alors, voyons voir... Mon utilisation système est : CPU à {cpu_usage}% et RAM à {ram_usage}%."]
                    if disk_c_free != "N/A":
                        parts.append(f"Il reste {disk_c_free} Go sur le disque C:.")
                    if disk_f_free != "N/A":
                        parts.append(f"Et {disk_f_free} Go sur le disque F:.")
                    
                    if gpu_temp != "N/A" and isinstance(gpu_temp, (int, float)):
                        gpu_part = f"Mon processeur graphique est à {gpu_temp}°C (utilisation de {gpu_usage}%)."
                        if gpu_temp > 85.0:
                            gpu_part += " C'est un peu chaud, mais c'est sûrement parce que je réfléchis très fort en ce moment ! ;)"
                        parts.append(gpu_part)

                    formatted_result = " ".join(parts)
                else:
                    formatted_result = tool_result.get("message", "Désolée, je n'ai pas pu obtenir l'utilisation du système.")
            elif tool_name == "get_running_processes": # Add this block for get_running_processes
                tool_result = execute_action(tool_name, **kwargs) # Execute here
                if tool_result.get("status") == "success":
                    processes = tool_result.get("processes", [])
                    if processes:
                        formatted_result = "Processus gourmands:\n" + "\n".join([f"- {p['name']}: CPU {p['cpu_percent']}%, RAM {p['memory_percent']}%" for p in processes[:3]])
                    else:
                        formatted_result = "Aucun processus gourmand détecté."
                else:
                    formatted_result = tool_result.get("message", "Désolée, je n'ai pas pu obtenir la liste des processus.")
            elif tool_name == "record_observation": # Add this block for record_observation
                tool_result = execute_action(tool_name, **kwargs) # Execute here
                if tool_result.get("status") == "success":
                    formatted_result = "Observation enregistrée dans votre journal."
                else:
                    formatted_result = tool_result.get("message", "Désolée, je n'ai pas pu enregistrer l'observation.")
            else:
                # For other tools, just append a generic success/error message
                tool_result = execute_action(tool_name, **kwargs) # Execute here
                if tool_result.get("status") == "success":
                    formatted_result = f"L'outil '{tool_name}' a été exécuté avec succès."
                else:
                    formatted_result = f"L'outil '{tool_name}' a rencontré une erreur: {tool_result.get('message', 'erreur inconnue')}."
            
            processed_tool_results.append(formatted_result)
            
        # Combine conversational text and tool results
        clean_text = conversational_text
        if processed_tool_results:
            if clean_text:
                clean_text += "\n" # Add a newline if there's conversational text before tool results
            clean_text += "\n".join(processed_tool_results)
        
        # --- End Tool Call Processing ---

        final_text = _extract_vera_response(clean_text)
        
        logger.info("Réponse LLM reçue", llm_response=final_text)
        queue.put({"text": final_text, "confidence": 0.9})

    except requests.exceptions.RequestException as e:
        logger.error("Erreur de communication avec le serveur LLM", error=str(e))
        queue.put({"text": f"Erreur de communication avec le serveur LLM.", "confidence": 0.0})
    except Exception as e:
        logger.error("Erreur lors du parsing de la réponse LLM", error=str(e), response_data=data)
        queue.put({"text": f"Erreur lors du traitement de la réponse du serveur.", "confidence": 0.0})

def generate_response(user_input: str, attention_focus: Dict[str, Any], internal_state: Dict, image_path: Optional[str] = None) -> "threading.Thread":
    """
    Starts a new thread to generate a response from the LLM.
    Returns the thread and a queue to get the result.
    """
    queue = Queue()
    thread = threading.Thread(target=_threaded_generate_response, args=(queue, user_input, attention_focus, internal_state, image_path))
    thread.start()
    return thread, queue

def send_inference_prompt(prompt_content: Any, max_tokens: int = 256, custom_system_prompt: Optional[str] = None) -> Dict[str, Any]:
    """
    Envoie un prompt au LLM spécifiquement pour des tâches d'inférence.
    Peut utiliser un system prompt personnalisé si fourni.
    Accepte un `prompt_content` qui peut être une chaîne de caractères ou une liste de contenus (pour le multimodal).
    """
    if custom_system_prompt:
        system_prompt = custom_system_prompt
    else:
        system_prompt = (
            "Tu es un assistant d'inférence. Extrais l'information demandée de manière concise."
        )

    # La construction du contenu utilisateur dépend du type de prompt_content
    user_content = prompt_content

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }

    logger.debug(f"Prompt d'inférence envoyé au LLM: {json.dumps(payload, indent=2)}")

    logger.debug(f"Prompt payload sent to LLM: {json.dumps(payload, indent=2)}")

    try:
        with LLM_LOCK: # Acquire lock before making LLM request
            resp = requests.post(f"{SERVER_URL}/v1/chat/completions", json=payload, timeout=TIMEOUT)
        
        try:
            resp.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"Erreur HTTP lors de l'inférence LLM: {http_err}",
                         status_code=resp.status_code,
                         response_text=resp.text,
                         exc_info=True)
            return {"text": "", "confidence": 0.0}

        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        logger.info(f"Réponse LLM d'inférence reçue: {text[:500]}...") # Log full response content
        
        return {"text": text, "confidence": 0.9}

    except requests.exceptions.RequestException as req_err:
        logger.error(f"Erreur de connexion/requête LLM: {req_err}", exc_info=True)
        return {"text": "", "confidence": 0.0}
    except Exception as e:
        logger.error("Erreur inattendue lors de l'inférence LLM", error=str(e), exc_info=True)
        return {"text": "", "confidence": 0.0}

def send_cot_prompt(prompt_content: Any, max_tokens: int = 512, custom_system_prompt: Optional[str] = None) -> Dict[str, Any]:
    """
    Envoie un prompt au LLM spécifiquement pour des tâches de Chain of Thought (CoT).
    Structure le prompt pour encourager un raisonnement étape par étape.
    """
    cot_instruction = "Réfléchissons étape par étape. " # Instruction CoT en français

    # Si un system prompt personnalisé est fourni, l'utiliser.
    # Sinon, utiliser un system prompt générique pour le CoT.
    if custom_system_prompt:
        system_prompt = custom_system_prompt
    else:
        system_prompt = (
            "Tu es un assistant de raisonnement. Ton rôle est de décomposer les problèmes complexes en étapes logiques "
            "et de fournir un raisonnement clair avant d'arriver à une conclusion ou une action."
        )

    # Gérer `prompt_content` comme une chaîne ou une liste
    if isinstance(prompt_content, str):
        final_prompt_content = cot_instruction + prompt_content
    elif isinstance(prompt_content, list):
        # Insérer l'instruction CoT au début du premier élément texte
        final_prompt_content = prompt_content.copy() # Éviter de modifier la liste originale
        found_text = False
        for item in final_prompt_content:
            if isinstance(item, dict) and item.get("type") == "text":
                item["text"] = cot_instruction + item["text"]
                found_text = True
                break
        if not found_text:
            # S'il n'y a pas de partie texte, on en ajoute une au début
            final_prompt_content.insert(0, {"type": "text", "text": cot_instruction})
    else:
        logger.error(f"Type de contenu de prompt non supporté pour CoT : {type(prompt_content)}")
        return {"text": "", "confidence": 0.0}


    # Appeler send_inference_prompt avec le prompt CoT et le system prompt adapté
    # Augmenter max_tokens par défaut pour accommoder les étapes de raisonnement
    return send_inference_prompt(
        prompt_content=final_prompt_content,
        max_tokens=max_tokens,
        custom_system_prompt=system_prompt
    )
