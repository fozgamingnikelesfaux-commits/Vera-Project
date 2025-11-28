# migrate_to_unified_db.py
import json
import logging
from pathlib import Path
from uuid import uuid4

# Assuming these are in the same directory or properly imported
from db_config import DATA_DIR, TABLE_NAMES
from db_manager import db_manager # Ensure db_manager is initialized on import

# Configure logging for the migration script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_single_json_file(file_path: Path, table_name: str, doc_id: str, column_name: str = "state_json"):
    """Migrates a single JSON file (expected to contain one dict) to the unified DB."""
    if not file_path.exists():
        logger.info(f"Old JSON file not found: {file_path}. Skipping migration for {table_name}.")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning(f"File {file_path} does not contain a single dictionary. Skipping for {table_name}.")
            return

        db_manager.insert_document(table_name, doc_id, data, column_name)
        logger.info(f"Successfully migrated {file_path} to table '{table_name}' with ID '{doc_id}'.")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}. Skipping migration for {table_name}.")
    except Exception as e:
        logger.error(f"An unexpected error occurred migrating {file_path}: {e}.")

def migrate_list_json_file(file_path: Path, table_name: str, id_key: str = "id", column_name: str = "state_json"):
    """
    Migrates a JSON file (expected to contain a list of dicts) to the unified DB,
    inserting each item as a separate document.
    """
    if not file_path.exists():
        logger.info(f"Old JSON file not found: {file_path}. Skipping migration for {table_name}.")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data_list = json.load(f)
        if not isinstance(data_list, list):
            logger.warning(f"File {file_path} does not contain a list. Skipping for {table_name}.")
            return

        for item in data_list:
            if not isinstance(item, dict):
                logger.warning(f"Item in {file_path} is not a dictionary. Skipping item.")
                continue

            # Ensure item has an ID. If not, generate a UUID.
            if id_key not in item or not item[id_key]:
                item[id_key] = str(uuid4())
                logger.warning(f"Generated UUID for item in {file_path} as it was missing or empty.")
            
            doc_id = str(item[id_key]) # Ensure ID is string for DB

            db_manager.insert_document(table_name, doc_id, item, column_name)
        logger.info(f"Successfully migrated {len(data_list)} items from {file_path} to table '{table_name}'.")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}. Skipping migration for {table_name}.")
    except Exception as e:
        logger.error(f"An unexpected error occurred migrating {file_path}: {e}.")


def migrate_nested_list_json_file(file_path: Path, table_name: str, nested_keys: list[str], id_key: str = "id", column_name: str = "state_json"):
    """
    Migrates a JSON file (expected to contain a dict with nested lists of dicts)
    to the unified DB, inserting each item from nested lists as a separate document.
    """
    if not file_path.exists():
        logger.info(f"Old JSON file not found: {file_path}. Skipping migration for {table_name}.")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data_dict = json.load(f)
        if not isinstance(data_dict, dict):
            logger.warning(f"File {file_path} does not contain a dictionary. Skipping for {table_name}.")
            return

        total_items_migrated = 0
        for key in nested_keys:
            if key in data_dict and isinstance(data_dict[key], list):
                for item in data_dict[key]:
                    if not isinstance(item, dict):
                        logger.warning(f"Item in nested list '{key}' of {file_path} is not a dictionary. Skipping item.")
                        continue

                    if id_key not in item or not item[id_key]:
                        item[id_key] = str(uuid4())
                        logger.warning(f"Generated UUID for item in nested list '{key}' of {file_path} as it was missing or empty.")
                    
                    doc_id = str(item[id_key]) # Ensure ID is string for DB

                    db_manager.insert_document(table_name, doc_id, item, column_name)
                    total_items_migrated += 1
            else:
                logger.debug(f"Nested key '{key}' not found or not a list in {file_path}.")

        logger.info(f"Successfully migrated {total_items_migrated} items from {file_path} (nested lists) to table '{table_name}'.")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}. Skipping migration for {table_name}.")
    except Exception as e:
        logger.error(f"An unexpected error occurred migrating {file_path}: {e}.")

def run_migration():
    logger.info("Starting migration to unified SQLite database...")

    # =========================================================
    # Files expected to contain a single JSON object (dict)
    # =========================================================
    single_object_migrations = [
        ("emotions.json", TABLE_NAMES["emotions"], "current_state"),
        ("identity.json", TABLE_NAMES["identity"], "vera_identity"),
        ("semantic_memory.json", TABLE_NAMES["semantic_memory"], "current_memory"),
        ("metacognition.json", TABLE_NAMES["metacognition"], "current_state"),
        ("personality.json", TABLE_NAMES["personality"], "vera_personality"),
        ("attention_focus.json", TABLE_NAMES["attention_focus"], "current_focus"),
        ("self_narrative.json", TABLE_NAMES["self_narrative"], "current_narrative"),
        ("somatic.json", TABLE_NAMES["somatic"], "current_state"),
        ("homeostasis.json", TABLE_NAMES["homeostasis"], "current_state"),
        ("web_cache.json", TABLE_NAMES["web_cache"], "cache_data", "cache_json") # Adjusted column_name for web_cache
    ]

    for filename, table_name, doc_id, *col_name in single_object_migrations:
        column_name_to_use = col_name[0] if col_name else "state_json"
        migrate_single_json_file(DATA_DIR / filename, table_name, doc_id, column_name=column_name_to_use)

    # =========================================================
    # Files expected to contain a list of JSON objects (dicts)
    # These were previously causing issues. Now specific handling.
    # =========================================================
    # Special handling for goals.json (contains "active", "completed", "archived" keys)
    migrate_nested_list_json_file(DATA_DIR / "goals.json", TABLE_NAMES["goals"], ["active", "completed", "archived"], id_key="id", column_name="goal_json")
    
    # Assuming reminders.json and accomplishments.json might have similar structures if they were lists
    # If they are just a top-level list, the old migrate_list_json_file is still appropriate.
    # Let's read them first to confirm. For now, try with nested_list migration assuming they might be similar to goals.
    migrate_nested_list_json_file(DATA_DIR / "reminders.json", TABLE_NAMES["reminders"], ["reminders"], id_key="id", column_name="reminder_json") # Assuming "reminders" as a top-level key
    migrate_nested_list_json_file(DATA_DIR / "accomplishments.json", TABLE_NAMES["accomplishments"], ["accomplishments"], id_key="id", column_name="state_json") # Assuming "accomplishments" as a top-level key

    # Unverified knowledge remains a top-level list
    migrate_list_json_file(DATA_DIR / "unverified_knowledge.json", TABLE_NAMES["unverified_knowledge"], id_key="id", column_name="knowledge_json")
    
    # =========================================================
    # Special case: Config.json contains application-wide settings
    # As discussed, config.json is NOT migrated to unified DB.
    # It will remain a standalone file for application settings.
    # =========================================================

    logger.info("Migration process completed.")
    logger.warning("Please ensure to backup your old 'data/' directory before running this script in production.")

if __name__ == "__main__":
    run_migration()

