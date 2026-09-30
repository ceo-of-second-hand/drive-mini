"""Login window, with a small Register form behind a button."""
from pydantic import ValidationError
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout)

from client.api import DEFAULT_SERVER, ApiError, RestApiClient
from client.ui import busy_cursor, settings
from common.schemas import RegisterIn, UserOut

# Friendlier wording for the client-side pre-check than pydantic's defaults.
FIELD_HINTS = {
    "username": "Username: 3–32 characters, only letters, digits and _ . -",
    "display_name": "Display name: 1–64 characters.",
}


def _error_label() -> QLabel:
    label = QLabel()
    label.setStyleSheet("color: #c0392b;")
    label.setWordWrap(True)
    label.hide()
    return label


def _show_error(label: QLabel, text: str) -> None:
    label.setText(text)
    label.show()


class RegisterDialog(QDialog):
    """Create an account. Input is pre-checked with the shared RegisterIn schema."""

    def __init__(self, api: RestApiClient, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Register — Drive Mini")
        self.setMinimumWidth(380)
        self.api = api
        self.username = QLineEdit()
        self.display_name = QLineEdit()
        self.password = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.error = _error_label()

        form = QFormLayout()
        form.addRow("Username", self.username)
        form.addRow("Display name", self.display_name)
        form.addRow("Password", self.password)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton("Create account", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self._register)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addWidget(buttons)

    def _register(self) -> None:
        try:
            body = RegisterIn(username=self.username.text(), display_name=self.display_name.text(),
                              password=self.password.text())
        except ValidationError as exc:
            field = str(exc.errors()[0]["loc"][0])
            message = exc.errors()[0]["msg"].removeprefix("Value error, ")
            _show_error(self.error, FIELD_HINTS.get(field, message))
            return
        try:
            with busy_cursor():
                self.api.register(body.username, body.display_name, body.password)
        except ApiError as exc:
            _show_error(self.error, exc.detail)
            return
        self.accept()


class LoginDialog(QDialog):
    """Ask for server, username and password. On success, .api and .user are set."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log in — Drive Mini")
        self.setMinimumWidth(380)
        self.api: RestApiClient | None = None
        self.user: UserOut | None = None

        saved = settings()
        self.server = QLineEdit(saved.value("server_url", DEFAULT_SERVER))
        self.username = QLineEdit(saved.value("last_username", ""))
        self.password = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.error = _error_label()

        form = QFormLayout()
        form.addRow("Server", self.server)
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)

        register = QPushButton("Register…")
        register.clicked.connect(self._open_register)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton("Log in", QDialogButtonBox.ButtonRole.AcceptRole).setDefault(True)
        buttons.addButton(register, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.accepted.connect(self._login)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Drive Mini</b> — your files on a remote server"))
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addWidget(buttons)
        (self.password if self.username.text() else self.username).setFocus()

    def _client(self) -> RestApiClient:
        return RestApiClient(self.server.text().strip() or DEFAULT_SERVER)

    def _login(self, username: str | None = None, password: str | None = None) -> None:
        api = self._client()
        try:
            with busy_cursor():
                user = api.login(username or self.username.text().strip(),
                                 password or self.password.text())
        except ApiError as exc:
            _show_error(self.error, exc.detail)
            return
        self.api, self.user = api, user
        saved = settings()
        saved.setValue("server_url", api.base_url.rstrip("/"))
        saved.setValue("last_username", user.username)
        self.accept()

    def _open_register(self) -> None:
        dialog = RegisterDialog(self._client(), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Log straight in with the new account.
            self._login(dialog.username.text().strip(), dialog.password.text())
