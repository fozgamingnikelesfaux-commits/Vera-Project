# NOTE: The custom window frame and styling has been temporarily disabled for debugging purposes.
# The UI was not appearing, and this is to test if the issue is related to the custom window implementation.

from PyQt5.QtWidgets import QMainWindow, QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QSpacerItem, QSizePolicy, QLabel, QApplication
from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtGui import QMouseEvent, QCursor


class ConstrainedMainWindow(QMainWindow):
    """Une fenêtre principale qui gère mieux sa géométrie"""

    def __init__(self):
        super().__init__()
        self._screen_rect = None
        self.updateScreenGeometry()

    def updateScreenGeometry(self):
        """Met à jour les limites de taille basées sur l'écran"""
        if screen := self.screen():
            self._screen_rect = screen.availableGeometry()
            self.setMaximumSize(
                self._screen_rect.width(),
                self._screen_rect.height()
            )

    def setGeometry(self, *args):
        """Surcharge pour contraindre la géométrie à l'écran"""
        if not self._screen_rect:
            self.updateScreenGeometry()
        if len(args) == 1 and isinstance(args[0], QRect):
            rect = args[0]
        elif len(args) == 4:
            rect = QRect(*args)
        else:
            return super().setGeometry(*args)
        if self._screen_rect:
            w = min(rect.width(), self._screen_rect.width())
            h = min(rect.height(), self._screen_rect.height())
            x = max(self._screen_rect.left(), min(rect.x(), self._screen_rect.right() - w))
            y = max(self._screen_rect.top(), min(rect.y(), self._screen_rect.bottom() - h))
            if self.isMaximized(): # NOUVEAU: Ne pas contraindre si maximisé
                rect = QRect(x, y, w, h)
            else:
                rect = QRect(x, y, w, h)
        super().setGeometry(rect)

    def moveEvent(self, event):
        """Garde la fenêtre dans les limites de l'écran"""
        super().moveEvent(event)
        if self._screen_rect and not self.isMaximized(): # NOUVEAU: Ne pas contraindre si maximisé
            pos = self.pos()
            size = self.size()
            x = max(self._screen_rect.left(), min(pos.x(), self._screen_rect.right() - size.width()))
            y = max(self._screen_rect.top(), min(pos.y(), self._screen_rect.bottom() - size.height()))
            if x != pos.x() or y != pos.y():
                self.move(x, y)

    def resizeEvent(self, event):
        """Empêche la fenêtre de devenir plus grande que l'écran"""
        super().resizeEvent(event)
        if self._screen_rect and not self.isMaximized(): # NOUVEAU: Ne pas contraindre si maximisé
            size = self.size()
            w = min(size.width(), self._screen_rect.width())
            h = min(size.height(), self._screen_rect.height())
            if w != size.width() or h != size.height():
                self.resize(w, h)


