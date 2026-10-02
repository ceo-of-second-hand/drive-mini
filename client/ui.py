"""Small UI helpers shared by the windows."""
from contextlib import contextmanager

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication


def settings() -> QSettings:
    """Remembered between runs: server address, last username, sync folder. Never secrets.

    An INI file in %APPDATA%\\DriveMini\\ (next to the sync snapshots), not the registry.
    """
    return QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "DriveMini", "client")


def short_path(path, label, width: int = 420) -> str:
    """Long folder paths shortened in the middle ("C:\\Users\\…\\my-drive") to fit `width` pixels."""
    return label.fontMetrics().elidedText(str(path), Qt.TextElideMode.ElideMiddle, width)


@contextmanager
def busy_cursor():
    """Wait cursor while a (short) server call runs."""
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()
