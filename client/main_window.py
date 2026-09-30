"""Main window (FileListView): the user's virtual disk as a table."""
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QLabel, QMainWindow, QMessageBox,
                               QSizePolicy, QTableView, QToolBar, QWidget)

from client.api import ApiError, RestApiClient
from client.file_model import FileTableModel
from client.ui import busy_cursor
from common.schemas import UserOut


class MainWindow(QMainWindow):
    def __init__(self, api: RestApiClient, user: UserOut):
        super().__init__()
        self.api = api
        self.user = user
        self.logged_out = False  # tells __main__ to show the login window again
        self.setWindowTitle(f"Drive Mini — {user.display_name}")
        self.resize(900, 520)

        self.model = FileTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name takes the rest
        self.setCentralWidget(self.table)

        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        toolbar.addAction("Refresh", self.refresh)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        toolbar.addWidget(QLabel(f"{user.display_name} ({user.username})  "))
        toolbar.addAction("Log out", self.log_out)

        self.refresh()

    def refresh(self) -> None:
        try:
            with busy_cursor():
                files = self.api.list_files()
        except ApiError as exc:
            self._handle_error(exc)
            return
        self.model.set_files(files)
        self.statusBar().showMessage(f"{len(files)} file(s) · {self.api.base_url}")

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
