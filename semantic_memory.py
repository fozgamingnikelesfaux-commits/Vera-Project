# semantic_memory.py
import json
import re
from datetime import datetime
from typing import Optional, Dict, List # Added for type hints
from tools.logger import VeraLogger # Import VeraLogger
from db_manager import db_manager # NEW: Import DbManager
from db_config import TABLE_NAMES # NEW: Import TABLE_NAMES

# Use DbManager to centralize semantic memory in the unified DB
_db_table_name = TABLE_NAMES["semantic_memory"]
_db_doc_id = "current_memory"
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

def init_semantic_memory():
    """Assure que la mémoire sémantique existe dans la DB et est à jour avec les clés par défaut."""
    db_manager._create_tables_if_not_exist() # Ensure table is made
    current = db_manager.get_document(_db_table_name, _db_doc_id)
    
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
    
    db_manager.insert_document(_db_table_name, _db_doc_id, merged_memory)

def load_semantic_memory() -> Dict:
    """Loads the semantic memory state from the database."""
    mem = db_manager.get_document(_db_table_name, _db_doc_id)
    if mem is None:
        init_semantic_memory() # Ensure it's initialized if not found
        mem = DEFAULT_MEMORY.copy() # Return default after ensuring it's in DB
    return mem

def save_semantic_memory(data: Dict):
    """Saves the semantic memory state to the database."""
    db_manager.insert_document(_db_table_name, _db_doc_id, data)

# --------- Fonctions principales ---------

def save_user_location(location: str):
    """Saves the user's location."""
    mem = load_semantic_memory()
    mem["user"]["location"] = location
    save_semantic_memory(mem)

def get_user_location() -> Optional[str]:
    """Gets the user's location."""
    mem = load_semantic_memory()
    return mem["user"].get("location")

def remember_fact(text):
    """
    Uses the LLM to analyze a text, identify important facts, and store them dynamically.
    """
    extract_and_store_facts_from_text(text)

def _should_store_fact(fact_text: str) -> bool:
    """
    Uses an LLM call to decide if a given fact is important enough to store in long-term semantic memory.
    """
    from llm_wrapper import send_inference_prompt # Local import

    prompt = f"""
    En tant que filtre d'informations pour la mémoire à long terme de Vera, évalue le fait suivant : "{fact_text}".
    Ce fait est-il suffisamment **important, nouveau, ou pertinent pour l'identité de Vera, la compréhension de l'utilisateur (ses préférences, ses traits personnels) ou du monde** pour être stocké de manière permanente ?
    **Considère les préférences personnelles de l'utilisateur et les traits/préférences de Vera comme importants.**
    Ignore les informations triviales, éphémères, redondantes ou purement conversationnelles.
    Réponds UNIQUEMENT par 'oui' ou 'non'.
    """
    try:
        llm_response = send_inference_prompt(prompt, max_tokens=5)
        decision = llm_response.get("text", "non").strip().lower()
        logger.debug(f"Décision de stockage pour le fait '{fact_text[:50]}...': {decision}")
        return "oui" in decision
    except Exception as e:
        logger.error(f"Erreur lors de la décision de stockage du fait par LLM: {e}", exc_info=True)
        return False # Par défaut, ne pas stocker en cas d'erreur ou d'incertitude


def extract_and_store_facts_from_text(text: str):
    """
    Uses the LLM to analyze a text, identify important facts, and store them dynamically.
    """
    from llm_wrapper import send_inference_prompt # Import here to avoid circular dependency

    prompt = f"""
    En tant que système de mémoire sémantique, analyse le texte suivant et extrait toutes les informations factuelles importantes qui devraient être mémorisées à long terme. Ignore les informations éphémères ou conversationnelles.
    Pour chaque fait, identifie une catégorie pertinente (ex: "physical_attribute", "preference", "personal_detail", "event", "location", "vera_trait", "world_fact", etc.) et le sujet du fait (l'utilisateur, Vera, ou le monde).
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
        logger.info("Début de l'extraction des faits par LLM...") # AJOUT DU LOG
        llm_response = send_inference_prompt(prompt, max_tokens=512)
        logger.info("Extraction des faits par LLM terminée.") # AJOUT DU LOG
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
                # --- NOUVEAU: Filtre metacognitif avant stockage ---
                if not _should_store_fact(fact):
                    logger.info(f"Fait ignoré (jugé non important) : {fact[:50]}...")
                    continue # Passer au fait suivant
                
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
                if item not in mem["user"].get("préférences_média", {}).get("likes", []):
                    mem["user"].setdefault("préférences_média", {}).setdefault("likes", []).append(item)

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

def _get_semantic_keywords(query: str) -> List[str]:
    """
    Uses a fast LLM call to expand the user's query into specific phrases/information items
    to look for in the semantic memory.
    """
    from llm_wrapper import send_inference_prompt
    
    prompt = f"""
