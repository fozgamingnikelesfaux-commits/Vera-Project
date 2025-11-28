from PyQt5.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QLabel
from PyQt5.QtCore import Qt
from json_manager import JSONManager

class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = JSONManager("config")
        self.init_ui()
        self.load_initial_settings()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # --- Self Evolution Toggle ---
        self.self_evolution_checkbox = QCheckBox("Activer l'auto-évolution (propose_new_tool)")
        self.self_evolution_checkbox.stateChanged.connect(self.on_self_evolution_toggled)
        layout.addWidget(self.self_evolution_checkbox)

        # --- Vision Toggle ---
        self.vision_checkbox = QCheckBox("Activer la vision (analyse des screenshots)")
        self.vision_checkbox.stateChanged.connect(self.on_vision_toggled)
        layout.addWidget(self.vision_checkbox)

        # Spacer to push everything to the top
        layout.addStretch(1)

    def load_initial_settings(self):
        config = self.config_manager.get()
        if config:
            allow_evolution = config.get("allow_self_evolution", False)
            self.self_evolution_checkbox.setChecked(allow_evolution)

            enable_vision_setting = config.get("enable_vision", True) # Default to True
            self.vision_checkbox.setChecked(enable_vision_setting)

    def on_self_evolution_toggled(self, state):
        config = self.config_manager.get()
        if config:
            is_checked = (state == Qt.Checked)
            config["allow_self_evolution"] = is_checked
            self.config_manager.save(config)

    def on_vision_toggled(self, state):
        config = self.config_manager.get()
        if config:
            is_checked = (state == Qt.Checked)
            config["enable_vision"] = is_checked
            self.config_manager.save(config)
