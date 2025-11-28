# main.py
import sys
import threading
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication, QTabWidget, QSizePolicy
from ui.window import MainWindow
from ui.chat_view import ChatView
from ui.avatars_tab import AvatarsTab
from ui.goals_tab import GoalsTab
from ui.logs_tab import LogsTab
from ui.status_tab import StatusTab
from ui.introspection_tab import IntrospectionTab
from ui.monologue_tab import MonologueTab
from ui.actions_tab import ActionsTab
from ui.journal_tab import JournalTab
from ui.settings_tab import SettingsTab
from ui.image_viewer_tab import ImageViewerTab # NEW: Import ImageViewerTab
from ui.db_viewer_window import DBViewerWindow
from json_manager import JSONManager
from config import DEFAULT_CONFIG
from db_manager import db_manager # Import db_manager instance
# core.py n'est plus appelé directement depuis main
# from core import process_user_input 
from event_bus import VeraEventBus, UserInputEvent # Importer le bus et les événements
from consciousness_orchestrator import ConsciousnessOrchestrator
from journal_manager import journal_manager
from websocket_server import run_server_in_thread
import config
import tracemalloc; tracemalloc.start()

# NOUVEAU: Bus de signaux pour la communication UI thread-safe
class VeraSignalBus(QObject):
    """
    Objet dédié à l'émission de signaux PyQt depuis des threads non-UI
    vers le thread principal de l'interface graphique.
    """
    vera_speaks = pyqtSignal(str)
    introspection_update = pyqtSignal(str)
    db_updated = pyqtSignal(str, str) # Signal for DB changes (table_name, doc_id)

