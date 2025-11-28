from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QListView, QSizePolicy, QFrame, QFileDialog, QLabel
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPixmap
from typing import Optional

from .message_model import MessageListModel, ChatMessage
from .message_delegate import MessageDelegate
from .virtual_list import VirtualListView

class ChatView(QWidget):
    message_sent = pyqtSignal(str, str)  # (text, image_path)
    db_viewer_requested = pyqtSignal()
    image_viewer_requested = pyqtSignal() # NEW: Signal for Image Viewer

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_image_path = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.message_list_view = VirtualListView()
        self.message_model = MessageListModel()
        self.message_list_view.setModel(self.message_model)
        self.message_list_view.setItemDelegate(MessageDelegate(self.message_list_view))
        main_layout.addWidget(self.message_list_view)

        # --- Input Area ---
        input_container = QFrame()
        input_container.setObjectName("input_container")
        input_container.setContentsMargins(5, 5, 5, 5)
        input_layout = QVBoxLayout(input_container)
        input_layout.setSpacing(5)

        # Image preview
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedSize(100, 100)
        self.preview_label.setVisible(False) # Hidden by default
        input_layout.addWidget(self.preview_label)

        # Text input and buttons
        bottom_layout = QHBoxLayout()
        self.input_text_edit = QTextEdit()
        self.input_text_edit.setPlaceholderText("Tapez votre message ici...")
        self.input_text_edit.setFixedHeight(40)
        self.input_text_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bottom_layout.addWidget(self.input_text_edit)

        self.image_button = QPushButton("Image")
        self.image_button.setFixedWidth(80)
        self.image_button.setFixedHeight(40)
        self.image_button.clicked.connect(self.open_image_dialog)
        bottom_layout.addWidget(self.image_button)

        self.send_button = QPushButton("Envoyer")
        self.send_button.setFixedWidth(80)
        self.send_button.setFixedHeight(40)
        self.send_button.clicked.connect(self.send_message)
        bottom_layout.addWidget(self.send_button)
        
        input_layout.addLayout(bottom_layout)
        main_layout.addWidget(input_container)

        # NEW: Layout for DB Viewer and Image Viewer buttons at the very bottom
        bottom_buttons_layout = QHBoxLayout()
        bottom_buttons_layout.setContentsMargins(5, 0, 5, 5) # Margin top is 0 to be closer to input

        self.db_viewer_button = QPushButton("DB Viewer")
        self.db_viewer_button.clicked.connect(self.db_viewer_requested)
        bottom_buttons_layout.addWidget(self.db_viewer_button)

        self.image_viewer_button = QPushButton("Image Viewer")
        self.image_viewer_button.clicked.connect(self.image_viewer_requested)
        bottom_buttons_layout.addWidget(self.image_viewer_button)

        main_layout.addLayout(bottom_buttons_layout) # Add this new layout to main_layout

        self.input_text_edit.installEventFilter(self)

    def open_image_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Sélectionner une image", "", "Images (*.png *.xpm *.jpg *.jpeg *.bmp *.gif)")
        if path:
            self.selected_image_path = path
            pixmap = QPixmap(path)
            self.preview_label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.preview_label.setVisible(True)

    def eventFilter(self, obj, event):
        if obj is self.input_text_edit and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Return and not self.input_text_edit.textCursor().hasSelection():
                self.send_message()
                return True
        return super().eventFilter(obj, event)

    def send_message(self):
        message_text = self.input_text_edit.toPlainText().strip()
        if message_text or self.selected_image_path:
            self.message_sent.emit(message_text, self.selected_image_path)
            self.input_text_edit.clear()
            self.preview_label.clear()
            self.preview_label.setVisible(False)
            self.selected_image_path = None

    def add_message(self, sender: str, text: str, image_path: Optional[str] = None, avatar_path: Optional[str] = None, avatar_size: int = 56):
        is_user = (sender == "User")
        message = ChatMessage(
            text=text, 
            is_user=is_user, 
            image_path=image_path,  # Pass the image path directly
            avatar_path=avatar_path, 
            avatar_size=avatar_size
        )
        self.message_model.add_message(message)
        self.message_list_view.scrollToBottom()

    def clear_messages(self):
        self.message_model.clear_messages()
