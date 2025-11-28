from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton
)
from PyQt5.QtCore import pyqtSignal

class GoalsTab(QWidget):
    """Onglet de gestion des objectifs"""
    on_refresh = pyqtSignal() # Signal to request data refresh

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # Bouton rafraîchir
        refresh_btn = QPushButton("Rafraîchir objectifs")
        refresh_btn.clicked.connect(self.refresh_goals)
        layout.addWidget(refresh_btn)

        # Le container de boutons sera rempli dynamiquement
        self.goals_layout = layout
        layout.addStretch() # Add a stretch to push buttons to the top

    def refresh_goals(self):
        """Déclenche le rafraîchissement des objectifs"""
        self.on_refresh.emit()

    def set_goals(self, goals: list, toggle_callback):
        """Met à jour l'affichage des objectifs"""
        # D'abord nettoyer les anciens boutons sauf le refresh button and the stretch
        while self.goals_layout.count() > 1:
            item = self.goals_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                self.goals_layout.removeItem(item)

        for g in goals:
            btn = QPushButton(
                f"{g.get('description','?')} (Priority: {g.get('priority',0)}) [{g.get('status','')}]"
            )
            btn.setCheckable(True)
            btn.setChecked(g.get('status') == "active")
            btn.clicked.connect(lambda checked, gid=g.get('id'): toggle_callback(gid))
            self.goals_layout.addWidget(btn)
        self.goals_layout.addStretch() # Re-add the stretch after adding buttons