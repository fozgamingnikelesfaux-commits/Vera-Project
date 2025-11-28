from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel, QScrollArea
from PyQt5.QtCore import QTimer, Qt
from db_manager import db_manager
from db_config import TABLE_NAMES
from tools.logger import VeraLogger
import json

class DBMonitorTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = VeraLogger("db_monitor_tab")
        self.init_ui()
        self.init_timer()
        self.refresh_display() # Initial refresh

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.refresh_button = QPushButton("Actualiser les données")
        self.refresh_button.clicked.connect(self.refresh_display)
        layout.addWidget(self.refresh_button)

        # Dictionary to hold QTextEdit widgets for each table
        self.display_widgets = {}
        self.add_table_display(layout, "Attention Focus", TABLE_NAMES["attention_focus"], "current_focus")
        self.add_table_display(layout, "Emotions", TABLE_NAMES["emotions"], "current_state")
        self.add_table_display(layout, "Somatic", TABLE_NAMES["somatic"], "current_state")
        self.add_table_display(layout, "Self Narrative", TABLE_NAMES["self_narrative"], "current_narrative")
        self.add_table_display(layout, "Semantic Memory", TABLE_NAMES["semantic_memory"], "current_memory")
        self.add_table_display(layout, "Metacognition", TABLE_NAMES["metacognition"], "current_state")
        self.add_table_display(layout, "Config", TABLE_NAMES["config"], "main_config")
        self.add_table_display(layout, "Personality", TABLE_NAMES["personality"], "vera_personality")


        layout.addStretch(1)

    def add_table_display(self, layout, title, table_name, doc_id):
        header_label = QLabel(f"--- {title} ({table_name}/{doc_id}) ---")
        header_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(header_label)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setLineWrapMode(QTextEdit.NoWrap) # Prevent text wrapping
        text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded) # Enable horizontal scrollbar
        
        # Adjust height based on content or set a fixed/min height
        text_edit.setMinimumHeight(150) # Set a minimum height for visibility
        
        layout.addWidget(text_edit)
        self.display_widgets[table_name + "_" + doc_id] = text_edit # Store with unique key

    def init_timer(self):
        self.timer = QTimer(self)
        self.timer.setInterval(5000) # Refresh every 5 seconds
        self.timer.timeout.connect(self.refresh_display)
        self.timer.start()

    def refresh_display(self):
        self.logger.debug("Refreshing DB Monitor Tab display...")
        # Attention Focus
        attention_focus_data = db_manager.get_document(TABLE_NAMES["attention_focus"], "current_focus")
        self.update_text_edit(TABLE_NAMES["attention_focus"] + "_current_focus", attention_focus_data)

        # Emotions
        emotions_data = db_manager.get_document(TABLE_NAMES["emotions"], "current_state")
        self.update_text_edit(TABLE_NAMES["emotions"] + "_current_state", emotions_data)

        # Somatic
        somatic_data = db_manager.get_document(TABLE_NAMES["somatic"], "current_state")
        self.update_text_edit(TABLE_NAMES["somatic"] + "_current_state", somatic_data)

        # Self Narrative
        self_narrative_data = db_manager.get_document(TABLE_NAMES["self_narrative"], "current_narrative")
        self.update_text_edit(TABLE_NAMES["self_narrative"] + "_current_narrative", self_narrative_data)

        # Semantic Memory (current_memory doc)
        semantic_memory_data = db_manager.get_document(TABLE_NAMES["semantic_memory"], "current_memory")
        self.update_text_edit(TABLE_NAMES["semantic_memory"] + "_current_memory", semantic_memory_data)

        # Metacognition (current_state doc)
        metacognition_data = db_manager.get_document(TABLE_NAMES["metacognition"], "current_state")
        self.update_text_edit(TABLE_NAMES["metacognition"] + "_current_state", metacognition_data)

        # Config (main_config doc)
        config_data = db_manager.get_document(TABLE_NAMES["config"], "main_config")
        self.update_text_edit(TABLE_NAMES["config"] + "_main_config", config_data)
        
        # Personality (vera_personality doc)
        personality_data = db_manager.get_document(TABLE_NAMES["personality"], "vera_personality")
        self.update_text_edit(TABLE_NAMES["personality"] + "_vera_personality", personality_data)


    def update_text_edit(self, key, data):
        widget = self.display_widgets.get(key)
        if widget:
            if data is None:
                widget.setText("Aucune donnée trouvée.")
            else:
                # Convert data to pretty-printed JSON string
                formatted_json = json.dumps(data, indent=2, ensure_ascii=False)
                widget.setText(formatted_json)
        else:
            self.logger.warning(f"Widget non trouvé pour la clé : {key}")
