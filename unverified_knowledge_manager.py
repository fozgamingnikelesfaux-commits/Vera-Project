# unverified_knowledge_manager.py
import os
import json
import sqlite3
from typing import List, Dict, Optional
from tools.logger import VeraLogger

# --- Configuration ---
UNVERIFIED_KNOWLEDGE_DB_PATH = "data/unverified_knowledge.db"

logger = VeraLogger("unverified_knowledge_manager")

class UnverifiedKnowledgeManager:
    """
    Gère une base de connaissances non-vérifiée en utilisant une base de données SQLite
    avec une table FTS5 pour la recherche plein texte.
    """
    def __init__(self, db_path=UNVERIFIED_KNOWLEDGE_DB_PATH):
        self.db_path = db_path
        self._setup_database()

    def _setup_database(self):
        """
        S'assure que la base de données et la table FTS sont prêtes.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Créer la table principale si elle n'existe pas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS unverified_knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    source TEXT,
                    metadata TEXT
                );
            """)

            # Vérifier si la table FTS existe déjà
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='unverified_knowledge_fts';")
            if cursor.fetchone() is None:
                logger.info("Création de la table FTS 'unverified_knowledge_fts'...")
                cursor.execute("""
                    CREATE VIRTUAL TABLE unverified_knowledge_fts USING fts5(
                        text,
                        source,
                        content='unverified_knowledge',
                        content_rowid='id'
                    );
                """)
                # Remplir la table FTS avec les données existantes
                cursor.execute("INSERT INTO unverified_knowledge_fts(rowid, text, source) SELECT id, text, source FROM unverified_knowledge;")
                conn.commit()
                logger.info("Table FTS 'unverified_knowledge_fts' créée et remplie.")
            else:
                logger.info("La table FTS 'unverified_knowledge_fts' existe déjà.")
            conn.close()
        except Exception as e:
            logger.error(f"Erreur lors de la configuration de la base de données FTS pour unverified_knowledge: {e}", exc_info=True)

    def search(self, query_text: str, k: int = 5) -> List[Dict]:
        """
        Recherche les k faits les plus pertinents pour une requête donnée en utilisant FTS5.
        """
        logger.info(f"Recherche FTS de {k} faits pertinents dans la base non-vérifiée pour: '{query_text}'")
        
        results = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            escaped_query_text = query_text.replace("'", "''")
            
            query = """
                SELECT uk.text, uk.source, uk.metadata, fts.rank
                FROM unverified_knowledge_fts AS fts
                JOIN unverified_knowledge AS uk ON uk.id = fts.rowid
                WHERE fts.text MATCH ?
                ORDER BY fts.rank
                LIMIT ?;
            """
            
            cursor.execute(query, (f'"{escaped_query_text}"', k))
            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                metadata = json.loads(row[2]) if row[2] else {}
                result = {
                    "text": row[0],
                    "source": row[1],
                    "metadata": metadata,
                    "relevance": row[3]
                }
                results.append(result)
            
            logger.info(f"Trouvé {len(results)} résultats dans la base non-vérifiée via FTS.")
        except Exception as e:
            logger.error(f"Erreur lors de la recherche FTS dans SQLite (unverified): {e}", exc_info=True)
            return []

        return results

    def add_entry(self, text: str, source: str, metadata: Optional[Dict] = None) -> bool:
        """
        Ajoute une nouvelle entrée de connaissance non-vérifiée à la base de données.
        """
        logger.info(f"Ajout d'une nouvelle connaissance non-vérifiée. Source: {source}")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            metadata_str = json.dumps(metadata) if metadata else "{}"
            
            cursor.execute(
                "INSERT INTO unverified_knowledge (text, source, metadata) VALUES (?, ?, ?)",
                (text, source, metadata_str)
            )
            
            new_id = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO unverified_knowledge_fts (rowid, text, source) VALUES (?, ?, ?)",
                (new_id, text, source)
            )
            
            conn.commit()
            conn.close()
            
            logger.info(f"Nouvelle connaissance non-vérifiée ajoutée avec succès (ID: {new_id}).")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout d'une connaissance non-vérifiée à SQLite: {e}", exc_info=True)
            return False

# --- Instance Globale ---
unverified_knowledge_manager = UnverifiedKnowledgeManager()
