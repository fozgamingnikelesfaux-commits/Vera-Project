# external_knowledge_base.py
import os
import json
import sqlite3
from typing import List, Dict, Optional
from tools.logger import VeraLogger

# --- Configuration ---
KNOWLEDGE_MAP_DB_PATH = "data/knowledge_map.db"

logger = VeraLogger("external_knowledge_base")

class ExternalKnowledgeBase:
    """
    Gère une base de connaissances externe en lecture seule en utilisant une base de données SQLite
    avec une table FTS5 pour la recherche plein texte.
    """
    def __init__(self, db_path):
        self.db_path = db_path
        self._setup_database()

    def _setup_database(self):
        """
        S'assure que la base de données et la table FTS sont prêtes.
        """
        if not os.path.exists(self.db_path):
            logger.error(f"La base de données '{self.db_path}' n'existe pas. La recherche sera impossible.")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Vérifier si la table FTS existe déjà
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_fts';")
            if cursor.fetchone() is None:
                logger.info("Création de la table FTS 'knowledge_fts'...")
                # Créer la table FTS en se basant sur la table 'knowledge'
                cursor.execute("""
                    CREATE VIRTUAL TABLE knowledge_fts USING fts5(
                        text,
                        source,
                        content='knowledge',
                        content_rowid='id'
                    );
                """)
                # Remplir la table FTS
                cursor.execute("INSERT INTO knowledge_fts(rowid, text, source) SELECT id, text, source FROM knowledge;")
                conn.commit()
                logger.info("Table FTS 'knowledge_fts' créée et remplie.")
            else:
                logger.info("La table FTS 'knowledge_fts' existe déjà.")
            conn.close()
        except Exception as e:
            logger.error(f"Erreur lors de la configuration de la base de données FTS: {e}", exc_info=True)

    def search(self, query_text: str, k: int = 5) -> List[Dict]:
        """
        Recherche les k faits les plus pertinents pour une requête donnée en utilisant FTS5.
        """
        if not os.path.exists(self.db_path):
            logger.error(f"Recherche annulée: la base de données '{self.db_path}' est manquante.")
            return []

        logger.info(f"Recherche FTS de {k} faits pertinents dans la base externe pour: '{query_text}'")
        
        results = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Échapper les apostrophes simples pour éviter les erreurs de syntaxe FTS5
            escaped_query_text = query_text.replace("'", "''")
            
            # Utiliser une requête FTS5. L'ordre est géré par le rang de pertinence de FTS5.
            query = """
                SELECT k.text, k.source, k.metadata, fts.rank
                FROM knowledge_fts AS fts
                JOIN knowledge AS k ON k.id = fts.rowid
                WHERE fts.text MATCH ?
                ORDER BY fts.rank
                LIMIT ?;
            """
            
            cursor.execute(query, (f'"{escaped_query_text}"', k))
            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                metadata = json.loads(row[2])
                result = {
                    "text": row[0],
                    "source": row[1],
                    "metadata": metadata,
                    "relevance": row[3]  # Utiliser le rang FTS comme score de pertinence
                }
                results.append(result)
            
            logger.info(f"Trouvé {len(results)} résultats dans la base externe via FTS.")
        except Exception as e:
            logger.error(f"Erreur lors de la recherche FTS dans SQLite: {e}", exc_info=True)
            return []

        return results

    def add_entry(self, text: str, source: str, metadata: Optional[Dict] = None) -> bool:
        """
        Ajoute une nouvelle entrée de connaissance à la base de données.
        """
        if not os.path.exists(self.db_path):
            logger.error(f"Ajout annulé: la base de données '{self.db_path}' est manquante.")
            return False

        logger.info(f"Ajout d'une nouvelle connaissance à la base de données. Source: {source}")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Sérialiser les métadonnées en JSON
            metadata_str = json.dumps(metadata) if metadata else "{}"
            
            # Insérer dans la table principale 'knowledge'
            cursor.execute(
                "INSERT INTO knowledge (text, source, metadata) VALUES (?, ?, ?)",
                (text, source, metadata_str)
            )
            
            # Récupérer l'ID de la nouvelle entrée
            new_id = cursor.lastrowid
            
            # Insérer dans la table de recherche FTS
            cursor.execute(
                "INSERT INTO knowledge_fts (rowid, text, source) VALUES (?, ?, ?)",
                (new_id, text, source)
            )
            
            conn.commit()
            conn.close()
            
            logger.info(f"Nouvelle connaissance ajoutée avec succès (ID: {new_id}).")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout d'une connaissance à SQLite: {e}", exc_info=True)
            return False

# --- Instance Globale ---
external_knowledge_base = ExternalKnowledgeBase(KNOWLEDGE_MAP_DB_PATH)

def get_external_context(query_text: str, k: int = 5) -> str:
    """
    Recherche les faits pertinents et les formate pour le contexte du LLM.
    """
    logger.info(f"Construction du contexte externe pour la requête: '{query_text}'")
    search_results = external_knowledge_base.search(query_text, k=k)
    
    if not search_results:
        return "Aucun fait pertinent trouvé dans la base de connaissances externe."

    # Pas de filtrage par distance, FTS5 a déjà trié par pertinence.
    if not search_results:
        return None

    context_lines = ["Voici des informations pertinentes extraites de ma banque de données externe :"]
    for res in search_results:
        context_lines.append(f"- {res['text']} (Source: {res['source']})")
        
    return "\n".join(context_lines)