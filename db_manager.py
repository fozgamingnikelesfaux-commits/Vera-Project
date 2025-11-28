import sqlite3
import json
import threading
from pathlib import Path
import logging

from db_config import UNIFIED_DB_PATH, INITIAL_TABLE_SCHEMAS, TABLE_NAMES
from tools.json_utils import datetime_converter # NEW: Import datetime_converter

logger = logging.getLogger(__name__)

class DbManager:
    _instance = None
    _lock = threading.Lock() # Class-level lock for singleton and connection

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DbManager, cls).__new__(cls)
                cls._instance._initialized = False # Use an internal flag for initialization
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.db_path = UNIFIED_DB_PATH
        self.signal_bus = None # To hold the signal bus instance
        self._conn_lock = threading.Lock() # Lock for database connection
        self._local = threading.local() # Thread-local storage for connection

        self._ensure_db_directory()
        self._create_tables_if_not_exist()
        self._initialized = True
        logger.info(f"DbManager initialized. Database path: {self.db_path}")

    def set_signal_bus(self, bus):
        """Injects the signal bus instance for event-driven updates."""
        self.signal_bus = bus
        logger.info("Signal bus has been set for DbManager.")

    def _get_connection(self):
        """Returns a thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            with self._conn_lock: # Ensure only one thread creates connection if needed
                self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self._local.conn.row_factory = sqlite3.Row # Access columns by name
        return self._local.conn

    def _ensure_db_directory(self):
        """Ensures the directory for the database file exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _create_tables_if_not_exist(self):
        """Creates tables based on INITIAL_TABLE_SCHEMAS if they don't already exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        for table_name, schema in INITIAL_TABLE_SCHEMAS.items():
            columns_sql = ", ".join([f"{col_name} {col_type}" for col_name, col_type in schema.items()])
            create_table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_sql})"
            try:
                cursor.execute(create_table_sql)
                logger.debug(f"Table '{table_name}' ensured.")
            except sqlite3.Error as e:
                logger.error(f"Error creating table '{table_name}': {e}")
        conn.commit()

    def insert_document(self, table_name: str, doc_id: str, document: dict, column_name: str = "state_json"):
        """
        Inserts a JSON document into the specified table.
        If a document with the given doc_id already exists, it will be replaced (UPSERT).
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # NEW: Use datetime_converter as the default argument for json.dumps
        document_json = json.dumps(document, default=datetime_converter, ensure_ascii=False)
        
        try:
            # Using INSERT OR REPLACE for UPSERT functionality
            cursor.execute(
                f"INSERT OR REPLACE INTO {table_name} (id, {column_name}) VALUES (?, ?)",
                (doc_id, document_json)
            )
            conn.commit()
            logger.debug(f"Document '{doc_id}' inserted/updated in table '{table_name}'.")
            if self.signal_bus:
                self.signal_bus.db_updated.emit(table_name, doc_id)
        except sqlite3.Error as e:
            logger.error(f"Error inserting/updating document '{doc_id}' in table '{table_name}': {e}")
            conn.rollback()
            raise

    def get_document(self, table_name: str, doc_id: str, column_name: str = "state_json") -> dict | None:
        """Retrieves a JSON document by its ID from the specified table."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                f"SELECT {column_name} FROM {table_name} WHERE id = ?",
                (doc_id,)
            )
            result = cursor.fetchone()
            if result:
                return json.loads(result[0])
            return None
        except sqlite3.Error as e:
            logger.error(f"Error retrieving document '{doc_id}' from table '{table_name}': {e}")
            raise

    def get_all_documents(self, table_name: str, column_name: str = "state_json") -> list[dict]:
        """Retrieves all JSON documents from the specified table."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(f"SELECT {column_name} FROM {table_name}")
            results = cursor.fetchall()
            return [json.loads(row[0]) for row in results]
        except sqlite3.Error as e:
            logger.error(f"Error retrieving all documents from table '{table_name}': {e}")
            raise

    def delete_document(self, table_name: str, doc_id: str):
        """Deletes a document by its ID from the specified table."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                f"DELETE FROM {table_name} WHERE id = ?",
                (doc_id,)
            )
            conn.commit()
            logger.debug(f"Document '{doc_id}' deleted from table '{table_name}'.")
            if self.signal_bus:
                self.signal_bus.db_updated.emit(table_name, doc_id)
        except sqlite3.Error as e:
            logger.error(f"Error deleting document '{doc_id}' from table '{table_name}': {e}")
            conn.rollback()
            raise

# Global instance for easy access throughout the application
db_manager = DbManager()

