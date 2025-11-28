from pathlib import Path

# Base directory for data files (same as config.py)
ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"

# Unified SQLite Database Path
UNIFIED_DB_PATH = DATA_DIR / "vera_unified_state.db"

# Table Names (Collections in a document-like sense)
# These will be the primary keys/identifiers for state objects within the DB
TABLE_NAMES = {
    "emotions": "emotions",
    "episodic_memory_events": "episodic_memory_events", # This is for a future migration if needed, currently separate
    "external_knowledge": "external_knowledge", # Also currently separate
    "identity": "identity",
    "semantic_memory": "semantic_memory",
    "metacognition": "metacognition",
    "config": "config",
    "goals": "goals",
    "reminders": "reminders",
    "personality": "personality",
    "learned_knowledge": "learned_knowledge", # For verified knowledge
    "unverified_knowledge": "unverified_knowledge", # For new, unverified knowledge
    "web_cache": "web_cache",
    "attention_focus": "attention_focus",
    "self_narrative": "self_narrative",
    "accomplishments": "accomplishments",
    "somatic": "somatic",
    "homeostasis": "homeostasis",
    "user_models": "user_models", # From metacognition's world_model
    "beliefs_self_model": "beliefs_self_model", # From metacognition's beliefs
    "thoughts": "thoughts", # From internal_monologue
    "action_log": "action_log" # From action_dispatcher (if migrated)
}

# Initial schema for tables that will store single JSON documents
# The key 'id' will be used to store a unique identifier for single-record tables
# For tables storing single large JSON objects, 'id' can be a fixed string like 'current_state'
# For tables storing multiple records (like goals, thoughts), 'id' will be unique for each record
INITIAL_TABLE_SCHEMAS = {
    TABLE_NAMES["emotions"]: {
        "id": "TEXT PRIMARY KEY",
        "state_json": "TEXT" # Stores the JSON string of the emotion state
    },
    TABLE_NAMES["identity"]: {
        "id": "TEXT PRIMARY KEY",
        "state_json": "TEXT"
    },
    TABLE_NAMES["semantic_memory"]: {
        "id": "TEXT PRIMARY KEY",
        "state_json": "TEXT"
    },
    TABLE_NAMES["metacognition"]: {
        "id": "TEXT PRIMARY KEY",
        "state_json": "TEXT"
    },
    TABLE_NAMES["config"]: {
        "id": "TEXT PRIMARY KEY",
        "state_json": "TEXT"
    },
    TABLE_NAMES["personality"]: {
        "id": "TEXT PRIMARY KEY",
        "state_json": "TEXT"
    },
    TABLE_NAMES["attention_focus"]: {
        "id": "TEXT PRIMARY KEY",
        "state_json": "TEXT" # Stores the JSON string of the entire attention focus dict
    },
    TABLE_NAMES["self_narrative"]: {
        "id": "TEXT PRIMARY KEY",
        "state_json": "TEXT"
    },
    TABLE_NAMES["accomplishments"]: {
        "id": "TEXT PRIMARY KEY",
        "state_json": "TEXT"
    },
    TABLE_NAMES["somatic"]: {
        "id": "TEXT PRIMARY KEY",
        "state_json": "TEXT"
    },
    TABLE_NAMES["homeostasis"]: {
        "id": "TEXT PRIMARY KEY",
        "state_json": "TEXT"
    },
    TABLE_NAMES["web_cache"]: { # NEW: Add web_cache table schema
        "id": "TEXT PRIMARY KEY", # Assuming web cache stores a single large JSON object
        "cache_json": "TEXT"
    },
    # Tables that will store multiple records (like goals, reminders, unverified_knowledge)
    TABLE_NAMES["goals"]: {
        "id": "TEXT PRIMARY KEY", # Goal ID (UUID or unique string)
        "goal_json": "TEXT" # Stores the JSON string of a single goal object
    },
    TABLE_NAMES["reminders"]: {
        "id": "TEXT PRIMARY KEY", # Reminder ID
        "reminder_json": "TEXT" # Stores the JSON string of a single reminder object
    },
    TABLE_NAMES["unverified_knowledge"]: {
        "id": "TEXT PRIMARY KEY", # Topic ID or unique identifier
        "knowledge_json": "TEXT" # Stores the JSON string of an unverified knowledge entry
    },
    TABLE_NAMES["user_models"]: { # To store individual user models from metacognition.world_model
        "id": "TEXT PRIMARY KEY", # User ID
        "model_json": "TEXT" # Stores the JSON string of a single user model
    },
    TABLE_NAMES["beliefs_self_model"]: { # To store beliefs.self_model from metacognition
        "id": "TEXT PRIMARY KEY", # 'self_model'
        "model_json": "TEXT"
    },
    TABLE_NAMES["thoughts"]: { # To store internal monologue thoughts
        "id": "TEXT PRIMARY KEY", # Timestamp or UUID
        "thought_json": "TEXT"
    },
    TABLE_NAMES["action_log"]: { # To store actions
        "id": "TEXT PRIMARY KEY", # Timestamp or UUID
        "action_json": "TEXT"
    }
}
