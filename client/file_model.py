"""The file table's data: one row per file on the virtual disk (Qt table model)."""
from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from common.schemas import FileOut

# (header, FileOut attribute). Name is column 0 and always stays visible.
COLUMNS = [
    ("Name", "name"),
    ("Created", "created_at"),
    ("Modified", "modified_at"),
    ("Uploader", "uploader_name"),
    ("Editor", "editor_name"),
    ("Size", "size"),
]


def format_time(value: datetime) -> str:
    """Server times are UTC; show them in this PC's local time."""
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB"):
        if size < 1024 or unit == "MB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


class FileTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._files: list[FileOut] = []

    def set_files(self, files: list[FileOut]) -> None:
        self.beginResetModel()
        self._files = list(files)
        self.endResetModel()

    def file_at(self, row: int) -> FileOut:
        return self._files[row]

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._files)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section][0]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        value = getattr(self._files[index.row()], COLUMNS[index.column()][1])
        if role == Qt.ItemDataRole.DisplayRole:
            if isinstance(value, datetime):
                return format_time(value)
            if COLUMNS[index.column()][1] == "size":
                return format_size(value)
            return value
        if role == Qt.ItemDataRole.ToolTipRole and isinstance(value, datetime):
            return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        if role == Qt.ItemDataRole.TextAlignmentRole and COLUMNS[index.column()][1] == "size":
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None
