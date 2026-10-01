"""Preview panel on the right of the table (FileViewer / TextViewer / ImageViewer).

Variant 57: .js is shown as text, .png as an image; other types get a short message.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QScrollArea, QStackedWidget

from common.rules import file_extension

PREVIEW_MAX_BYTES = 2 * 1024 * 1024  # bigger files aren't downloaded just to preview them


def preview_kind(name: str) -> str | None:
    """'text', 'image' or None (no preview for this type)."""
    return {"js": "text", "png": "image"}.get(file_extension(name))


class TextViewer(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setFont(QFont("Consolas", 10))

    def display(self, data: bytes) -> None:
        self.setPlainText(data.decode("utf-8", errors="replace"))


class ImageViewer(QScrollArea):
    def __init__(self):
        super().__init__()
        self.label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.setWidget(self.label)
        self.setWidgetResizable(True)

    def display(self, data: bytes) -> bool:
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return False  # e.g. a file named .png that isn't really an image
        if pixmap.width() > 600:
            pixmap = pixmap.scaledToWidth(600, Qt.TransformationMode.SmoothTransformation)
        self.label.setPixmap(pixmap)
        return True


class PreviewPanel(QStackedWidget):
    """Shows one of: a message, the text viewer, the image viewer."""

    def __init__(self):
        super().__init__()
        self.message = QLabel(alignment=Qt.AlignmentFlag.AlignCenter, wordWrap=True)
        self.message.setStyleSheet("color: #777;")
        self.text = TextViewer()
        self.image = ImageViewer()
        for widget in (self.message, self.text, self.image):
            self.addWidget(widget)
        self.show_message("Select a file to preview it.\n(.js as text, .png as image)")

    def show_message(self, text: str) -> None:
        self.message.setText(text)
        self.setCurrentWidget(self.message)

    def show_content(self, name: str, data: bytes) -> None:
        kind = preview_kind(name)
        if kind == "text":
            self.text.display(data)
            self.setCurrentWidget(self.text)
        elif kind == "image" and self.image.display(data):
            self.setCurrentWidget(self.image)
        elif kind == "image":
            self.show_message(f"“{name}” can't be shown: it isn't a valid PNG image.")
        else:
            self.show_message(f"No preview for “{name}”.\nOnly .js and .png files are previewed.")
