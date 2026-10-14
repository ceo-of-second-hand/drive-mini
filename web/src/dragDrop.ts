/**
 * Drag-and-drop upload from Explorer (the bonus feature).
 *
 * The web twin of the Stage 2 bug: the page must call preventDefault() on EVERY dragover,
 * otherwise the browser refuses the drop (the "not allowed" cursor) and, if the file is dropped
 * anyway, opens it in the tab instead of uploading it. On desktop the same thing was the missing
 * dragMoveEvent in client/main_window.py. DrivePage does it once, for the whole window.
 */

/** True if what's being dragged includes files (not, say, selected text). */
export function draggingFiles(transfer: DataTransfer | null): boolean {
  return !!transfer && Array.from(transfer.types).includes("Files");
}

/** The dropped files, and one line for each dropped folder (folders can't be uploaded: the drive is flat). */
export function droppedFiles(transfer: DataTransfer): { files: File[]; problems: string[] } {
  const files: File[] = [];
  const problems: string[] = [];
  const items = Array.from(transfer.items ?? []);
  if (items.length) {
    for (const item of items) {
      if (item.kind !== "file") continue;
      const entry = item.webkitGetAsEntry?.(); // the only way to tell a folder from a file here
      if (entry?.isDirectory) {
        problems.push(`${entry.name}: folders can't be uploaded, only files`);
        continue;
      }
      const file = item.getAsFile();
      if (file) files.push(file);
    }
  } else {
    files.push(...Array.from(transfer.files)); // browsers without .items
  }
  return { files, problems };
}
