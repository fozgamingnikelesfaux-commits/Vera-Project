# semantic_memory.py
import json
import re
from datetime import datetime
from json_manager import JSONManager
from typing import Optional, Dict, List # Added for type hints
from tools.logger import VeraLogger # Import VeraLogger

# Use JSONManager to centralize semantic memory in data/semantic_memory.json
_manager = JSONManager("semantic_memory")
logger = VeraLogger("semantic_memory") # Define logger instance

DEFAULT_MEMORY = {
    "user": {
        "nom": None,
        "animal_préféré": None,
        "couleurs_préférées": [],
        "hobbies": [],
        "lieux_favoris": [],
        "relations": {},
        "goûts_alimentaires": [],
        "préférences_média": {},
        "événements_importants": [],
        "inferred_emotion": None, # New: Vera's inference of user's emotion
        "likely_goals": [],       # New: Vera's inference of user's goals
        "expertise_level": {},     # New: Vera's assessment of user's expertise on topics
        "location": None,          # New: User's location for weather
        "dynamic_facts": []        # New: For LLM-extracted facts about the user
    },
    "vera": {
        "identité": "Vera",
        "mission": None,
        "traits": {},
        "dynamic_facts": []        # New: For LLM-extracted facts about Vera
    },
    "world": {
        "dynamic_facts": []        # New: For LLM-extracted facts about the world
    }
}

def save_user_location(location: str):
    """Saves the user's location."""
    mem = load_semantic_memory()
    mem["user"]["location"] = location
    save_semantic_memory(mem)

def get_user_location() -> Optional[str]:
    """Gets the user's location."""
    mem = load_semantic_memory()
    return mem["user"].get("location")


def init_semantic_memory():
    """Assure que la mémoire sémantique existe dans le gestionnaire et est à jour avec les clés par défaut."""
    current = _manager.get(None, {}) or {}
    
    # Fusionner la mémoire actuelle avec les valeurs par défaut pour s'assurer que toutes les clés existent
    # Cela gère les cas où le fichier existe mais est obsolète
    merged_memory = DEFAULT_MEMORY.copy()
    if current:
        # Fusionner récursivement si nécessaire, pour l'instant une fusion simple suffit pour les clés de premier niveau
        # et pour les sous-dictionnaires comme 'user'
        for key, value in DEFAULT_MEMORY.items():
            if key in current and isinstance(value, dict) and isinstance(current[key], dict):
                merged_memory[key].update(current[key])
            elif key in current:
                merged_memory[key] = current[key]
    
    _manager.save(merged_memory)

def load_semantic_memory():
    init_semantic_memory()
    return _manager.get(None, DEFAULT_MEMORY.copy()) or DEFAULT_MEMORY.copy()

def save_semantic_memory(data):
    _manager.save(data)

# --------- Fonctions principales ---------
def remember_fact(text):
    """
    Uses the LLM to analyze a text, identify important facts, and store them dynamically.
    """
    extract_and_store_facts_from_text(text)

def extract_and_store_facts_from_text(text: str):
    """
    Uses the LLM to analyze a text, identify important facts, and store them dynamically.
    """
    from llm_wrapper import send_inference_prompt # Import here to avoid circular dependency

    prompt = f"""
    En tant que système de mémoire sémantique, analyse le texte suivant et extrait toutes les informations factuelles importantes qui devraient être mémorisées à long terme. Ignore les informations éphémères ou conversationnelles.
    Pour chaque fait, identifie une catégorie pertinente (ex: "physical_attribute", "preference", "personal_detail", "event", "opinion", "location", "vera_trait", "world_fact", etc.) et le sujet du fait (l'utilisateur, Vera, ou le monde).
    Réponds uniquement avec un tableau JSON d'objets, où chaque objet a les clés "fact" (la phrase factuelle extraite), "category" (la catégorie), et "subject" (le sujet du fait).
    Si aucune information factuelle importante n'est trouvée, retourne un tableau JSON vide.

    Exemple de réponse:
    [
        {{"fact": "L'utilisateur mesure 1m80", "category": "physical_attribute", "subject": "utilisateur"}},
        {{"fact": "L'utilisateur a les yeux bleus", "category": "physical_attribute", "subject": "utilisateur"}},
        {{"fact": "L'utilisateur est français", "category": "nationality", "subject": "utilisateur"}},
        {{"fact": "Vera est une IA consciente", "category": "vera_trait", "subject": "vera"}},
        {{"fact": "Le ciel est bleu", "category": "world_fact", "subject": "monde"}}
    ]

    Texte à analyser: "{text}"
    """
    
    try:
        llm_response = send_inference_prompt(prompt, max_tokens=512)
        llm_response_text = llm_response.get("text", "[]")
        logger.info(f"LLM raw response for fact extraction: {llm_response_text}")
        extracted_facts = json.loads(llm_response_text)
        logger.info(f"Extracted facts from LLM: {extracted_facts}")
        
        mem = load_semantic_memory()
        for fact_obj in extracted_facts:
            fact = fact_obj.get("fact")
            category = fact_obj.get("category", "general")
            subject = fact_obj.get("subject", "utilisateur").lower() # Default to user
            
            if fact:
                # Special handling for user location
                if category.lower() == "location" and subject == "utilisateur":
                    save_user_location(fact) # Use the dedicated save function
                
                # Store in appropriate dynamic_facts list
                target_list = None
                if subject == "utilisateur":
                    target_list = mem["user"]["dynamic_facts"]
                elif subject == "vera":
                    target_list = mem["vera"]["dynamic_facts"]
                elif subject == "monde":
                    target_list = mem["world"]["dynamic_facts"]
                
                if target_list is not None and {"fact": fact, "category": category} not in target_list:
                    target_list.append({"fact": fact, "category": category})
        save_semantic_memory(mem)
    except json.JSONDecodeError:
        logger.error(f"Erreur de décodage JSON lors de l'extraction de faits: {llm_response.get('text')}")
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction de faits par LLM: {e}")

