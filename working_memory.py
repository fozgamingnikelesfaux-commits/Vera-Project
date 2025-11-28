"""
Gestion de la mémoire de travail avec logging et validation
"""
from datetime import datetime
from typing import Dict, Any, Optional
from tools.logger import VeraLogger

logger = VeraLogger("working_memory")

# Mémoire temporaire pendant la conversation
working_memory: Dict[str, Any] = {}

def update_working_memory(key: str, value: Any) -> bool:
    """
    Mettre à jour la mémoire de travail
    
    Args:
        key: Clé de la donnée
        value: Valeur à stocker
        
    Returns:
        bool: Succès de l'opération
    """
    try:
        working_memory[key] = value
        logger.debug("Mémoire mise à jour",
            key=key,
            type=type(value).__name__)
        return True
    except Exception as e:
        logger.error("Erreur mise à jour mémoire",
            error=str(e),
            key=key)
        return False

def get_working_memory(key: str, default: Any = None) -> Optional[Any]:
    """
    Récupérer une valeur de la mémoire de travail
    
    Args:
        key: Clé à récupérer
        default: Valeur par défaut si non trouvée
        
    Returns:
        Any: Valeur stockée ou default
    """
    value = working_memory.get(key, default)
    logger.debug("Lecture mémoire",
        key=key,
        found=(value is not None))
    return value

def clear_working_memory():
    """Vider la mémoire de travail"""
    global working_memory
    old_size = len(working_memory)
    working_memory = {}
    logger.info("Mémoire vidée",
        old_size=old_size)

def get_memory_status() -> Dict[str, Any]:
    """
    Obtenir état de la mémoire de travail
    
    Returns:
        Dict: Statistiques mémoire
    """
    return {
        "size": len(working_memory),
        "keys": list(working_memory.keys()),
        "types": {k: type(v).__name__ for k,v in working_memory.items()},
        "last_update": datetime.now().isoformat()
    }
