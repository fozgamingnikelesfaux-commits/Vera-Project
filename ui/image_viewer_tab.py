from PyQt5 import QtWidgets, QtGui, QtCore
from PIL import Image
from pathlib import Path
import os

class ImageViewerTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.assets_path = Path("F:/Ai - Copie/assets")
        self.init_ui()

    def init_ui(self):
        # Main layout for the tab
        main_layout = QtWidgets.QVBoxLayout(self)

        # Image display area
        self.image_label = QtWidgets.QLabel("No Image Selected")
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid gray;")
        self.image_label.setFixedSize(600, 400)  # Fixed size for display area
        main_layout.addWidget(self.image_label)

        # Scroll area for image selection buttons
        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        buttons_widget = QtWidgets.QWidget()
        self.buttons_layout = QtWidgets.QVBoxLayout(buttons_widget)
        buttons_widget.setLayout(self.buttons_layout)
        scroll_area.setWidget(buttons_widget)

        self.load_images_from_assets()

    def load_images_from_assets(self):
        # Clear existing buttons
        while self.buttons_layout.count():
            item = self.buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.assets_path.exists():
            self.buttons_layout.addWidget(QtWidgets.QLabel("Assets folder not found."))
            return

        image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')
        found_images = []
        for file_path in self.assets_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                found_images.append(file_path)
        
        if not found_images:
            self.buttons_layout.addWidget(QtWidgets.QLabel("No images found in assets folder."))
            return

        for image_path in sorted(found_images):
            button = QtWidgets.QPushButton(image_path.name)
            button.clicked.connect(lambda _, path=image_path: self.display_image(path))
            self.buttons_layout.addWidget(button)

    def display_image(self, image_path: Path):
        try:
            pil_image = Image.open(image_path)
            
            # Resize image to fit label while maintaining aspect ratio
            label_size = self.image_label.size()
            max_width = label_size.width()
            max_height = label_size.height()

            pil_image.thumbnail((max_width, max_height), Image.LANCZOS)
            
            # Convert PIL Image to QPixmap
            q_image = QtGui.QImage(pil_image.tobytes(), pil_image.width, pil_image.height, 
                                   pil_image.width * (len(pil_image.getbands())), # bytes per line
                                   QtGui.QImage.Format_RGB888 if pil_image.mode == 'RGB' else QtGui.QImage.Format_RGBA8888) # Handle RGB and RGBA
            
            pixmap = QtGui.QPixmap.fromImage(q_image)
            self.image_label.setPixmap(pixmap)
            self.image_label.setText("") # Clear "No Image Selected" text
            self.image_label.setToolTip(image_path.name) # Show filename on hover

        except Exception as e:
            self.image_label.setText(f"Error loading image: {image_path.name}\n{e}")
            self.image_label.setPixmap(QtGui.QPixmap()) # Clear any previous image
            print(f"Error loading image {image_path}: {e}")

if __name__ == '__main__':
    # Simple test to run the tab standalone
    import sys
    app = QtWidgets.QApplication(sys.argv)
    viewer = ImageViewerTab()
    viewer.setWindowTitle("Image Viewer Test")
    viewer.show()
    sys.exit(app.exec_())