Basé sur la question de l'utilisateur, liste toutes les phrases ou éléments d'information spécifiques que je devrais rechercher dans une base de connaissances personnelle pour répondre à cette question.
Pense aux noms propres, aux attributs spécifiques, et aux concepts précis.
Inclue des synonymes et des mots liés.
Réponds UNIQUEMENT avec une liste de phrases/mots-clés en minuscules, séparés par des virgules.

Exemple pour "Qui est Maysara ?": "Maysara, âge de Maysara, relation de Maysara"
Exemple pour "Quelle est ma couleur préférée ?": "couleur préférée de l'utilisateur, préférences de l'utilisateur, goût"
Exemple pour "C'est quoi le nom de mes enfants ?": "nom des enfants de l'utilisateur, Maysara, Jayden, Mila, enfants, famille"
Exemple pour "tu connais mon poid, mon age et ma taille ?": "poids, pèse, kilos, age, ans, né le, taille, mesure, cm"

Question: "{query}"
"""
    try:
        response = send_inference_prompt(prompt, max_tokens=100)
        keywords_str = response.get("text", "")
        keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
        logger.debug(f"Phrases/mots-clés sémantiques extraits par LLM: {keywords}")
        return keywords
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction des phrases/mots-clés sémantiques: {e}", exc_info=True)
        return []

def find_relevant_facts(query: str) -> List[Dict]:
    """
    Finds relevant facts using a hybrid keyword search (both simple and semantic).
    This is Stage 1 of the retrieval process.
    """
    logger.info(f"Étape 1: Recherche par mots-clés pour la requête: '{query}'")
    mem = load_semantic_memory()
    
    all_facts = []
    # Collect all dynamic facts and add a 'source' to them
    user_facts = mem.get("user", {}).get("dynamic_facts", [])
    for fact in user_facts:
        fact['source'] = 'user'
        all_facts.append(fact)
        
    vera_facts = mem.get("vera", {}).get("dynamic_facts", [])
    for fact in vera_facts:
        fact['source'] = 'vera'
        all_facts.append(fact)

    world_facts = mem.get("world", {}).get("dynamic_facts", [])
    for fact in world_facts:
        fact['source'] = 'world'
        all_facts.append(fact)

    if not query:
        logger.debug("Requête vide, retourne les faits les plus récents.")
        return all_facts

    # Get semantic keywords/phrases from LLM
    semantic_phrases = _get_semantic_keywords(query)
    
    # Simple keyword extraction as a fallback and supplement
    stopwords = {"le", "la", "les", "un", "une", "des", "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "de", "du", "et", "est", "a", "à", "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses", "notre", "nos", "votre", "vos", "leur", "leurs", "ce", "cet", "cette", "ces", "qui", "que", "quoi", "où", "quand", "comment", "pourquoi", "quel", "quelle", "quels", "quelles", "être", "avoir", "faire", "dire", "pouvoir", "vouloir", "aller", "voir", "savoir", "falloir", "venir", "prendre", "donner", "comme", "mais", "où", "et", "donc", "or", "ni", "car", "si", "par", "avec", "dans", "sur", "sous", "vers", "avant", "après", "depuis", "pendant", "malgré", "sauf", "selon", "sans", "plus", "moins", "très", "bien", "mal", "aussi", "encore", "jamais", "toujours", "souvent", "jamais", "parfois", "chaque", "tout", "tous", "toute", "toutes", "plusieurs", "certains", "certaines", "quelques", "aucun", "aucune", "chaque", "même", "autre", "autres", "premier", "première", "deuxième", "troisième", "seul", "seule", "seuls", "seules", "grand", "grande", "grands", "grandes", "petit", "petite", "petits", "petites", "jeune", "vieux", "vieille", "bon", "bonne", "bons", "bonnes", "mauvais", "mauvaise", "mauvais", "mauvaises", "nouveau", "nouvelle", "nouveaux", "nouvelles", "vrai", "vraie", "vrais", "vraies", "faux", "fausse", "faux", "fausses", "long", "longue", "longs", "longues", "court", "courte", "courts", "courtes", "rapide", "rapides", "lent", "lente", "lents", "lentes", "facile", "faciles", "difficile", "difficiles", "simple", "simples", "complexe", "complexes", "heureux", "heureuse", "heureux", "heureuses", "triste", "tristes", "content", "contente", "contents", "contentes", "fâché", "fâchée", "fâchés", "fâchées", "calme", "calmes", "agité", "agitée", "agités", "agitées", "curieux", "curieuse", "curieux", "curieuses", "monde", "utilisateur", "vera", "pourrais", "dire", "plait", "genre", "etc", "dis", "moi"}
    simple_keywords = {word for word in re.split(r'\W+', query.lower()) if len(word) > 2 and word not in stopwords}
    
    # Combine both sets of keywords/phrases
    combined_search_terms = list(set(semantic_phrases) | simple_keywords)
    logger.debug(f"Termes de recherche combinés pour la recherche de faits: {combined_search_terms}")

    if not combined_search_terms:
        return all_facts

    scored_facts = []
    for fact_obj in all_facts:
        fact_text = fact_obj.get("fact", "").lower()
        score = 0
        for term in combined_search_terms:
            if term.lower() in fact_text.lower(): # Match whole phrase/keyword case-insensitively
                score += 1
        if score > 0:
            scored_facts.append({"fact": fact_obj, "score": score})
    
    scored_facts.sort(key=lambda x: x["score"], reverse=True)
    
    logger.debug(f"{len(scored_facts)} faits candidats trouvés par mots-clés sémantiques.")
    return [item["fact"] for item in scored_facts]

def rerank_facts_with_llm(facts: List[Dict], query: str) -> List[Dict]:
    """
    Uses a fast LLM call to re-rank a list of facts based on semantic relevance to a query.
    This is Stage 2 of the retrieval process.
    """
    from llm_wrapper import send_inference_prompt
    logger.info(f"Étape 2: Re-classement par LLM pour la requête: '{query}'")

    if not facts:
        return []
    
    # NEW: Limit the number of facts sent for re-ranking to prevent overly large prompts
    MAX_FACTS_FOR_RERANKING = 15 
    limited_facts = facts[:MAX_FACTS_FOR_RERANKING]

    # Format facts for the prompt
    # Use compact JSON format to save tokens
    facts_to_evaluate_str = "\n".join([f"- {json.dumps(fact, ensure_ascii=False, separators=(',', ':'))}" for fact in limited_facts])

    prompt = f"""