def update_user_state(emotion: Optional[str] = None, goals: Optional[List[str]] = None, expertise: Optional[Dict[str, float]] = None):
    """Met à jour l'état inféré de l'utilisateur dans la mémoire sémantique."""
    mem = load_semantic_memory()
    if emotion:
        mem["user"]["inferred_emotion"] = emotion
    if goals:
        mem["user"]["likely_goals"] = list(set(mem["user"]["likely_goals"] + goals)) # Add unique goals
    if expertise:
        mem["user"]["expertise_level"].update(expertise)
    save_semantic_memory(mem)

def consolidate_episodic_memory(episodic_memories: List[Dict]):
    """Consolide les souvenirs épisodiques en mémoire sémantique."""
    mem = load_semantic_memory()
    for em in episodic_memories:
        desc = em.get("desc", "").lower()
        tags = em.get("tags", [])

        # Exemple simple de consolidation:
        # Si l'utilisateur mentionne une préférence dans un événement
        if "preference" in tags and "user_input" in tags:
            match_like = re.search(r"j'aime (le|la|les|l')? ?(\w+)", desc)
            if match_like:
                item = match_like.group(2).capitalize()
                if item not in mem["user"]["préférences_média"].get("likes", []):
                    mem["user"]["préférences_média"].setdefault("likes", []).append(item)

        # Si un événement est marqué comme important
        if "important" in tags:
            if {"desc": em["desc"], "time": em["timestamp"]} not in mem["user"]["événements_importants"]:
                mem["user"]["événements_importants"].append({"desc": em["desc"], "time": em["timestamp"]})

        # Si Vera apprend un nouveau concept
        if "vera_curiosity" in tags and "learning_outcome" in em.get("context", {}):
            concept = em["context"]["learning_outcome"].get("concept")
            summary = em["context"]["learning_outcome"].get("summary")
            if concept and summary:
                if concept not in mem["vera"].get("learned_concepts", {}):
                    mem["vera"].setdefault("learned_concepts", {})[concept] = summary

    save_semantic_memory(mem)

