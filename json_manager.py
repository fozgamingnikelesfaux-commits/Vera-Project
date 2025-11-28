"""
Gestionnaire JSON commun pour tous les modules
"""
import json
import threading
from pathlib import Path
from config import DATA_FILES

# Verrou global pour toutes les opérations sur les fichiers JSON
GLOBAL_JSON_LOCK = threading.RLock()

class JSONManager:
    def __init__(self, file_key):
        """
        Initialise un gestionnaire JSON
        :param file_key: Clé du fichier dans DATA_FILES (config.py)
        """
        self.file_path = DATA_FILES[file_key]
        self.lock = GLOBAL_JSON_LOCK
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Crée le fichier s'il n'existe pas"""
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self.save({})
            
    def load(self):
        """Charge les données du fichier JSON"""
        with self.lock:
            with self.file_path.open('r', encoding='utf-8') as f:
                return json.load(f)
            
    def save(self, data):
        """Sauvegarde les données dans le fichier JSON"""
        with self.lock:
            tmp_file = self.file_path.with_suffix('.tmp')
            with tmp_file.open('w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            tmp_file.replace(self.file_path)
            
    def update(self, key, value):
        """Met à jour une valeur spécifique"""
        data = self.load()
        data[key] = value
        self.save(data)
        
    def get(self, key=None, default=None):
        """Récupère une valeur ou toutes les données"""
        data = self.load()
        if key is None:
            return data
        return data.get(key, default)
        
    def delete(self, key):
        """Supprime une clé"""
        data = self.load()
        if key in data:
            del data[key]
            self.save(data)