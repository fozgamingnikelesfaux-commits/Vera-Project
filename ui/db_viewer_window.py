from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QTextEdit, QTabWidget, QGraphicsBlurEffect, QHBoxLayout, QSpacerItem, QSizePolicy, QApplication, QStackedLayout
from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QMouseEvent, QCursor
from db_manager import db_manager
from db_config import TABLE_NAMES
from tools.logger import VeraLogger
import json

class DBViewerWindow(QMainWindow):
    def __init__(self, signal_bus, parent=None):
        super().__init__(parent)
        self.logger = VeraLogger("DBViewerWindow")
        self.setWindowTitle("Visionneuse de la Base de Données de Vera")
        
        self.signal_bus = signal_bus

        # --- Custom Window Frame Logic ---
        self.offset = None
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(800, 900)

        # --- Simplified Layout for Debugging ---
        # The main container is now the central widget
        self.main_container = QWidget()
        self.main_container.setObjectName("background_widget") # Use the same ID for styling
        self.setCentralWidget(self.main_container)

        # The main layout is applied directly to it
        main_content_layout = QVBoxLayout(self.main_container)
        main_content_layout.setContentsMargins(1, 1, 1, 1)
        main_content_layout.setSpacing(0)

        # --- Title Bar ---
        title_bar_layout = QHBoxLayout()
        title_bar_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.minimize_btn = QPushButton("\u2014")
        self.maximize_btn = QPushButton("\U0001F5D6")
        self.close_btn = QPushButton("\u2715")
        for btn in [self.minimize_btn, self.maximize_btn, self.close_btn]:
            btn.setObjectName("window-control-btn")
            btn.setFixedSize(40, 30)
            title_bar_layout.addWidget(btn)
        title_bar_layout.setContentsMargins(0, 5, 15, 0)
        main_content_layout.addLayout(title_bar_layout)

        # Main UI elements
        inner_elements_layout = QVBoxLayout()
        inner_elements_layout.setContentsMargins(10, 0, 10, 10) # Margins around actual content
        self.refresh_button = QPushButton("Actualiser Tout")
        inner_elements_layout.addWidget(self.refresh_button)
        self.tab_widget = QTabWidget()
        inner_elements_layout.addWidget(self.tab_widget)
        main_content_layout.addLayout(inner_elements_layout, 1) # Add inner elements to main content layout with stretch

        # --- Apply Styles & Connections ---
        self.apply_stylesheet()
        
        self.minimize_btn.clicked.connect(self.showMinimized)
        self.maximize_btn.clicked.connect(self.toggle_maximize)
        self.close_btn.clicked.connect(self.close)
        self.refresh_button.clicked.connect(self.refresh_display)

        # --- Populate Tabs ---
        self.display_widgets = {}
        self.init_tabs()
        
        # --- Final Steps ---
        self.connect_signals()
        self.refresh_display()
        self.center_on_screen()


    def init_tabs(self):
        """Creates a separate tab for each module to be displayed."""
        modules_to_display = [
            {"title": "Attention", "table_key": "attention_focus", "doc_id": "current_focus"},
            {"title": "Emotions", "table_key": "emotions", "doc_id": "current_state"},
            {"title": "Somatic", "table_key": "somatic", "doc_id": "current_state"},
            {"title": "Narrative", "table_key": "self_narrative", "doc_id": "current_narrative"},
            {"title": "Semantic", "table_key": "semantic_memory", "doc_id": "current_memory"},
            {"title": "Metacognition", "table_key": "metacognition", "doc_id": "current_state"},
            {"title": "Config", "table_key": "config", "doc_id": "main_config"},
            {"title": "Personality", "table_key": "personality", "doc_id": "vera_personality"},
            {"title": "Homeostasis", "table_key": "homeostasis", "doc_id": "current_state"}, # NEW: Add Homeostasis tab
        ]

        for module in modules_to_display:
            table_name = TABLE_NAMES[module["table_key"]]
            doc_id = module["doc_id"]
            
            tab_page = QWidget()
            tab_layout = QVBoxLayout(tab_page)
            tab_layout.setContentsMargins(5, 5, 5, 5)
            
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setLineWrapMode(QTextEdit.NoWrap)
            text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            tab_layout.addWidget(text_edit)
            
            self.tab_widget.addTab(tab_page, module["title"])
            
            # Store the widget with a unique tuple key for refreshing
            self.display_widgets[(table_name, doc_id)] = text_edit

    def connect_signals(self):
        """Connects the DB update signal to the partial refresh slot."""
        if self.signal_bus:
            self.signal_bus.db_updated.connect(self.refresh_single_tab)

    def refresh_single_tab(self, table_name, doc_id):
        """Refreshes only the specific tab that was updated."""
        self.logger.debug(f"Partial refresh triggered for table: {table_name}, doc_id: {doc_id}")
        widget = self.display_widgets.get((table_name, doc_id))
        if widget:
            data = db_manager.get_document(table_name, doc_id)
            self.update_text_edit(widget, data)
        else:
            self.logger.warning(f"Widget non trouvé pour la clé : ({table_name}, {doc_id})")

    def refresh_display(self):
        """Refreshes all tabs manually."""
        self.logger.debug("Full manual refresh triggered...")
        for (table_name, doc_id), widget in self.display_widgets.items():
            data = db_manager.get_document(table_name, doc_id)
            self.update_text_edit(widget, data)

    def update_text_edit(self, widget: QTextEdit, data: dict):
        """Updates the content of a specific QTextEdit widget."""
        if widget:
            if data is None:
                # This part of the logic will now be harder to implement without the key.
                # For now, just show a generic message.
                widget.setText("Aucune donnée trouvée.")
            else:
                formatted_json = json.dumps(data, indent=2, ensure_ascii=False)
                widget.setText(formatted_json)
        # No else needed as we pass the widget directly


    # --- Custom Window Frame Logic (Copied and Adapted from original MainWindow) ---
    def center_on_screen(self):
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        x = (screen_geometry.width() - self.width()) / 2
        y = (screen_geometry.height() - self.height()) / 2
        self.move(int(x), int(y))
        
    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # Mouse events for dragging
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            # Check if click is in the title bar area
            if event.y() < 40: # Assuming title bar height is around 40px
                self.offset = event.globalPos() - self.pos()
            else:
                self.offset = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.offset is not None and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.offset = None
        super().mouseReleaseEvent(event)

    # Stylesheet (Copied and Adapted from original MainWindow)
    def apply_stylesheet(self):
        stylesheet = """
            #background_widget {
                background-color: rgba(0, 30, 40, 0.7); /* More opaque for blur */
                border-radius: 25px;
                border: 1px solid #00BFFF;
            }
            QPushButton#window-control-btn {
                background-color: transparent;
                color: #00BFFF;
                border: none;
                font-size: 12px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton#window-control-btn:hover {
                background-color: rgba(0, 60, 70, 0.7);
            }
            QPushButton#window-control-btn:pressed {
                background-color: rgba(0, 40, 50, 0.9);
            }
            QLabel, QRadioButton, QCheckBox {
                color: #00BFFF;
                font-size: 14px;
                background-color: transparent;
            }
            QTextEdit, QPlainTextEdit {
                background-color: rgba(0, 20, 30, 0.8);
                color: #00BFFF;
                border: 1px solid #00BFFF;
                border-radius: 10px;
                font-size: 14px;
                padding: 5px;
            }
            QLineEdit {
                background-color: rgba(0, 40, 50, 0.9);
                color: #00BFFF;
                border: 1px solid #00BFFF;
                border-radius: 8px;
               padding: 5px;
                font-size: 14px;
            }
            QPushButton {
                background-color: #00BFFF;
                color: #001E28;
                border: none;
                border-radius: 8px;
                padding: 9px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00FFFF;
            }
            QPushButton:pressed {
                background-color: #009ACD;
            }
            QTabWidget::pane {
                border: none;
                padding: 0px;
                background-color: transparent;
            }
            QTabBar::tab {
                background: transparent;
                color: #00BFFF;
                padding: 12px 20px; /* Reduced padding */
                min-width: 110px;  /* Set a minimum width to ensure text fits */
                border: 1px solid transparent;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QTabBar::tab:selected {
                background: rgba(0, 40, 50, 0.7);
                border: 1px solid #00BFFF;
                border-bottom: 1px solid #00BFFF;
            }
            QTabBar::tab:!selected:hover {
                background: rgba(0, 60, 70, 0.5);
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 12px;
                margin: 16px 0 16px 0;
            }
            QScrollBar::handle:vertical {
                background: #00BFFF;
                min-height: 25px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
            QScrollBar:horizontal {
                border: none;
                background: transparent;
                height: 12px;
                margin: 0 16px 0 16px;
            }
            QScrollBar::handle:horizontal {
                background: #00BFFF;
                min-width: 25px;
                border-radius: 6px;
            }
        """
        self.setStyleSheet(stylesheet)

