"""Main window (FileListView): the user's virtual disk as a table, plus file actions."""
from pathlib import Path

from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QHeaderView, QLabel, QMainWindow,
                               QMessageBox, QSizePolicy, QTableView, QToolBar, QWidget)

from client.api import ApiError, RestApiClient, upload_problem
from client.file_model import FileTableModel
from client.ui import busy_cursor
from common.rules import name_key
from common.schemas import FileOut, UserOut


class MainWindow(QMainWindow):
    def __init__(self, api: RestApiClient, user: UserOut):
        super().__init__()
        self.api = api
        self.user = user
        self.logged_out = False  # tells __main__ to show the login window again
        self.setWindowTitle(f"Drive Mini — {user.display_name}")
        self.resize(900, 520)
        self.setAcceptDrops(True)  # drag files from Explorer onto the window to upload

        self.model = FileTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name takes the rest
        self.setCentralWidget(self.table)

        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        toolbar.addAction("Upload…", self.choose_and_upload)
        self.download_action = toolbar.addAction("Download…", self.download_selected)
        self.delete_action = toolbar.addAction("Delete", self.delete_selected)
        toolbar.addSeparator()
        toolbar.addAction("Refresh", self.refresh)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        toolbar.addWidget(QLabel(f"{user.display_name} ({user.username})  "))
        toolbar.addAction("Log out", self.log_out)

        self.table.selectionModel().selectionChanged.connect(self._update_actions)
        self.refresh()

    # --- list ---

    def refresh(self) -> None:
        try:
            with busy_cursor():
                files = self.api.list_files()
        except ApiError as exc:
            self._handle_error(exc)
            return
        self.model.set_files(files)
        self._update_actions()
        self.statusBar().showMessage(f"{len(files)} file(s) · {self.api.base_url}")

    def selected_file(self) -> FileOut | None:
        rows = self.table.selectionModel().selectedRows()
        return self.model.file_at(rows[0].row()) if rows else None

    def _update_actions(self) -> None:
        has_selection = self.selected_file() is not None
        self.download_action.setEnabled(has_selection)
        self.delete_action.setEnabled(has_selection)

    # --- upload (button and drag-n-drop) ---

    def choose_and_upload(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(self, "Upload files")
        self.upload_paths([Path(n) for n in names])

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        # Windows asks again on every mouse move while dragging; without accepting here the
        # cursor shows "not allowed" and the drop is refused.
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        event.acceptProposedAction()
        self.upload_paths(paths)

    def upload_paths(self, paths: list[Path]) -> None:
        """Upload each file; on a taken name ask "Replace?" and send the new content (PUT)."""
        problems, uploaded = [], 0
        for path in paths:
            problem = upload_problem(path)  # shared rules, checked before sending
            if problem:
                problems.append(problem)
                continue
            try:
                with busy_cursor():
                    self.api.upload(path)
                uploaded += 1
            except ApiError as exc:
                if exc.status == 409 and self._ask_replace(path):
                    if self._replace(path, problems):
                        uploaded += 1
                elif exc.status != 409:
                    problems.append(f"{path.name}: {exc.detail}")
        self.refresh()
        if uploaded:
            self.statusBar().showMessage(f"Uploaded {uploaded} file(s).", 5000)
        if problems:
            QMessageBox.warning(self, "Upload", "Some files were not uploaded:\n\n" + "\n".join(problems))

    def _ask_replace(self, path: Path) -> bool:
        answer = QMessageBox.question(
            self, "File already exists",
            f"“{path.name}” already exists on your drive.\nReplace it with this file?")
        return answer == QMessageBox.StandardButton.Yes

    def _replace(self, path: Path, problems: list[str]) -> bool:
        try:
            with busy_cursor():
                # Names match ignoring case, as on the server ("A.js" = "a.js").
                existing = next(f for f in self.api.list_files() if name_key(f.name) == name_key(path.name))
                self.api.replace(existing.id, path)
            return True
        except ApiError as exc:
            problems.append(f"{path.name}: {exc.detail}")
            return False

    # --- download / delete ---

    def download_selected(self) -> None:
        file = self.selected_file()
        if file is None:
            return
        target, _ = QFileDialog.getSaveFileName(self, "Save file",
                                                str(Path.home() / "Downloads" / file.name))
        if not target:
            return
        try:
            with busy_cursor():
                Path(target).write_bytes(self.api.download(file.id))
        except ApiError as exc:
            self._handle_error(exc)
            return
        except OSError as exc:
            QMessageBox.warning(self, "Download", f"Could not save the file:\n{exc}")
            return
        self.statusBar().showMessage(f"Saved to {target}", 5000)

    def delete_selected(self) -> None:
        file = self.selected_file()
        if file is None:
            return
        answer = QMessageBox.question(self, "Delete file",
                                      f"Delete “{file.name}” from your drive?\nThis can't be undone.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            with busy_cursor():
                self.api.delete(file.id)
        except ApiError as exc:
            self._handle_error(exc)
        self.refresh()

    # --- session ---

    def log_out(self) -> None:
        self.api.logout()
        self.logged_out = True
        self.close()

    def _handle_error(self, exc: ApiError) -> None:
        if exc.status == 401:  # token expired (12 h) or server restarted with a new key
            QMessageBox.information(self, "Drive Mini", "Your session has expired. Please log in again.")
            self.log_out()
        else:
            QMessageBox.warning(self, "Drive Mini", exc.detail)
