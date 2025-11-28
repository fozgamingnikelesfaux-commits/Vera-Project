from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QSizePolicy, QHBoxLayout, QLineEdit, QFileDialog


class AvatarsTab(QWidget):
    """Onglet de configuration des avatars"""

    def __init__(self, config, on_avatar_changed=None, on_size_changed=None):
        super().__init__()
        self.config = config
        self.on_avatar_changed = on_avatar_changed
        self.on_size_changed = on_size_changed
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # Boutons choix avatar
        btn_user = QPushButton("Choisir avatar utilisateur")
        btn_user.clicked.connect(lambda: self._choose_avatar(True))
        btn_vera = QPushButton("Choisir avatar Vera")  
        btn_vera.clicked.connect(lambda: self._choose_avatar(False))
        layout.addWidget(btn_user)
        layout.addWidget(btn_vera)

        # Contrôle taille avatar
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Taille avatar :"))
        self.size_input = QLineEdit(str(self.config.get("avatar_size", 56)))
        self.size_input.setFixedWidth(60)
        size_row.addWidget(self.size_input)
        size_apply = QPushButton("Appliquer")
        size_apply.clicked.connect(self._apply_size)
        size_row.addWidget(size_apply)
        size_row.addStretch()
        layout.addLayout(size_row)

        # Zone aperçu
        preview_row = QHBoxLayout()
        self.preview_user = QLabel()
        self.preview_vera = QLabel()
        preview_row.addWidget(QLabel("Aperçu utilisateur:"))
        preview_row.addWidget(self.preview_user)
        preview_row.addStretch()
        preview_row.addWidget(QLabel("Aperçu Vera:"))
        preview_row.addWidget(self.preview_vera)
        layout.addLayout(preview_row)

        layout.addStretch()
        self._update_previews()

    def _choose_avatar(self, is_user: bool):
        """Ouvre un dialogue pour choisir un avatar"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une image (png/jpg)",
            "",
            "Images (*.png *.jpg *.jpeg)"
        )
        if not path:
            return
        
        if self.on_avatar_changed:
            self.on_avatar_changed(path, is_user)
            self._update_previews()

    def _apply_size(self):
        """Applique la nouvelle taille d'avatar"""
        try:
            size = int(self.size_input.text().strip())
            if 24 <= size <= 256:
                if self.on_size_changed:
                    self.on_size_changed(size)
                    self._update_previews()
        except ValueError:
            pass

    def _update_previews(self):
        """Met à jour les aperçus des avatars"""
        size = self.config.get("avatar_size", 56)
        self.preview_user.setFixedSize(size, size)
        self.preview_vera.setFixedSize(size, size)

        for preview, path_key in [
            (self.preview_user, "user_avatar"),
            (self.preview_vera, "vera_avatar")
        ]:
            path = self.config.get(path_key)
            if path:
                pix = QPixmap(path).scaled(
                    size, size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                preview.setPixmap(pix)
            else:
                preview.setPixmap(QPixmap())
                preview.setStyleSheet(
                    "background-color: #222;"
                    "border-radius: 8px;"
                )