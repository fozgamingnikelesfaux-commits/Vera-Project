from PyQt5.QtCore import Qt, QAbstractListModel, QModelIndex
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ChatMessage:
    """Représente un message dans le chat"""
    text: str
    is_user: bool
    timestamp: datetime = field(default_factory=datetime.now)
    avatar_path: Optional[str] = None
    image_path: Optional[str] = None  # New field for the image
    avatar_size: int = 56
    copied: bool = False # New attribute


class MessageListModel(QAbstractListModel):
    """Modèle de données pour la liste des messages"""
    
    def __init__(self):
        super().__init__()
        self.messages = []

    def rowCount(self, parent=QModelIndex()):
        return len(self.messages)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.messages)):
            return None

        message = self.messages[index.row()]

        if role == Qt.DisplayRole:
            return message.text
        elif role == Qt.UserRole:  # message complet
            return message
        
        return None

    def add_message(self, message: ChatMessage):
        """Ajoute un nouveau message au modèle"""
        # Insertion à la fin de la liste (plus récent en bas)
        row = len(self.messages)
        self.beginInsertRows(QModelIndex(), row, row)
        self.messages.append(message)
        self.endInsertRows()

    def clear(self):
        """Efface tous les messages"""
        self.beginResetModel()
        self.messages.clear()
        self.endResetModel()

    def set_message_copied_status(self, index: QModelIndex, status: bool):
        if not index.isValid():
            return
        message = self.messages[index.row()]
        if message.copied != status:
            message.copied = status
            self.dataChanged.emit(index, index, [Qt.UserRole]) # Emit dataChanged for this item