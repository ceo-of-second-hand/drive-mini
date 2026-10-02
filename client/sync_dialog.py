"""Sync result window: what was done, plus each conflict with Keep mine / Keep server's."""
from html import escape

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from client.api import ApiError
from client.sync import Conflict, FolderSync, SyncResult
from client.ui import busy_cursor, short_path

SECTIONS = [
    ("uploaded", "Uploaded to the drive"),
    ("downloaded", "Downloaded to the folder"),
    ("deleted_on_server", "Deleted on the drive (you deleted them in the folder)"),
    ("deleted_locally", "Deleted in the folder (they were deleted on the drive)"),
    ("skipped", "Skipped"),
    ("errors", "Errors (will be retried at the next sync)"),
]


def summary_html(result: SyncResult) -> str:
    if result.nothing_happened:
        return "<b>Everything is up to date.</b>"
    parts = []
    for attr, title in SECTIONS:
        names = getattr(result, attr)
        if names:
            items = "".join(f"<li>{escape(n)}</li>" for n in names)
            parts.append(f"<b>{title}</b> ({len(names)})<ul style='margin-top:2px'>{items}</ul>")
    return "".join(parts) or "No files were transferred."


class ConflictRow(QWidget):
    """One conflict: name, what happened on each side, and the two choices."""

    def __init__(self, sync: FolderSync, conflict: Conflict):
        super().__init__()
        self.sync, self.conflict = sync, conflict
        self.label = QLabel(f"<b>{escape(conflict.name)}</b> — {escape(conflict.reason)}")
        self.keep_mine = QPushButton("Keep mine")
        self.keep_server = QPushButton("Keep server's")
        self.keep_mine.clicked.connect(lambda: self._resolve("mine"))
        self.keep_server.clicked.connect(lambda: self._resolve("server"))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.keep_mine)
        layout.addWidget(self.keep_server)

    def _resolve(self, keep: str) -> None:
        try:
            with busy_cursor():
                done = self.sync.resolve(self.conflict, keep)
        except (ApiError, OSError) as exc:
            QMessageBox.warning(self, "Sync", f"{self.conflict.name}: {getattr(exc, 'detail', exc)}")
            return
        self.keep_mine.hide()
        self.keep_server.hide()
        self.label.setText(f"<b>{escape(self.conflict.name)}</b> — resolved: {done} ✓")


class SyncDialog(QDialog):
    def __init__(self, sync: FolderSync, result: SyncResult, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sync result — Drive Mini")
        self.resize(560, 420)
        content = QWidget()
        layout = QVBoxLayout(content)
        self.summary = QLabel(summary_html(result), wordWrap=True)
        layout.addWidget(self.summary)

        self.rows = [ConflictRow(sync, c) for c in result.conflicts]
        if self.rows:
            box = QGroupBox(f"Conflicts ({len(self.rows)})")
            box_layout = QVBoxLayout(box)
            box_layout.addWidget(QLabel("These files changed on both sides since the last sync. "
                                        "Nothing was changed for them: choose which version to keep.",
                                        wordWrap=True))
            for row in self.rows:
                box_layout.addWidget(row)
            layout.addWidget(box)
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        outer = QVBoxLayout(self)
        folder = QLabel()
        folder.setText("Folder: " + short_path(sync.folder, folder, 480))
        folder.setToolTip(str(sync.folder))
        outer.addWidget(folder)
        outer.addWidget(scroll)
        outer.addWidget(buttons)