Tu es un assistant de tri sémantique intelligent. Ta seule tâche est d'identifier les faits qui sont **utiles ou pertinents** pour formuler une réponse à la question de l'utilisateur, à partir d'une liste.
Sois particulièrement attentif à inclure tout fait qui répond directement à une partie spécifique de la question de l'utilisateur (par exemple, âge, taille, couleur des yeux).

Question de l'utilisateur: "{query}"

Faits à évaluer:
{facts_to_evaluate_str}

Réponds **UNIQUEMENT** avec un tableau JSON contenant les objets JSON complets des faits les plus pertinents. Si aucun fait n'est utile, retourne un tableau JSON vide.
"""
    try:
        llm_response = send_inference_prompt(prompt, max_tokens=1024)
        response_text = llm_response.get("text", "[]")
        
        # Clean the response to get only the JSON array
        # Find the first '[' and the last ']' to extract the JSON array robustly
        start_index = response_text.find('[')
        end_index = response_text.rfind(']')
        
        if start_index != -1 and end_index != -1 and end_index > start_index:
            json_str = response_text[start_index : end_index + 1]
            try:
                reranked_facts = json.loads(json_str)
                logger.debug(f"Faits re-classés par le LLM: {reranked_facts}")
                return reranked_facts
            except json.JSONDecodeError as e:
                logger.warning(f"Erreur de décodage JSON lors du re-classement LLM: {e}. Texte JSON: {json_str[:200]}...")
                return []
        else:
            logger.warning("Le re-classement LLM n'a pas retourné de tableau JSON valide (crochets manquants).")
            return []
    except Exception as e:
        logger.error(f"Erreur lors du re-classement des faits par le LLM: {e}", exc_info=True)
        return [] # Return empty list on error

def get_memory_context(query: str = "") -> str:
    """
    Orchestrates the two-stage retrieval process to get the most relevant facts.
    """
    if not query:
        return ""

    # Stage 1: Keyword search to get a broad list of candidates
    candidate_facts = find_relevant_facts(query)
    
    # Stage 2: LLM re-ranking to get the most semantically relevant facts
    final_facts = rerank_facts_with_llm(candidate_facts, query)
    
    if not final_facts:
        logger.info("Aucun fait sémantique pertinent trouvé après le re-classement.")
        return ""
        
    context_lines = ["\n--- Faits Connus (Mémoire Sémantique) ---"]
    for fact_obj in final_facts:
        subject = fact_obj.get('source', 'Inconnu')
        subject_fr = "l'utilisateur" if subject == "user" else "Vera" if subject == "vera" else "le monde"
        context_lines.append(f"- Fait sur {subject_fr} ({fact_obj.get('category', 'général')}): {fact_obj.get('fact')}")
    context_lines.append("--- Fin des Faits Connus ---")

    return "\n".join(context_lines)

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