# Mode strict pour éviter les erreurs silencieuses
from __future__ import annotations

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import (
    QListView, QFrame, QWidget, QVBoxLayout,
    QSizePolicy, QAbstractItemView
)

class VirtualListView(QListView):
    """Une version améliorée de QListView avec meilleures contraintes de taille"""
    
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.NoFrame)
        self.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setUniformItemSizes(False)  # Items peuvent avoir des tailles différentes
        self.setSpacing(4)  # Petit espace entre les items
        self.setEditTriggers(QAbstractItemView.AllEditTriggers) # Activer les triggers pour le delegate
        
        # Contraintes de taille strictes
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(100)  # Hauteur minimale raisonnable
        self.setMaximumHeight(800)  # Hauteur maximale raisonnable
        
        self.setSizeAdjustPolicy(QListView.AdjustToContents)
        self.setResizeMode(QListView.Adjust)
        
        # Style
        self.setStyleSheet("""
            QListView {
                background: transparent;
                border: none;
                padding: 0px;
                max-height: 800px;
            }
            QListView::item {
                border: none;
                padding: 0px;
                max-height: 800px;
            }
        """)
        
        # Le viewport avec limites aussi
        self.viewport().setMaximumHeight(800)
        self.viewport().setAutoFillBackground(False)

    def sizeHint(self) -> QSize:
        """Taille suggérée raisonnable"""
        sh = super().sizeHint()
        return QSize(sh.width(), min(sh.height(), 800))
        
    def minimumSizeHint(self) -> QSize:
        """Taille minimale raisonnable"""
        return QSize(200, 100)