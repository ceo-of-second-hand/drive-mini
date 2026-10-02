"""Sync result window and the Sync button (offscreen, fake server; real clicks via QTest)."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

import client.main_window as main_window_module
from client.api import ApiError
from client.main_window import MainWindow
from client.sync import Conflict, SyncResult
from client.sync_dialog import SyncDialog, summary_html
from common.schemas import UserOut


@pytest.fixture(autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


def fake_sync(tmp_path):
    sync = MagicMock()
    sync.folder = tmp_path
    sync.resolve.return_value = "replaced the server's copy"
    return sync


def test_summary_lists_each_kind_of_change():
    result = SyncResult(uploaded=["a.js"], downloaded=["b.c"], deleted_on_server=["old.js"],
                        skipped=["sub: subfolders aren't synced"], errors=["x.js: server hiccup"])
    html = summary_html(result)
    for text in ["Uploaded to the drive", "a.js", "Downloaded to the folder", "b.c",
                 "Deleted on the drive", "old.js", "Skipped", "Errors", "x.js: server hiccup"]:
        assert text in html
    assert "Deleted in the folder" not in html  # empty sections are left out
    assert "up to date" in summary_html(SyncResult())


def test_keep_mine_button_resolves_the_conflict(tmp_path):
    sync = fake_sync(tmp_path)
    conflict = Conflict("a.js", "a.js", "changed here, changed on the server")
    dialog = SyncDialog(sync, SyncResult(conflicts=[conflict]))
    dialog.show()
    row = dialog.rows[0]
    QTest.mouseClick(row.keep_mine, Qt.MouseButton.LeftButton)
    sync.resolve.assert_called_once_with(conflict, "mine")
    assert row.keep_mine.isHidden() and row.keep_server.isHidden()
    assert "resolved: replaced the server's copy" in row.label.text()


def test_failed_resolution_keeps_the_buttons(tmp_path, monkeypatch):
    sync = fake_sync(tmp_path)
    sync.resolve.side_effect = ApiError(0, "Cannot reach the server")
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    dialog = SyncDialog(sync, SyncResult(conflicts=[Conflict("a.js", "a.js", "x")]))
    dialog.show()
    QTest.mouseClick(dialog.rows[0].keep_server, Qt.MouseButton.LeftButton)
    assert warnings == ["a.js: Cannot reach the server"]
    assert not dialog.rows[0].keep_server.isHidden()  # still there to try again


def make_window(username="ivanka"):
    api = MagicMock()
    api.list_files.return_value = []
    api.base_url = "http://127.0.0.1:8000"
    return MainWindow(api, UserOut(id=1, username=username, display_name=username.title()))


@pytest.fixture
def window():
    main_window_module.settings().clear()  # each test starts without a remembered folder
    w = make_window()
    yield w
    w.close()


def test_sync_button_runs_sync_shows_result_and_refreshes(window, tmp_path, monkeypatch):
    window.sync_folder = tmp_path
    runs, shown = [], []
    monkeypatch.setattr(main_window_module, "FolderSync",
                        lambda api, folder, user: MagicMock(run=lambda: runs.append((folder, user)) or SyncResult()))
    monkeypatch.setattr(main_window_module.SyncDialog, "exec", lambda self: shown.append(self))
    calls_before = window.api.list_files.call_count
    window.sync_now()
    assert runs == [(tmp_path, "ivanka")] and len(shown) == 1
    assert window.api.list_files.call_count == calls_before + 1  # table refreshed afterwards


def test_sync_without_a_folder_asks_for_one_and_remembers_it(window, tmp_path, monkeypatch):
    window.sync_folder = None
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: "")
    window.sync_now()  # cancelled: nothing happens
    assert window.sync_folder is None

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: str(tmp_path))
    monkeypatch.setattr(main_window_module, "FolderSync", lambda *a: MagicMock(run=SyncResult))
    monkeypatch.setattr(main_window_module.SyncDialog, "exec", lambda self: None)
    window.sync_now()
    assert window.sync_folder == Path(tmp_path)
    assert main_window_module.settings().value(window.folder_setting) == str(tmp_path)  # temp settings


def test_folder_is_remembered_per_account(window, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: str(tmp_path))
    window.choose_sync_folder()
    assert make_window("ivanka").sync_folder == Path(tmp_path)  # log out + log in: still there
    assert make_window("bob").sync_folder is None  # another account on this PC: its own (none yet)


def test_changing_the_folder_asks_and_unlinks_the_old_one(window, tmp_path, monkeypatch):
    old, new = tmp_path / "A", tmp_path / "B"
    old.mkdir()
    new.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: str(old))
    window.choose_sync_folder()  # first choice: no question
    snapshot = main_window_module.FolderSync(window.api, old, "ivanka").snapshot_file
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text("{}")  # as if A had been synced

    questions = []
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: str(new))
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a: questions.append(a[2]) or QMessageBox.StandardButton.No)
    assert not window.choose_sync_folder()  # answered No: nothing changes
    assert window.sync_folder == old and snapshot.exists()
    assert "will no longer be synced" in questions[0]

    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes)
    assert window.choose_sync_folder()
    assert window.sync_folder == new
    assert not snapshot.exists()  # A unlinked: coming back later is a first sync
