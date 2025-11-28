"""
Moniteur système autonome et événementiel pour Vera.
"""
import psutil
import threading
import time
from typing import Dict, Any
from tools.logger import VeraLogger
from event_bus import VeraEventBus, SystemMonitorEvent, HeartbeatEvent # MODIFIED: Import HeartbeatEvent
import pythoncom # NEW: Import pythoncom for COM initialization in threads

# Tenter d'importer WMI pour la température CPU, mais ne pas bloquer si absent
try:
    import wmi
    WMI_AVAILABLE = True
except ImportError:
    wmi = None
    WMI_AVAILABLE = False

_global_logger = VeraLogger("system_monitor")

class SystemMonitor:
    def __init__(self, check_interval_seconds: int = 15):
        self.logger = VeraLogger("system_monitor.SystemMonitor") # Initialize instance logger
        self.check_interval_seconds = check_interval_seconds
        self._thread = None
        self._stop_event = threading.Event()
        
        # État précédent pour la détection de changements significatifs
        self.last_state = {}
        # Seuils pour déclencher des événements
        self.thresholds = {
            "cpu_usage_percent": 80.0,
            "ram_usage_percent": 85.0,
            "disk_c_free_gb": 15.0, # Seuil bas
        }

    def _get_current_system_usage(self) -> Dict[str, Any]:
        """Récupère les métriques d'utilisation actuelles du système, y compris la température CPU et GPU."""
        cpu_usage = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        ram_usage = ram.percent
        
        disk_c_free_gb = -1
        try:
            disk_c = psutil.disk_usage('C:\\')
            disk_c_free_gb = round(disk_c.free / (1024**3), 2)
        except FileNotFoundError:
            pass # C: drive not found, keep -1

        disk_f_free_gb = -1
        try:
            disk_f = psutil.disk_usage('F:\\')
            disk_f_free_gb = round(disk_f.free / (1024**3), 2)
        except FileNotFoundError:
            pass # F: drive not found, keep -1

        cpu_temp = self._get_cpu_temperature_internal()
        gpu_temp = "N/A"
        gpu_usage = "N/A"

        if WMI_AVAILABLE:
            try:
                # IMPORTANT: WMI queries for GPU metrics are highly system-dependent.
                # The generic queries below may not work or may cause errors on all systems.
                # A more robust solution would involve detecting specific GPU vendors (NVIDIA, AMD)
                # and using their specific WMI namespaces/APIs, or external tools (like nvml, ADL).

                # Pour l'instant, les métriques GPU restent 'N/A' à moins que des requêtes spécifiques
                # et testées ne soient implémentées ici.
                pass 
            except wmi.x_wmi as e:
                self.logger.debug(f"Erreur WMI spécifique lors de la récupération des métriques GPU: {e}")
            except Exception as e:
                self.logger.debug(f"Impossible de récupérer les métriques GPU via WMI: {e}")

        return {
            "cpu_usage_percent": cpu_usage,
            "ram_usage_percent": ram_usage,
            "disk_c_free_gb": disk_c_free_gb,
            "disk_f_free_gb": disk_f_free_gb,
            "cpu_temperature_celsius": cpu_temp,
            "gpu_temperature_celsius": gpu_temp,
            "gpu_usage_percent": gpu_usage,
        }

    def _get_cpu_temperature_internal(self) -> str:
        """Récupère la température CPU via WMI si disponible."""
        if WMI_AVAILABLE:
            try:
                w = wmi.WMI(namespace="root\\wmi")
                temperature_infos = w.MSAcpi_ThermalZoneTemperature()
                if temperature_infos:
                    temp_k = temperature_infos[0].CurrentTemperature 
                    temp_c = round(temp_k / 10 - 273.15, 1)
                    return temp_c
            except wmi.x_wmi as e: # Catch specific WMI exceptions
                pass # Silencieux, l'erreur est connue et non critique
            except Exception as e:
                pass # Silencieux, l'erreur est connue et non critique
        return "N/A"

    def _monitor_loop(self):
        """
        Boucle de fond qui vérifie l'état du système et émet des événements
        uniquement lorsque des changements significatifs ou des seuils sont franchis.
        """
        pythoncom.CoInitialize() # Initialize COM for this thread
        self.logger.info("System monitoring loop started.")
        try:
            while not self._stop_event.is_set():
                current_state = self._get_current_system_usage()
                
                for metric, value in current_state.items():
                    if not isinstance(value, (int, float)): continue

                    last_value = self.last_state.get(metric, 0)
                    threshold = self.thresholds.get(metric)

                    # Par défaut, on considère un changement significatif comme un franchissement de seuil
                    should_emit = False
                    
                    if threshold is not None:
                        # Cas pour les métriques qui augmentent (CPU, RAM)
                        if 'usage' in metric:
                            if last_value < threshold <= value:
                                should_emit = True
                                reason = "crossed threshold upwards"
                        # Cas pour les métriques qui diminuent (espace disque)
                        elif 'free' in metric:
                            if last_value >= threshold > value:
                                should_emit = True
                                reason = "crossed threshold downwards"
                    
                    # Si un événement est justifié, on l'émet
                    if should_emit:
                        self.logger.info(f"System metric '{metric}' {reason}. Emitting event. (Value: {value})")
                        VeraEventBus.put(SystemMonitorEvent(metric=metric, value=value, threshold=threshold))
                
                self.last_state = current_state
                
                # NEW: Emit a heartbeat event to keep the orchestrator loop alive
                VeraEventBus.put(HeartbeatEvent())

                time.sleep(self.check_interval_seconds)
            self.logger.info("System monitoring loop stopped.")
        finally:
            pythoncom.CoUninitialize() # Uninitialize COM when the thread exits

    def start(self):
        """Démarre le thread de surveillance."""
        if self._thread and self._thread.is_alive():
            self.logger.warning("System monitor is already running.")
            return
            
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        self.logger.info("System monitoring started.")

    def stop(self):
        """Arrête la surveillance."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.logger.info("System monitoring stopped.")

# Instance unique pour être importée
system_monitor_service = SystemMonitor()

# --- Fonctions pour l'accès externe (API des outils) ---
def get_system_usage():
    """Récupère l'utilisation actuelle du système."""
    return system_monitor_service._get_current_system_usage()

