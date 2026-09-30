"""Start the desktop client: python -m client"""
import sys

from PySide6.QtWidgets import QApplication, QDialog

from client.login_dialog import LoginDialog
from client.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Drive Mini")
    while True:  # log out → back to the login window
        login = LoginDialog()
        if login.exec() != QDialog.DialogCode.Accepted:
            return 0
        window = MainWindow(login.api, login.user)
        window.show()
        app.exec()
        if not window.logged_out:
            return 0


if __name__ == "__main__":
    sys.exit(main())
