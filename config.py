"""
Configuration centralisée pour le projet Vera
"""
from pathlib import Path

# Chemins principaux
ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
BACKUP_DIR = ROOT_DIR / "backups"

# Créer les dossiers nécessaires
for directory in [DATA_DIR, LOG_DIR, BACKUP_DIR]:
    directory.mkdir(exist_ok=True)

# Fichiers de données
DATA_FILES = {
    "episodic_memory": DATA_DIR / "episodic_memory.json", # Kept for existing episodic memory DB
    "config": DATA_DIR / "config.json", # Kept for global application settings
}

# Valeurs par défaut
DEFAULT_CONFIG = {
    "emotion_threshold": 0.5,
    "max_memory_events": 100,
    "llm_timeout": 10,
    "llm_server": "http://127.0.0.1:1234",
    "llm_model": "qwen/qwen3-v1-8b"
}

# Configuration du logging
LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "json": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s %(extra)s"
        }
    }
}

# Versions des formats de données
DATA_VERSIONS = {
    "emotions": "2.0",
    "episodic_memory": "2.0",
    "identity": "2.0",
    "semantic_memory": "2.0",
    "metacognition": "2.0"
}