def get_cpu_temperature():
    """Récupère la température CPU actuelle."""
    return system_monitor_service._get_cpu_temperature_internal()

def get_running_processes(limit=5):
    """Récupère les processus les plus gourmands."""
    try:
        processes = sorted(psutil.process_iter(['name', 'cpu_percent', 'memory_percent']), 
                           key=lambda p: p.info['memory_percent'], 
                           reverse=True)
        return [{"name": p.info['name'], "cpu_percent": p.info['cpu_percent'], "memory_percent": p.info['memory_percent']} for p in processes[:limit]]
    except Exception as e:
        _global_logger.error(f"Erreur lors de la récupération des processus: {e}")
        return []

from llm_wrapper import send_inference_prompt # Import inside the function to avoid circular dependency

def generate_system_health_digest(reason: str = "Périodique") -> Dict[str, Any]:
    """
    Génère un résumé digeste de la santé actuelle du système en utilisant un LLM.
    """
    _global_logger.info(f"Génération d'un résumé de la santé du système (raison: {reason}).")
    
    # 1. Collecte des données brutes
    current_usage = get_system_usage()
    cpu_temp = get_cpu_temperature()
    running_procs = get_running_processes(limit=3) # Top 3 gourmands

    # 2. Préparation du prompt pour le LLM
    prompt_parts = []
    prompt_parts.append("Veuillez générer un résumé concis de la santé du système basé sur les informations suivantes pour Vera.")
    prompt_parts.append("\n--- Données Système ---")
    
    prompt_parts.append(f"Utilisation CPU : {current_usage.get('cpu_usage_percent', 'N/A')}%")
    prompt_parts.append(f"Utilisation RAM : {current_usage.get('ram_usage_percent', 'N/A')}%")
    prompt_parts.append(f"Espace libre Disque C: : {current_usage.get('disk_c_free_gb', 'N/A')} Go")
    if current_usage.get('disk_f_free_gb') != -1: # Only if F: drive exists
        prompt_parts.append(f"Espace libre Disque F: : {current_usage.get('disk_f_free_gb', 'N/A')} Go")
    
    if cpu_temp != "N/A": # Only if CPU temp is available
        prompt_parts.append(f"Température CPU : {cpu_temp}°C")

    if current_usage.get('gpu_temperature_celsius') != "N/A":
        prompt_parts.append(f"Température GPU : {current_usage.get('gpu_temperature_celsius', 'N/A')}°C")
    if current_usage.get('gpu_usage_percent') != "N/A":
        prompt_parts.append(f"Utilisation GPU : {current_usage.get('gpu_usage_percent', 'N/A')}%")
    
    if running_procs:
        prompt_parts.append("\nProcessus les plus gourmands (Top 3):")
        for p in running_procs:
            prompt_parts.append(f"- {p.get('name')} (CPU: {p.get('cpu_percent')}%, RAM: {p.get('memory_percent')}%)")
    prompt_parts.append("--- Fin Données Système ---")
    
    prompt_parts.append("\nEn tant que Vera, décris l'état général du système en une ou deux phrases, en soulignant les points importants ou les anomalies. Mentionne si tout semble aller bien.")

    digest_prompt = "\n".join(prompt_parts)

    # 3. Appel au LLM pour la synthèse
    try:
        llm_response = send_inference_prompt(
            prompt_content=digest_prompt,
            max_tokens=200, # Un résumé concis
            custom_system_prompt=(
                "Tu es un expert en diagnostic système et tu rapportes à Vera de manière concise et claire."
                " Ton rôle est de synthétiser l'état du PC en 1-2 phrases. Sois objectif et factuel."
            )
        )
        digest_text = llm_response.get("text", "Impossible de générer un résumé de la santé du système.")
        _global_logger.info("Résumé de la santé du système généré avec succès.")
        return {"status": "success", "digest": digest_text}
    except Exception as e:
        _global_logger.error(f"Erreur lors de la génération du résumé de la santé du système par LLM: {e}")
        return {"status": "error", "message": f"Erreur lors de la génération du résumé: {e}"}
