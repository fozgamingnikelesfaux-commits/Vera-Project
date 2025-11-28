import threading
from datetime import timedelta
from tools.logger import VeraLogger
from episodic_memory import memory_manager
from semantic_memory import consolidate_episodic_memory

logger = VeraLogger("memory_consolidation")

class MemoryConsolidator:
    def __init__(self, consolidation_interval_seconds: int = 3600, age_threshold_days: int = 7):
        self.consolidation_interval_seconds = consolidation_interval_seconds
        self.age_threshold_days = age_threshold_days
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_consolidation, daemon=True)

    def start(self):
        logger.info("Démarrage du processus de consolidation de la mémoire.")
        self._thread.start()

    def stop(self):
        logger.info("Arrêt du processus de consolidation de la mémoire.")
        self._stop_event.set()
        self._thread.join()

    def _run_consolidation(self):
        while not self._stop_event.is_set():
            self.consolidate_memories()
            self._stop_event.wait(self.consolidation_interval_seconds)

    def consolidate_memories(self):
        logger.info("Début de la consolidation des mémoires épisodiques.")
        memories_to_consolidate = memory_manager.get_memories_for_consolidation(self.age_threshold_days)
        
        if not memories_to_consolidate:
            logger.info("Aucune mémoire à consolider.")
            return

        logger.info(f"Consolidation de {len(memories_to_consolidate)} mémoires.")
        consolidate_episodic_memory(memories_to_consolidate)

        for mem in memories_to_consolidate:
            memory_manager.mark_as_consolidated(mem["id"])
        
        logger.info("Consolidation des mémoires terminée.")

# Instance globale
memory_consolidator = MemoryConsolidator()
