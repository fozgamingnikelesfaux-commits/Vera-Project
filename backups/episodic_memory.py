
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import os
from tools.logger import VeraLogger
from error_handler import log_error
from contextlib import contextmanager # Import contextmanager

logger = VeraLogger("memory_sqlite")

class MemoryManager:
    def __init__(self, db_path="data/episodic_memory.db"):
        self.db_path = db_path
        self._initialize_database()

    @contextmanager # Decorator to make this a context manager
    def _get_connection(self):
        """Crée et retourne une connexion à la base de données, gérée par un contexte."""
        # Crée le répertoire 'data' s'il n'existe pas
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = None # Initialize conn to None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
            yield conn # Yield the connection
        finally:
            if conn:
                conn.close() # Ensure connection is closed

    def _initialize_database(self):
        """Crée la table des épisodes si elle n'existe pas."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS episodes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        description TEXT NOT NULL,
                        tags TEXT,
                        importance REAL,
                        context TEXT
                    )
                """)
                conn.commit()
            logger.info("Base de données de la mémoire épisodique initialisée.")
        except Exception as e:
            log_error("db_init", f"Erreur lors de l'initialisation de la base de données: {e}")
            raise

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convertit une ligne de la base de données en dictionnaire, en désérialisant les champs JSON."""
        if not row:
            return {}
        event = dict(row)
        if event.get('tags'):
            event['tags'] = json.loads(event['tags'])
        if event.get('context'):
            event['context'] = json.loads(event['context'])
        return event

    def ajouter_evenement(self, desc: str, tags: Optional[List[str]] = None,
                         importance: float = 1.0,
                         context: Optional[Dict[str, Any]] = None,
                         emotion: Optional[Dict[str, Any]] = None,
                         intention: Optional[str] = None,
                         attention_focus: Optional[str] = None) -> Dict[str, Any]:
        """Ajoute un nouvel événement dans la base de données, enrichi de contexte autonoétique."""
        # Prépare le contexte
        full_context = context or {}
        if emotion:
            full_context['emotion'] = emotion
        if intention:
            full_context['intention'] = intention
        if attention_focus:
            full_context['attention_focus'] = attention_focus

        tags_json = json.dumps(tags or [])
        context_json = json.dumps(full_context)
        timestamp = datetime.now().isoformat()

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO episodes (timestamp, description, tags, importance, context)
                    VALUES (?, ?, ?, ?, ?)
                """, (timestamp, desc, tags_json, importance, context_json))
                conn.commit()
                event_id = cursor.lastrowid
            
            logger.info("Événement ajouté à la mémoire SQLite.", event_id=event_id, tags=tags, context_keys=list(full_context.keys()))
            
            return {
                "id": event_id,
                "timestamp": timestamp,
                "description": desc,
                "tags": tags or [],
                "importance": importance,
                "context": full_context
            }
        except Exception as e:
            log_error("db_add_event", f"Erreur lors de l'ajout d'un événement à la DB: {e}")
            return {}

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retourne les N événements les plus récents."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM episodes ORDER BY timestamp DESC LIMIT ?", (limit,))
                rows = cursor.fetchall()
                return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            log_error("db_get_recent", f"Erreur lors de la récupération des événements récents: {e}")
            return []

    def get_pivotal_memories(self, recent_limit: int = 10, pivotal_limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retourne une combinaison de souvenirs récents et de souvenirs "pivotaux"
        basés sur l'intensité émotionnelle (Arousal).
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 1. Récupérer les souvenirs les plus récents
                cursor.execute("SELECT * FROM episodes ORDER BY timestamp DESC LIMIT ?", (recent_limit,))
                recent_rows = cursor.fetchall()

                # 2. Récupérer les souvenirs les plus intenses (Arousal élevé)
                # Utilise json_extract pour lire dans le champ JSON.
                # ABS() est utilisé car une intensité peut être forte en négatif comme en positif.
                cursor.execute("""
                    SELECT * FROM episodes
                    WHERE json_valid(context) AND json_extract(context, '$.emotion.arousal') IS NOT NULL
                    ORDER BY ABS(json_extract(context, '$.emotion.arousal')) DESC
                    LIMIT ?
                """, (pivotal_limit,))
                pivotal_rows = cursor.fetchall()

                # 3. Combiner et dédoublonner les résultats
                all_memories = {}
                for row in recent_rows + pivotal_rows:
                    # La clé du dictionnaire est l'ID, ce qui garantit l'unicité
                    all_memories[row['id']] = self._row_to_dict(row)
                
                # Trier la liste finale par timestamp pour la cohérence narrative
                sorted_memories = sorted(all_memories.values(), key=lambda m: m['timestamp'])
                
                return sorted_memories
        except Exception as e:
            # Si json_extract n'est pas supporté, on retourne juste les souvenirs récents
            if "no such function: json_extract" in str(e):
                logger.warning("La fonction json_extract n'est pas supportée par cette version de SQLite. Retour aux souvenirs récents.")
                return self.get_recent(limit=recent_limit + pivotal_limit)
            
            log_error("db_get_pivotal", f"Erreur lors de la récupération des souvenirs pivotaux: {e}")
            return []

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Recherche simple dans les descriptions."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # La recherche par `LIKE` est simple mais peut être lente sur de très grands datasets.
                # Pour une meilleure performance, une FTS (Full-Text Search) serait nécessaire.
                cursor.execute("""
                    SELECT * FROM episodes 
                    WHERE description LIKE ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (f'%{query}%', limit))
                rows = cursor.fetchall()
                return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            log_error("db_search", f"Erreur lors de la recherche en mémoire: {e}")
            return []

    def get_memories_by_tag(self, tag: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Récupère les mémoires contenant un tag spécifique."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # `LIKE` est utilisé pour trouver le tag dans la chaîne JSON.
                cursor.execute("""
                    SELECT * FROM episodes 
                    WHERE tags LIKE ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (f'%"{tag}"%', limit))
                rows = cursor.fetchall()
                return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            log_error("db_get_by_tag", f"Erreur lors de la récupération par tag: {e}")
            return []

    def get_memories_for_consolidation(self, age_threshold_days: int = 7, limit: int = 20) -> List[Dict[str, Any]]:
        """Récupère les mémoires plus anciennes qui n'ont pas été consolidées."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Calcule la date seuil
                threshold_date = (datetime.now() - timedelta(days=age_threshold_days)).isoformat()
                cursor.execute("""
                    SELECT * FROM episodes
                    WHERE timestamp < ? AND (tags IS NULL OR tags NOT LIKE '%"consolidated"%')
                    ORDER BY timestamp ASC
                    LIMIT ?
                """, (threshold_date, limit))
                rows = cursor.fetchall()
                return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            log_error("db_consolidation", context={"message": f"Erreur lors de la rÚcupÚration pour consolidation: {e}"})
            return []

    def mark_as_consolidated(self, memory_id: int):
        """Marque une mémoire comme consolidée en ajoutant le tag."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT tags FROM episodes WHERE id = ?", (memory_id,))
                row = cursor.fetchone()
                if not row:
                    return

                tags = json.loads(row['tags']) if row['tags'] else []
                if "consolidated" not in tags:
                    tags.append("consolidated")
                    tags_json = json.dumps(tags)
                    cursor.execute("UPDATE episodes SET tags = ? WHERE id = ?", (tags_json, memory_id))
                    conn.commit()
                    logger.info("Mémoire marquée comme consolidée", event_id=memory_id)
        except Exception as e:
            log_error("db_mark_consolidated", f"Erreur lors du marquage de consolidation: {e}")

# Instance globale du gestionnaire de mémoire
memory_manager = MemoryManager()

# --- Fonctions de compatibilité pour l'ancien API ---
# Ces fonctions permettent de ne pas avoir à tout réécrire dans les autres fichiers tout de suite.
# AVERTISSEMENT : `charger_epmem` est supprimée car elle est la cause du problème de mémoire.

def ajouter_evenement(desc, tags=None, importance=1.0, context=None, emotion=None, intention=None, attention_focus=None):
    return memory_manager.ajouter_evenement(desc, tags=tags, importance=importance, context=context, emotion=emotion, intention=intention, attention_focus=attention_focus)

def recuperer_memoire(limit=None, include_post_echo: bool = False):
    # L'argument `include_post_echo` n'est plus géré de la même manière,
    # mais on peut le simuler si nécessaire. Pour l'instant, on l'ignore.
    return memory_manager.get_recent(limit or 50)

# La fonction `charger_epmem` est intentionnellement omise.
# Tout code l'utilisant doit être mis à jour pour utiliser `memory_manager.get_recent()`
# ou une autre fonction de recherche spécifique.
