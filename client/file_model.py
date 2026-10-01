"""The file table's data: one row per file on the virtual disk (Qt table model)."""
from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from client.sorting import FileFilter, SortOrder, filter_files, sort_by_created
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
NAME_COLUMN, CREATED_COLUMN = 0, 1


def format_time(value: datetime) -> str:
    """Server times are UTC; show them in this PC's local time (with seconds, so the
    sort-by-created order is visible even for files uploaded in the same minute)."""
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB"):
        if size < 1024 or unit == "MB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


class FileTableModel(QAbstractTableModel):
    """Keeps all files from the server and shows sort_by_created(filter_files(...)) of them."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_files: list[FileOut] = []
        self._files: list[FileOut] = []  # what the table shows, in display order
        self.sort_order = SortOrder.DESC  # newest first
        self.file_filter = FileFilter.ALL

    def set_files(self, files: list[FileOut]) -> None:
        self._all_files = list(files)
        self._apply()

    def set_sort_order(self, order: SortOrder) -> None:
        self.sort_order = order
        self._apply()
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, CREATED_COLUMN, CREATED_COLUMN)

    def set_filter(self, file_filter: FileFilter) -> None:
        self.file_filter = file_filter
        self._apply()

    def _apply(self) -> None:
        self.beginResetModel()  # also clears the selection, so it can't point at a moved row
        self._files = sort_by_created(filter_files(self._all_files, self.file_filter), self.sort_order)
        self.endResetModel()

    def total_count(self) -> int:
        return len(self._all_files)

    def file_at(self, row: int) -> FileOut:
        return self._files[row]

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._files)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            if section == CREATED_COLUMN:  # the arrow shows the current order
                return "Created ▼" if self.sort_order is SortOrder.DESC else "Created ▲"
            return COLUMNS[section][0]
        if role == Qt.ItemDataRole.ToolTipRole and section == CREATED_COLUMN:
            return f"Sorted {self.sort_order.value}. Click to reverse."
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
