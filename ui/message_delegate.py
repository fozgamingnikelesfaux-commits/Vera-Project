from PyQt5.QtWidgets import (
    QStyledItemDelegate, QStyle, QApplication, QStyleOptionViewItem
)
from PyQt5.QtCore import Qt, QRect, QSize, QPoint, QRectF, QEvent, QTimer, QModelIndex
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPainterPath
from .message_model import ChatMessage, MessageListModel

class MessageDelegate(QStyledItemDelegate):
    USER_BUBBLE_COLOR = QColor("#007A99")
    VERA_BUBBLE_COLOR = QColor("#005066")
    TEXT_COLOR = QColor("#00BFFF")
    ICON_COLOR = QColor("#00BFFF")

    PADDING = 15
    V_MARGIN = 8
    AVATAR_MARGIN = 10
    BUBBLE_RADIUS = 15
    ICON_SIZE = 16
    ICON_MARGIN = 5
    IMAGE_MAX_WIDTH = 300
    IMAGE_V_SPACING = 10
    MAX_MESSAGE_HEIGHT = 400 # Nouvelle constante pour limiter la hauteur d'un message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._avatar_cache = {}
        self._image_cache = {}
        self._copy_timer = QTimer(self)
        self._copy_timer.setSingleShot(True)
        self._copy_timer.timeout.connect(self._reset_copy_status)
        self._current_copied_index = QModelIndex()

    def _reset_copy_status(self):
        if self._current_copied_index.isValid():
            model = self._current_copied_index.model()
            if isinstance(model, MessageListModel):
                model.set_message_copied_status(self._current_copied_index, False)
            self._current_copied_index = QModelIndex()

    def get_cached_avatar(self, path: str, size: int) -> QPixmap:
        cache_key = f"{path}_{size}"
        if cache_key not in self._avatar_cache:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                circular_pixmap = QPixmap(size, size)
                circular_pixmap.fill(Qt.transparent)
                painter = QPainter(circular_pixmap)
                painter.setRenderHint(QPainter.Antialiasing)
                path = QPainterPath()
                path.addEllipse(0, 0, size, size)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, pixmap.scaled(
                    size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                ))
                painter.end()
                pixmap = circular_pixmap
            self._avatar_cache[cache_key] = pixmap
        return self._avatar_cache[cache_key]

    def get_cached_image(self, path: str) -> QPixmap:
        if path not in self._image_cache:
            pixmap = QPixmap(path)
            if not pixmap.isNull() and pixmap.width() > self.IMAGE_MAX_WIDTH:
                pixmap = pixmap.scaledToWidth(self.IMAGE_MAX_WIDTH, Qt.SmoothTransformation)
            self._image_cache[path] = pixmap
        return self._image_cache[path]

    def _get_icon_rect(self, bubble_rect: QRectF) -> QRect:
        """Calcule la position de l'icône de copie dans le coin inférieur droit."""
        return QRect(
            int(bubble_rect.right() - self.ICON_SIZE - self.ICON_MARGIN - 5),
            int(bubble_rect.bottom() - self.ICON_SIZE - self.ICON_MARGIN - 5),
            self.ICON_SIZE,
            self.ICON_SIZE
        )

    def _calculate_content_rects(self, view_width: int, metrics, message: ChatMessage):
        available_width = view_width - 95 - self.AVATAR_MARGIN - (2 * self.PADDING) - self.ICON_SIZE - self.ICON_MARGIN
        
        text_rect = QRect()
        if message.text:
            text_rect = metrics.boundingRect(
                QRect(0, 0, int(available_width), self.MAX_MESSAGE_HEIGHT), # Use MAX_MESSAGE_HEIGHT here
                Qt.TextWordWrap,
                message.text
            )
            # Ensure text_rect height does not exceed MAX_MESSAGE_HEIGHT
            text_rect.setHeight(min(text_rect.height(), self.MAX_MESSAGE_HEIGHT))

        image_rect = QRect()
        if message.image_path:
            pixmap = self.get_cached_image(message.image_path)
            if not pixmap.isNull():
                image_rect = pixmap.rect()

        return text_rect, image_rect

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        message: ChatMessage = index.data(Qt.UserRole)
        if not message:
            return QSize()

        text_rect, image_rect = self._calculate_content_rects(option.rect.width(), option.fontMetrics, message)
        
        content_height = 0
        if not text_rect.isNull():
            content_height += text_rect.height()
        
        if not image_rect.isNull():
            if content_height > 0:
                content_height += self.IMAGE_V_SPACING
            content_height += image_rect.height()

        bubble_height = content_height + (2 * self.PADDING)
        total_height = max(bubble_height, message.avatar_size) + (2 * self.V_MARGIN)

        return QSize(option.rect.width(), int(min(total_height, self.MAX_MESSAGE_HEIGHT + (2 * self.V_MARGIN) + (2 * self.PADDING)))) # Cap total height

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        message: ChatMessage = index.data(Qt.UserRole)
        if not message:
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = option.rect
        metrics = option.fontMetrics

        text_rect, image_rect = self._calculate_content_rects(rect.width(), metrics, message)
        
        content_height = 0
        if not text_rect.isNull():
            content_height += text_rect.height()
        
        if not image_rect.isNull():
            if content_height > 0:
                content_height += self.IMAGE_V_SPACING
            content_height += image_rect.height()

        bubble_width = max(text_rect.width(), image_rect.width()) + (2 * self.PADDING)
        if message.text: # Add space for copy icon only if there is text
             bubble_width += self.ICON_SIZE + self.ICON_MARGIN

        bubble_height = content_height + (2 * self.PADDING)

        bubble_y = rect.top() + (rect.height() - bubble_height) / 2
        avatar_y = rect.top() + (rect.height() - message.avatar_size) / 2

        if message.is_user:
            avatar_x = rect.right() - message.avatar_size - self.AVATAR_MARGIN
            bubble_x = avatar_x - bubble_width - self.AVATAR_MARGIN
            bubble_color = self.USER_BUBBLE_COLOR
        else:
            avatar_x = rect.left() + self.AVATAR_MARGIN
            bubble_x = avatar_x + message.avatar_size + self.AVATAR_MARGIN
            bubble_color = self.VERA_BUBBLE_COLOR

        if message.avatar_path:
            avatar = self.get_cached_avatar(message.avatar_path, message.avatar_size)
            if not avatar.isNull():
                painter.drawPixmap(QPoint(int(avatar_x), int(avatar_y)), avatar)

        bubble_rect = QRectF(bubble_x, bubble_y, bubble_width, bubble_height)
        painter.setBrush(bubble_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bubble_rect, self.BUBBLE_RADIUS, self.BUBBLE_RADIUS)

        current_y = bubble_y + self.PADDING

        if not text_rect.isNull():
            text_draw_rect = QRectF(
                bubble_x + self.PADDING,
                current_y,
                text_rect.width(),
                text_rect.height()
            )
            painter.setPen(self.TEXT_COLOR)
            painter.drawText(text_draw_rect, Qt.TextWordWrap, message.text)
            current_y += text_rect.height()

        if not image_rect.isNull():
            if not text_rect.isNull():
                current_y += self.IMAGE_V_SPACING
            pixmap = self.get_cached_image(message.image_path)
            image_x = bubble_x + (bubble_width - pixmap.width()) / 2
            painter.drawPixmap(QPoint(int(image_x), int(current_y)), pixmap)

        if message.text:
            icon_rect = self._get_icon_rect(bubble_rect)
            icon = QApplication.style().standardIcon(QStyle.SP_FileIcon)
            if message.copied:
                icon = QApplication.style().standardIcon(QStyle.SP_DialogApplyButton)
            icon.paint(painter, icon_rect)

        painter.restore()

    def editorEvent(self, event: QEvent, model, option: QStyleOptionViewItem, index) -> bool:
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            message: ChatMessage = index.data(Qt.UserRole)
            if not message or not message.text: # Only allow copy if there is text
                return False

            # Recalculate bubble geometry
            rect = option.rect
            metrics = option.fontMetrics
            text_rect, image_rect = self._calculate_content_rects(rect.width(), metrics, message)
            
            content_height = 0
            if not text_rect.isNull(): content_height += text_rect.height()
            if not image_rect.isNull():
                if content_height > 0: content_height += self.IMAGE_V_SPACING
                content_height += image_rect.height()

            bubble_width = max(text_rect.width(), image_rect.width()) + (2 * self.PADDING) + self.ICON_SIZE + self.ICON_MARGIN
            bubble_height = content_height + (2 * self.PADDING)
            bubble_y = rect.top() + (rect.height() - bubble_height) / 2

            if message.is_user:
                avatar_x = rect.right() - message.avatar_size - self.AVATAR_MARGIN
                bubble_x = avatar_x - bubble_width - self.AVATAR_MARGIN
            else:
                avatar_x = rect.left() + self.AVATAR_MARGIN
                bubble_x = avatar_x + message.avatar_size + self.AVATAR_MARGIN
            
            bubble_rect = QRectF(bubble_x, bubble_y, bubble_width, bubble_height)
            icon_rect = self._get_icon_rect(bubble_rect)

            if icon_rect.contains(event.pos()):
                clipboard = QApplication.clipboard()
                clipboard.setText(message.text)

                if isinstance(model, MessageListModel):
                    model.set_message_copied_status(index, True)
                    self._current_copied_index = index
                    self._copy_timer.start(1500)

                return True

        return super().editorEvent(event, model, option, index)