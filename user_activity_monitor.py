
import time
import threading
from pynput import mouse, keyboard
from tools.logger import VeraLogger
from event_bus import VeraEventBus, UserActivityEvent

class UserActivityMonitor:
    """
    Surveille l'activité de l'utilisateur et émet des événements sur le VeraEventBus
    lorsque l'utilisateur devient AFK (Away From Keyboard) ou revient.
    """
    def __init__(self, afk_threshold_seconds: int = 180, check_interval_seconds: int = 10):
        self.last_activity_time = time.time()
        self._lock = threading.RLock()
        self.logger = VeraLogger("user_activity_monitor")
        
        self.afk_threshold_seconds = afk_threshold_seconds
        self.check_interval_seconds = check_interval_seconds
        
        # État interne pour éviter les événements dupliqués
        self.is_currently_afk = False
        
        # Threads pour les listeners et la boucle de vérification
        self._mouse_listener_thread = None
        self._keyboard_listener_thread = None
        self._monitor_thread = None
        self._stop_event = threading.Event()

    def _update_last_activity_time(self, *args):
        """Met à jour le timestamp de la dernière activité."""
        with self._lock:
            # Si l'utilisateur était AFK, c'est son retour
            if self.is_currently_afk:
                self.is_currently_afk = False
                self.logger.info("User has returned.")
                VeraEventBus.put(UserActivityEvent(status="returned"))
            self.last_activity_time = time.time()

    def _monitor_loop(self):
        """
        Boucle de fond qui vérifie périodiquement si l'utilisateur est AFK.
        """
        self.logger.info("User activity monitoring loop started.")
        while not self._stop_event.is_set():
            with self._lock:
                idle_time = time.time() - self.last_activity_time
                
                # Vérifier la transition vers l'état AFK
                if not self.is_currently_afk and idle_time > self.afk_threshold_seconds:
                    self.is_currently_afk = True
                    self.logger.info(f"User is now AFK (idle for {idle_time:.0f}s).")
                    VeraEventBus.put(UserActivityEvent(status="afk"))
            
            time.sleep(self.check_interval_seconds)
        self.logger.info("User activity monitoring loop stopped.")

    def start(self):
        """Démarre tous les threads de surveillance."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            self.logger.warning("User activity monitor is already running.")
            return

        self._stop_event.clear()
        
        # Démarrer les listeners pour la souris et le clavier
        self._mouse_listener_thread = mouse.Listener(
            on_move=self._update_last_activity_time, 
            on_click=self._update_last_activity_time, 
            on_scroll=self._update_last_activity_time
        )
        self._mouse_listener_thread.daemon = True
        self._mouse_listener_thread.start()

        self._keyboard_listener_thread = keyboard.Listener(
            on_press=self._update_last_activity_time
        )
        self._keyboard_listener_thread.daemon = True
        self._keyboard_listener_thread.start()
        
        # Démarrer la boucle de vérification de l'état
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        self.logger.info("User activity monitoring started.")

    def stop(self):
        """Arrête la surveillance."""
        self._stop_event.set()
        # Les listeners pynput s'arrêtent d'eux-mêmes car ils sont en mode daemon
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)
        self.logger.info("User activity monitoring stopped.")

# Instance unique pour être importée et démarrée par l'application principale
user_activity_monitor = UserActivityMonitor()
