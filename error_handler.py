"""Gestionnaire d'erreurs et de validation des données"""
from typing import Dict, Optional
import logging
from datetime import datetime
from pathlib import Path
import json

from config import LOG_DIR
from tools.logger import VeraLogger # Import VeraLogger

# Ensure log directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = VeraLogger("error_handler") # Instantiate logger

class DataValidationError(Exception):
    """Erreur de validation des données"""
    pass

def validate_json_data(data: Dict, schema: Dict) -> bool:
    """
    Valide les données JSON selon un schéma simple
    
    Args:
        data: Données à valider
        schema: Schéma avec types et champs requis
        
    Returns:
        bool: True si valide
        
    Raises:
        DataValidationError: Si données invalides
    """
    try:
        for key, specs in schema.items():
            # Vérifier présence champs requis
            if specs.get("required", True) and key not in data:
                raise DataValidationError(f"Champ requis manquant: {key}")
                
            # Vérifier type si présent
            if key in data and specs.get("type"):
                value = data[key]
                expected_type = specs["type"]
                
                if not isinstance(value, expected_type):
                    raise DataValidationError(
                        f"Type incorrect pour {key}: attendu {expected_type}, reçu {type(value)}"
                    )
                    
            # Vérifier valeurs énumérées
            if key in data and "enum" in specs:
                if data[key] not in specs["enum"]:
                    raise DataValidationError(
                        f"Valeur invalide pour {key}: doit être parmi {specs['enum']}"
                    )
                    
        return True
        
    except Exception as e:
        logger.error(f"Erreur validation: {str(e)}", exc_info=True)
        raise DataValidationError(str(e))

def safe_json_load(file_path: Path) -> Optional[Dict]:
    """
    Charge un fichier JSON de façon sécurisée
    
    Args:
        file_path: Chemin du fichier
        
    Returns:
        Dict or None: Données JSON ou None si erreur
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erreur lecture {file_path}: {e}", exc_info=True)
        return None

def safe_json_save(data: Dict, file_path: Path) -> bool:
    """
    Sauvegarde données JSON de façon sécurisée
    
    Args:
        data: Données à sauvegarder
        file_path: Chemin du fichier
        
    Returns:
        bool: True si succès
    """
    try:
        # Sauvegarder dans fichier temporaire d'abord
        tmp_file = file_path.parent / f"{file_path.stem}_tmp{file_path.suffix}"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        # Remplacer fichier original
        tmp_file.replace(file_path)
        return True
        
    except Exception as e:
        logger.error(f"Erreur sauvegarde {file_path}: {e}", exc_info=True)
        return False

def log_error(error, context: Dict = None):
    """
    Log une erreur avec contexte
    
    Args:
        error: Exception ou message d'erreur à logger
        context: Contexte additionnel
    """
    # Convert string error to Exception if needed
    if isinstance(error, str):
        error = Exception(error)
    ctx = {
        "timestamp": datetime.now().isoformat(),
        "error_type": error.__class__.__name__,
        "error_msg": str(error)
    }
    
    if context:
        ctx.update(context)
        
    logger.error(f"Erreur: {ctx}", exc_info=True)