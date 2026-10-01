"""Drag-n-drop from Explorer onto the main window (+5 bonus feature).

The events are sent to the top-level window, as Windows does, so Qt routes them to the widget
under the cursor. Every step must be accepted: enter, each move (it decides the cursor: a
"not allowed" sign if refused), and the drop.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # no visible window needed

from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolBar  # noqa: E402

from client.main_window import MainWindow  # noqa: E402
from common.schemas import UserOut  # noqa: E402


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    api = MagicMock()  # no server needed: only the drag handling is tested
    api.list_files.return_value = []
    w = MainWindow(api, UserOut(id=1, username="ivanka", display_name="Ivanka"))
    w.show()
    app.processEvents()
    w.uploaded = []
    w.upload_paths = lambda paths: w.uploaded.extend(p.name for p in paths)
    yield w
    w.close()


@pytest.mark.parametrize("target", ["table", "toolbar"])
def test_files_dropped_from_explorer_are_uploaded(window, tmp_path, target):
    files = [tmp_path / "app.js", tmp_path / "photo.jpg"]
    for f in files:
        f.write_bytes(b"x")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(f)) for f in files])
    widget = window.table.viewport() if target == "table" else window.findChildren(QToolBar)[0]
    pos = widget.mapTo(window, widget.rect().center())
    args = (Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

    events = [QDragEnterEvent(pos, *args), QDragMoveEvent(pos, *args), QDropEvent(QPointF(pos), *args)]
    for event in events:
        QGuiApplication.sendEvent(window.windowHandle(), event)
        assert event.isAccepted(), f"{type(event).__name__} was refused"
    assert window.uploaded == ["app.js", "photo.jpg"]


def test_dragged_text_is_refused(window):
    # e.g. text selected in a browser: nothing to upload, so the cursor must say "not allowed"
    # (Qt treats a file drag as text too, so checking for text instead of files would be wrong).
    mime = QMimeData()
    mime.setText("some selected text")
    pos = window.table.viewport().mapTo(window, window.table.viewport().rect().center())
    enter = QDragEnterEvent(pos, Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                            Qt.KeyboardModifier.NoModifier)
    QGuiApplication.sendEvent(window.windowHandle(), enter)
    assert not enter.isAccepted()
    assert window.uploaded == []