class MainWindow(QMainWindow):
    """
    Fenêtre principale avec une esthétique futuriste, sans cadre,
    transparente et avec des coins arrondis.
    """
    def __init__(self):
        super().__init__()

        self.offset = None
        # --- Resizing variables ---
        self._resizing = False
        self._resize_direction = Qt.SizeAllCursor
        self._start_pos = QPoint()
        self._start_geometry = QRect()
        self.BORDER_WIDTH = 10 # Define resize border width (increased for better usability)
        self._screen_rect = None # Initialize _screen_rect for MainWindow

        self.main_widget = QWidget()
        self.main_widget.setObjectName("main_widget")
        self.setCentralWidget(self.main_widget)

        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(1, 1, 1, 1)
        self.main_layout.setSpacing(0)

        # --- Title Bar ---
        title_bar_layout = QHBoxLayout()
        title_bar_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.minimize_btn = QPushButton("\u2014")
        self.maximize_btn = QPushButton("\U0001F5D6")
        self.close_btn = QPushButton("\u2715")

        for btn in [self.minimize_btn, self.maximize_btn, self.close_btn]:
            btn.setObjectName("window-control-btn")
            btn.setFixedSize(40, 30) # Taille rétablie
            title_bar_layout.addWidget(btn)
        
        title_bar_layout.setContentsMargins(0, 5, 15, 0) # Marge droite maintenue
        self.main_layout.addLayout(title_bar_layout)

        # Connections
        self.minimize_btn.clicked.connect(self.showMinimized)
        self.maximize_btn.clicked.connect(self.toggle_maximize)
        self.close_btn.clicked.connect(self.close)

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Vera")
        self.resize(1200, 800)
        self.apply_stylesheet()
        self.updateScreenGeometry() # Ensure screen geometry is up-to-date
        self.center_on_screen() # Center the window on startup

    def updateScreenGeometry(self):
        """Met à jour les limites de taille basées sur l'écran actuel de la fenêtre."""
        if screen := QApplication.screenAt(self.pos()): # Use QApplication.screenAt for multi-screen support
            self._screen_rect = screen.availableGeometry()
            # self.setMaximumSize( # Removed setMaximumSize to allow resizing beyond initial screen
            #     self._screen_rect.width(),
            #     self._screen_rect.height()
            # )

    def center_on_screen(self):
        """Centre la fenêtre sur l'écran principal."""
        screen_geometry = QApplication.primaryScreen().availableGeometry() # Use primaryScreen for initial centering
        x = (screen_geometry.width() - self.width()) / 2
        y = (screen_geometry.height() - self.height()) / 2
        self.move(int(x), int(y))

    def set_content_widget(self, widget: QWidget):
        """Ajoute le widget de contenu principal au layout."""
        self.main_layout.addWidget(widget)

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def apply_stylesheet(self):
        """Applique la feuille de style QSS pour un look futuriste."""
        stylesheet = """
            #main_widget {
                background-color: rgba(0, 30, 40, 0.3); /* Plus transparent */
                border-radius: 25px;
                border: 1px solid #00BFFF;
            }
            QPushButton#window-control-btn {
                background-color: transparent;
                color: #00BFFF;
                border: none;
                font-size: 12px; /* Taille de police réduite */
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
                padding: 40px;
            }
            QTabBar::tab {
                background: transparent;
                color: #00BFFF;
                padding: 12px 30px; /* Padding vertical augmenté */
                border: 1px solid transparent;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
                font-size: 14px; /* Taille de police augmentée */
                min-width: 90px; /* Largeur minimale pour les onglets */
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

    def mousePressEvent(self, event: QMouseEvent):
        """Capture la position initiale du clic pour le déplacement ou le redimensionnement."""
        if event.button() == Qt.LeftButton:
            # Vérifier si on est sur un bord de redimensionnement
            self._resize_direction = self._get_resize_direction(event.pos())
            if self._resize_direction != Qt.SizeAllCursor:
                self._resizing = True
                self._start_pos = event.globalPos()
                self._start_geometry = self.geometry()
                self.setCursor(QCursor(self._resize_direction)) # Explicitly set cursor on press
            # Sinon, permettre le déplacement par la barre de titre seulement
            elif event.y() < 40: # Zone de la barre de titre
                self.offset = event.globalPos() - self.pos()
            else:
                self.offset = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Déplace/redimensionne la fenêtre et change le curseur."""
        super().mouseMoveEvent(event) # Call superclass method first

        if self._resizing:
            self._resize_window(event.globalPos())
        elif self.offset is not None and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.offset)
            self._check_and_reposition_offscreen() # Check continuously during dragging
        else:
            # Changer le curseur quand on survole un bord de redimensionnement
            direction = self._get_resize_direction(event.pos())
            if direction != Qt.SizeAllCursor:
                self.setCursor(QCursor(direction))
            else:
                self.unsetCursor() # Only unset if no resize handle is detected

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Réinitialise les drapeaux de déplacement/redimensionnement."""
        self.offset = None
        self._resizing = False
        self.unsetCursor() # Réinitialiser le curseur
        super().mouseReleaseEvent(event)
        # Après le déplacement, vérifier si la fenêtre est hors écran
        self._check_and_reposition_offscreen() # Call the new method here

    def _check_and_reposition_offscreen(self):
        """Vérifie si la fenêtre est significativement hors écran et la repositionne."""
        if self.isMaximized() or self.isMinimized():
            return

        # Get the screen the window is currently on
        current_screen = QApplication.screenAt(self.pos())
        if not current_screen:
            current_screen = QApplication.primaryScreen() # Fallback to primary screen

        screen_geometry = current_screen.availableGeometry()
        window_geometry = self.geometry()

        # Calculate the intersection of the window and the screen
        intersection = screen_geometry.intersected(window_geometry)

        # If the intersection area is less than a certain percentage of the window area, recenter
        window_area = window_geometry.width() * window_geometry.height()
        intersection_area = intersection.width() * intersection.height()

        # Define a threshold (e.g., if less than 25% of the window is visible, recenter)
        if window_area > 0 and intersection_area < (window_area * 0.25):
            self.center_on_screen()


    def _get_resize_direction(self, pos: QPoint) -> Qt.CursorShape:
        """Détermine la direction du redimensionnement en fonction de la position de la souris."""
        width = self.width()
        height = self.height()
        x = pos.x()
        y = pos.y()

        on_left = x < self.BORDER_WIDTH
        on_right = x > width - self.BORDER_WIDTH
        on_top = y < self.BORDER_WIDTH
        on_bottom = y > height - self.BORDER_WIDTH

        if on_left and on_top:
            return Qt.SizeFDiagCursor # Top-left
        elif on_left and on_bottom:
            return Qt.SizeBDiagCursor # Bottom-left
        elif on_right and on_top:
            return Qt.SizeBDiagCursor # Top-right
        elif on_right and on_bottom:
            return Qt.SizeFDiagCursor # Bottom-right
        elif on_left:
            return Qt.SizeHorCursor # Left
        elif on_right:
            return Qt.SizeHorCursor # Right
        elif on_top:
            return Qt.SizeVerCursor # Top
        elif on_bottom:
            return Qt.SizeVerCursor # Bottom
        return Qt.SizeAllCursor # No resize handle

    def _resize_window(self, global_pos: QPoint):
        """Redimensionne la fenêtre en fonction du mouvement de la souris et de la direction."""
        delta = global_pos - self._start_pos
        new_geometry = self._start_geometry

        if self._resize_direction == Qt.SizeHorCursor: # Left or Right
            if self._start_pos.x() > self._start_geometry.center().x(): # Right border
                new_geometry.setWidth(max(self.minimumWidth(), self._start_geometry.width() + delta.x()))
            else: # Left border
                right_edge = self._start_geometry.x() + self._start_geometry.width()
                new_width = max(self.minimumWidth(), right_edge - global_pos.x())
                new_geometry.setX(right_edge - new_width)
                new_geometry.setWidth(new_width)
            self.setGeometry(new_geometry)
        elif self._resize_direction == Qt.SizeVerCursor: # Top or Bottom
            if self._start_pos.y() > self._start_geometry.center().y(): # Bottom border
                new_geometry.setHeight(max(self.minimumHeight(), self._start_geometry.height() + delta.y()))
            else: # Top border
                bottom_edge = self._start_geometry.y() + self._start_geometry.height()
                new_height = max(self.minimumHeight(), bottom_edge - global_pos.y())
                new_geometry.setY(bottom_edge - new_height)
                new_geometry.setHeight(new_height)
            self.setGeometry(new_geometry)
        elif self._resize_direction == Qt.SizeFDiagCursor: # Top-left or Bottom-right
            if (self._start_pos.x() < new_geometry.center().x() and self._start_pos.y() < new_geometry.center().y()) or \
               (self._start_pos.x() > new_geometry.center().x() and self._start_pos.y() > new_geometry.center().y()): # Top-left or Bottom-right
                new_geometry.setX(new_geometry.x() + delta.x())
                new_geometry.setWidth(max(self.minimumWidth(), new_geometry.width() - delta.x()))
                new_geometry.setY(new_geometry.y() + delta.y())
                new_geometry.setHeight(max(self.minimumHeight(), new_geometry.height() - delta.y()))
            else: # Bottom-right (primary logic)
                new_geometry.setWidth(max(self.minimumWidth(), new_geometry.width() + delta.x()))
                new_geometry.setHeight(max(self.minimumHeight(), new_geometry.height() + delta.y()))
            self.setGeometry(new_geometry)
        elif self._resize_direction == Qt.SizeBDiagCursor: # Top-right or Bottom-left
            if (self._start_pos.x() > new_geometry.center().x() and self._start_pos.y() < new_geometry.center().y()) or \
               (self._start_pos.x() < new_geometry.center().x() and self._start_pos.y() > new_geometry.center().y()): # Top-right or Bottom-left
                new_geometry.setWidth(max(self.minimumWidth(), new_geometry.width() + delta.x()))
                new_geometry.setY(new_geometry.y() + delta.y())
                new_geometry.setHeight(max(self.minimumHeight(), new_geometry.height() - delta.y()))
            else: # Top-right (primary logic)
                new_geometry.setX(new_geometry.x() + delta.x())
                new_geometry.setWidth(max(self.minimumWidth(), new_geometry.width() - delta.x()))
                new_geometry.setHeight(max(self.minimumHeight(), new_geometry.height() + delta.y()))
            self.setGeometry(new_geometry)