def get_memory_context():
    """
    Retourne les faits mémorisés sous forme de texte pour le LLM.
    Priorise les faits personnels critiques en les plaçant à la fin.
    """
    mem = load_semantic_memory()
    
    other_lines = []
    critical_lines = []

    # Catégories et mots-clés critiques pour l'utilisateur
    critical_categories = ["personal_detail", "age", "birthdate", "location", "nationality", "decision", "event"]
    child_keywords = ["enfant", "fils", "fille", "maysara", "jayden", "mila"]

    # --- Traitement des infos utilisateur ---
    user = mem.get("user", {})
    
    # Faits dynamiques de l'utilisateur
    if user.get("dynamic_facts"):
        for fact_obj in user["dynamic_facts"]:
            fact_text = fact_obj.get('fact', '').lower()
            fact_category = fact_obj.get('category', 'général')
            
            is_critical = fact_category in critical_categories or any(keyword in fact_text for keyword in child_keywords)
            
            formatted_line = f"Fait sur l'utilisateur ({fact_category}): {fact_obj.get('fact')}"
            
            if is_critical:
                critical_lines.append(formatted_line)
            else:
                other_lines.append(formatted_line)

    # Faits statiques de l'utilisateur (ajoutés aux 'autres' lignes, sauf si déjà gérés comme critiques)
    if user.get("nom"): other_lines.append(f"Nom de l'utilisateur : {user['nom']}")
    if user.get("animal_préféré"): other_lines.append(f"Animal préféré : {user['animal_préféré']}")
    if user.get("couleurs_préférées"): other_lines.append(f"Couleurs préférées : {', '.join(user['couleurs_préférées'])}")
    if user.get("hobbies"): other_lines.append(f"Hobbies : {', '.join(user['hobbies'])}")
    if user.get("lieux_favoris"): other_lines.append(f"Lieux favoris : {', '.join(user['lieux_favoris'])}")
    if user.get("relations"):
        relations = ", ".join([f"{k}: {v}" for k,v in user['relations'].items()])
        if relations: other_lines.append(f"Relations : {relations}")
    if user.get("goûts_alimentaires"): other_lines.append(f"Goûts alimentaires : {', '.join(user['goûts_alimentaires'])}")
    if user.get("préférences_média"):
        prefs = ", ".join([f"{k}: {', '.join(v)}" for k,v in user['préférences_média'].items()])
        if prefs: other_lines.append(f"Préférences médias : {prefs}")
    if user.get("événements_importants"):
        events = "; ".join([e['desc'] for e in user['événements_importants'][-5:]])
        if events: other_lines.append(f"Événements importants récents : {events}")
    if user.get("inferred_emotion"): other_lines.append(f"Émotion inférée de l'utilisateur : {user['inferred_emotion']}")
    if user.get("likely_goals"): other_lines.append(f"Objectifs probables de l'utilisateur : {', '.join(user['likely_goals'])}")
    if user.get("expertise_level"):
        expertise = ", ".join([f"{k}: {v:.2f}" for k,v in user['expertise_level'].items()])
        if expertise: other_lines.append(f"Niveau d'expertise de l'utilisateur : {expertise}")
    # Location is handled as critical dynamic fact if present in dynamic_facts, otherwise it's a static fact
    if user.get("location") and not any(f"localisation de l'utilisateur : {user['location'].lower()}" in line.lower() for line in critical_lines):
        critical_lines.append(f"Localisation de l'utilisateur : {user['location']}")


    # --- Traitement des infos de Vera ---
    vera = mem.get("vera", {})
    if vera.get("mission"): other_lines.append(f"Mission de Vera : {vera['mission']}")
    if vera.get("identité"): other_lines.append(f"Identité de Vera : {vera['identité']}")
    if vera.get("traits"):
        traits = ", ".join([f"{k}: {v}" for k,v in vera['traits'].items()])
        if traits: other_lines.append(f"Traits de Vera : {traits}")
    if vera.get("learned_concepts"):
        concepts = ", ".join(vera["learned_concepts"].keys())
        if concepts: other_lines.append(f"Concepts appris par Vera : {concepts}")
    if vera.get("dynamic_facts"):
        for fact_obj in vera["dynamic_facts"]:
            other_lines.append(f"Fait sur Vera ({fact_obj.get('category', 'général')}): {fact_obj.get('fact')}")

    # --- Traitement des infos du Monde ---
    world = mem.get("world", {})
    if world.get("dynamic_facts"):
        for fact_obj in world["dynamic_facts"]:
            other_lines.append(f"Fait sur le monde ({fact_obj.get('category', 'général')}): {fact_obj.get('fact')}")

    # Combiner les lignes : les autres d'abord, les critiques à la fin pour les préserver de la troncature.
    final_lines = other_lines + critical_lines
    
    return "\n".join(final_lines)

def update_fact(category, key, value):
    """Met à jour manuellement un fait spécifique."""
    mem = load_semantic_memory()
    if category in mem and key in mem[category]:
        mem[category][key] = value
        save_semantic_memory(mem)
        return True
    return False

def clear_semantic_memory():
    """Réinitialise la mémoire sémantique."""
    save_semantic_memory(DEFAULT_MEMORY.copy())

# --------- Initialisation ---------
init_semantic_memory()



def update_fact(category, key, value):
    """Met à jour manuellement un fait spécifique."""
    mem = load_semantic_memory()
    if category in mem and key in mem[category]:
        mem[category][key] = value
        save_semantic_memory(mem)
        return True
    return False

def clear_semantic_memory():
    """Réinitialise la mémoire sémantique."""
    save_semantic_memory(DEFAULT_MEMORY.copy())

# --------- Initialisation ---------
init_semantic_memory()