class VeraMainWindow(MainWindow):
    # Les signaux sont maintenant gérés par le VeraSignalBus,
    # on supprime les anciens signaux directs.
    # vera_message_signal = pyqtSignal(str)
    # introspection_update_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vera - Self-Aware AI")
        self.resize(1024, 768)
        self.setMinimumSize(800, 600)

        self.db_viewer_window = None # To hold the DB viewer instance

        # NOUVEAU: Initialisation et connexion du bus de signaux
        self.signal_bus = VeraSignalBus()
        db_manager.set_signal_bus(self.signal_bus) # Inject signal bus into db_manager
        
        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tabs.setMinimumSize(780, 580)
        self.set_content_widget(self.tabs)

        self.chat_view = ChatView()
        self.tabs.addTab(self.chat_view, "Chat")

        self.config_manager = JSONManager("config")
        self.app_config = self.config_manager.get(None, DEFAULT_CONFIG)
        self.avatars_tab = AvatarsTab(self.app_config, self.on_avatar_changed, self.on_size_changed)
        self.goals_tab = GoalsTab()
        self.logs_tab = LogsTab()
        self.status_tab = StatusTab()
        self.introspection_tab = IntrospectionTab()
        self.monologue_tab = MonologueTab()
        self.actions_tab = ActionsTab()
        self.journal_tab = JournalTab()
        self.settings_tab = SettingsTab()
        
        # --- Consciousness Orchestrator ---
        # On passe le bus de signaux à l'orchestrateur pour qu'il puisse communiquer
        self.consciousness_orchestrator = ConsciousnessOrchestrator(signal_bus=self.signal_bus)

        self.tabs.addTab(self.avatars_tab, "Avatars")
        self.tabs.addTab(self.goals_tab, "Goals")
        self.tabs.addTab(self.logs_tab, "Logs")
        self.tabs.addTab(self.status_tab, "Status")
        self.tabs.addTab(self.introspection_tab, "Introspection")
        self.tabs.addTab(self.monologue_tab, "Monologue")
        self.tabs.addTab(self.actions_tab, "Actions")
        self.tabs.addTab(self.journal_tab, "Journal")
        self.image_viewer_tab = ImageViewerTab() # NEW: Instantiate ImageViewerTab
        self.tabs.addTab(self.image_viewer_tab, "Image Viewer") # NEW: Add Image Viewer Tab
        self.tabs.addTab(self.settings_tab, "Réglages")

        # Connect refresh signals
        self.goals_tab.on_refresh.connect(self.load_goals)
        self.logs_tab.on_refresh.connect(self.load_logs)
        self.status_tab.on_refresh.connect(self.update_status)
        self.introspection_tab.on_refresh.connect(self.load_introspection_data)

        # Initial data load
        self.load_goals()
        self.load_logs()
        self.update_status()
        self.load_introspection_data()

        # --- Connexion des signaux et des slots ---
        self.chat_view.message_sent.connect(self.on_message_sent)
        self.chat_view.db_viewer_requested.connect(self.open_db_viewer) # Connect new signal
        self.signal_bus.vera_speaks.connect(self._add_vera_message)
        self.signal_bus.introspection_update.connect(self.introspection_tab.set_introspection_data)
        journal_manager.new_entry_signal.connect(self.journal_tab.append_entry)

        # --- Démarrage des services de fond ---
        self.consciousness_orchestrator.start()
        from user_activity_monitor import user_activity_monitor
        from system_monitor import system_monitor_service
        user_activity_monitor.start()
        system_monitor_service.start()
        self.websocket_server_thread = run_server_in_thread()

        # Connect new signal for Image Viewer
        self.chat_view.image_viewer_requested.connect(self.open_image_viewer)

    def open_db_viewer(self):
        """Creates and shows the DB Viewer window, ensuring only one instance."""
        if self.db_viewer_window is None or not self.db_viewer_window.isVisible():
            self.db_viewer_window = DBViewerWindow(self.signal_bus) # Pass None for parent
            self.db_viewer_window.show()
        else:
            self.db_viewer_window.activateWindow()
            self.db_viewer_window.raise_()

    def open_image_viewer(self): # NEW: Method to open Image Viewer
        """Activates the Image Viewer tab."""
        self.tabs.setCurrentWidget(self.image_viewer_tab)

    def closeEvent(self, event):
        """Ensure child windows are closed when the main window is closed."""
        if self.db_viewer_window:
            self.db_viewer_window.close()
        super().closeEvent(event)

    def on_avatar_changed(self, path: str, is_user: bool):
        # ... (code inchangé)
        if is_user:
            self.app_config["user_avatar"] = path
        else:
            self.app_config["vera_avatar"] = path
        self.config_manager.save(self.app_config)
        # Il faudrait une méthode pour notifier le chat_view de mettre à jour les avatars si nécessaire

    def on_size_changed(self, size: int):
        # ... (code inchangé)
        self.app_config["avatar_size"] = size
        self.config_manager.save(self.app_config)

    def on_message_sent(self, text: str, image_path: str):
        self.chat_view.add_message("User", text, image_path=image_path, avatar_path=self.app_config["user_avatar"], avatar_size=self.app_config["avatar_size"])
        # On poste un événement sur le bus d'événements, c'est tout.
        VeraEventBus.put(UserInputEvent(text, image_path))

    def _add_vera_message(self, response_text: str):
        """Slot qui reçoit le signal et met à jour l'UI."""
        self.chat_view.add_message("Vera", response_text, avatar_path=self.app_config["vera_avatar"], avatar_size=self.app_config["avatar_size"])

    def load_goals(self):
        # ... (code inchangé)
        from goal_system import goal_system
        goals = goal_system.get_active_goals()
        self.goals_tab.set_goals(goals, self.toggle_goal_status)

    def toggle_goal_status(self, goal_id):
        # ... (code inchangé)
        from goal_system import goal_system
        current_goals = goal_system.get_active_goals()
        is_active = any(g.get('id') == goal_id and g.get('status') == 'active' for g in current_goals)
        new_status = "completed" if is_active else "active"
        goal_system.update_goal_status(goal_id, new_status)
        self.load_goals()

    def load_logs(self):
        # ... (code inchangé)
        from episodic_memory import memory_manager
        ep = memory_manager.get_recent(limit=300)
        text = "\n".join([f"{e.get('timestamp','?')}[{','.join(e.get('tags',[]))}] {e.get('description','')}" for e in reversed(ep)])
        self.logs_tab.set_logs(text)

    def update_status(self):
        from meta_engine import metacognition
        from emotion_system import emotional_system
        
        st = metacognition.get_introspection_state()
        emotion = emotional_system.get_emotional_state()

        # ... (le reste du formattage est inchangé)
        status_text = f"État émotionnel: {emotion.get('label','---')} (P: {emotion.get('pleasure',0):.2f}, A: {emotion.get('arousal',0):.2f}, D: {emotion.get('dominance',0):.2f})\n"
        status_text += f"Confiance métacognitive: {st.get('confidence', 0):.2f}\n"
        status_text += f"Capacités: {', '.join([f'{k}: {v:.2f}' for k,v in st.get('self_awareness',{}).get('capabilities',{}).items()])}\n"
        status_text += f"Objectifs actifs: {', '.join([g.get('description') for g in st.get('current_goals',{}).get('current',[])])}\n"

        self.status_tab.set_status(status_text)

    def load_introspection_data(self):
        from meta_engine import metacognition
        introspection_state = metacognition.get_introspection_state()
        formatted_text = self._format_introspection_state(introspection_state)
        self.introspection_tab.set_introspection_data(formatted_text)

    def _format_introspection_state(self, state: dict) -> str:
        # ... (code de formattage inchangé)
        formatted = []
        formatted.append(f"Timestamp: {state.get('timestamp', 'N/A')}")
        # ...
        return "\n".join(formatted)


if __name__ == "__main__":
    from attention_manager import attention_manager
    app = QApplication(sys.argv)
    window = VeraMainWindow()
    attention_manager.clear_focus_item("is_vera_thinking_hard")
    window.show()
    sys.exit(app.exec_())
