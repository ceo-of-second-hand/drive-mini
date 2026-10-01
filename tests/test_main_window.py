"""Main window: Created header toggles the order, filter box, show/hide columns, preview.

Real clicks go through Qt's event routing (QTest), no server (fake api)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta, timezone  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtCore import QBuffer, QPoint, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from client.file_model import CREATED_COLUMN, NAME_COLUMN  # noqa: E402
from client.main_window import MainWindow  # noqa: E402
from client.sorting import FileFilter  # noqa: E402
from common.schemas import FileOut, UserOut  # noqa: E402

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


def png_bytes() -> bytes:
    image = QImage(4, 4, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def file_out(i, name, hours, size=10):
    t = T0 + timedelta(hours=hours)
    return FileOut(id=i, name=name, extension=name.rsplit(".", 1)[-1], size=size, mime_type="x",
                   created_at=t, modified_at=t, uploader_name="Ivanka", editor_name="Ivanka")


CONTENT = {1: b"console.log('hi');", 2: png_bytes(), 3: b"int main(){}", 4: b"\xff\xd8 jpg"}


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    api = MagicMock()
    api.list_files.return_value = [file_out(1, "app.js", 2), file_out(2, "logo.png", 5),
                                   file_out(3, "main.c", 0), file_out(4, "photo.jpg", 1)]
    api.download.side_effect = lambda file_id: CONTENT[file_id]
    w = MainWindow(api, UserOut(id=1, username="ivanka", display_name="Ivanka"))
    w.show()
    app.processEvents()
    yield w
    w.close()


def shown(w):
    return [w.model.file_at(r).name for r in range(w.model.rowCount())]


def click_header(w, column):
    header = w.table.horizontalHeader()
    x = header.sectionViewportPosition(column) + header.sectionSize(column) // 2
    QTest.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(x, header.height() // 2))


def test_newest_first_by_default_and_created_header_toggles(window):
    assert shown(window) == ["logo.png", "app.js", "photo.jpg", "main.c"]
    assert window.model.headerData(CREATED_COLUMN, Qt.Orientation.Horizontal) == "Created ▼"
    click_header(window, CREATED_COLUMN)
    assert shown(window) == ["main.c", "photo.jpg", "app.js", "logo.png"]
    assert window.model.headerData(CREATED_COLUMN, Qt.Orientation.Horizontal) == "Created ▲"
    click_header(window, NAME_COLUMN)  # other headers don't sort
    assert shown(window) == ["main.c", "photo.jpg", "app.js", "logo.png"]


def test_filter_box_shows_only_c_and_jpg(window):
    window.filter_box.setCurrentIndex(window.filter_box.findData(FileFilter.C_JPG))
    assert shown(window) == ["photo.jpg", "main.c"]
    assert "2 of 4" in window.statusBar().currentMessage()
    window.filter_box.setCurrentIndex(window.filter_box.findData(FileFilter.ALL))
    assert len(shown(window)) == 4


def test_any_column_but_name_can_be_hidden(window):
    menu = window.columns_menu()
    actions = {a.text(): a for a in menu.actions()}
    assert not actions["Name"].isEnabled()
    actions["Uploader"].setChecked(False)
    assert window.table.isColumnHidden(3)
    window.set_column_visible(NAME_COLUMN, False)  # ignored
    assert not window.table.isColumnHidden(NAME_COLUMN)


def select(w, name):
    row = shown(w).index(name)
    rect = w.table.visualRect(w.model.index(row, NAME_COLUMN))
    QTest.mouseClick(w.table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())


def test_preview_js_as_text_png_as_image_others_message(window):
    select(window, "app.js")
    assert window.preview.currentWidget() is window.preview.text
    assert window.preview.text.toPlainText() == "console.log('hi');"

    select(window, "logo.png")
    assert window.preview.currentWidget() is window.preview.image
    assert not window.preview.image.label.pixmap().isNull()

    downloads = window.api.download.call_count
    select(window, "main.c")
    assert window.preview.currentWidget() is window.preview.message
    assert "No preview" in window.preview.message.text()
    assert window.api.download.call_count == downloads  # nothing downloaded for other types


def test_png_that_is_not_an_image_gets_a_message(window):
    CONTENT[2] = b"not really a png"
    try:
        select(window, "logo.png")
        assert window.preview.currentWidget() is window.preview.message
        assert "isn't a valid PNG" in window.preview.message.text()
    finally:
        CONTENT[2] = png_bytes()
