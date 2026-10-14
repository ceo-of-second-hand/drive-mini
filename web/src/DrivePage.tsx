import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, type ApiClient, type FileOut, type UserOut } from "./api";
import { draggingFiles, droppedFiles } from "./dragDrop";
import { deleteFile, downloadFile, uploadFiles } from "./fileActions";
import { formatSize, formatTime } from "./format";
import { FILTERS, filterFiles, sortByCreated, type FileFilter, type SortOrder } from "./sorting";

// The same columns as the desktop table (client/file_model.py). Name always stays visible.
const COLUMNS: { title: string; show: (f: FileOut) => string; className?: string }[] = [
  { title: "Name", show: (f) => f.name },
  { title: "Created", show: (f) => formatTime(f.created_at) },
  { title: "Modified", show: (f) => formatTime(f.modified_at) },
  { title: "Uploader", show: (f) => f.uploader_name },
  { title: "Editor", show: (f) => f.editor_name },
  { title: "Size", show: (f) => formatSize(f.size), className: "size" },
];

/** The user's virtual disk: the top bar with the file actions, the file table and a status line. */
export default function DrivePage({ api, user, onLogout }: { api: ApiClient; user: UserOut; onLogout: () => void }) {
  const [files, setFiles] = useState<FileOut[] | null>(null); // null = not loaded yet
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [error, setError] = useState(""); // shown above the table, in red
  const [notice, setNotice] = useState(""); // shown in the status line, e.g. "Uploaded 2 file(s)."
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false); // files are being dragged over the table
  const picker = useRef<HTMLInputElement>(null);
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc"); // newest first, as on desktop
  const [filter, setFilter] = useState<FileFilter>("all");
  // What the table shows: variant 57's filter, then its sort by creation date.
  const shown = files && sortByCreated(filterFiles(files, filter), sortOrder);
  // Looked up in what's shown, so a deleted or filtered-out file is never "selected".
  const selected = shown?.find((f) => f.id === selectedId) ?? null;

  const refresh = useCallback(async () => {
    try {
      setFiles(await api.listFiles());
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : String(e));
    }
  }, [api]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    // dragover is asked again on every mouse move. Accepting it for the whole page (it bubbles up
    // here from the table too) is what allows the drop at all; without it the browser shows "not
    // allowed" (the Stage 2 bug). The drop handler stops a file dropped next to the table from
    // being opened in the tab, which would leave the app.
    const keep = (e: DragEvent) => {
      if (draggingFiles(e.dataTransfer)) e.preventDefault();
    };
    window.addEventListener("dragover", keep);
    window.addEventListener("drop", keep);
    return () => {
      window.removeEventListener("dragover", keep);
      window.removeEventListener("drop", keep);
    };
  }, []);

  /** Run one action with the buttons disabled; its error (if any) is shown above the table. */
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setBusy(false);
    }
  }

  const upload = (chosen: File[], skipped: string[] = []) => run(async () => {
    const { uploaded, problems } = await uploadFiles(api, chosen);
    problems.unshift(...skipped);
    await refresh();
    if (uploaded) setNotice(`Uploaded ${uploaded} file(s).`);
    if (problems.length) setError(["Some files were not uploaded:", ...problems].join("\n"));
  });

  const download = (file: FileOut) => run(async () => {
    await downloadFile(api, file);
    setNotice(`Downloaded ${file.name}.`);
  });

  const remove = (file: FileOut) => run(async () => {
    if (await deleteFile(api, file)) {
      await refresh();
      setNotice(`Deleted ${file.name}.`);
    }
  });

  return (
    <div className="drive">
      <header className="topbar">
        <strong>Drive Mini</strong>
        <button onClick={() => picker.current?.click()} disabled={busy}>Upload…</button>
        <button onClick={() => selected && void download(selected)} disabled={busy || !selected}>Download</button>
        <button onClick={() => selected && void remove(selected)} disabled={busy || !selected}>Delete</button>
        <button onClick={() => void refresh()} disabled={busy}>Refresh</button>
        <label className="show">
          Show:
          <select value={filter} onChange={(e) => setFilter(e.target.value as FileFilter)}>
            {Object.entries(FILTERS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <span>{user.display_name} ({user.username})</span>
        <button onClick={onLogout}>Log out</button>
        <input ref={picker} type="file" multiple hidden data-testid="file-picker"
               onChange={(e) => {
                 const chosen = Array.from(e.target.files ?? []);
                 e.target.value = ""; // so choosing the same file again still triggers onChange
                 if (chosen.length) void upload(chosen);
               }} />
      </header>

      <main className={dragOver ? "files drag-over" : "files"} data-testid="drop-zone"
            onDragEnter={(e) => { if (draggingFiles(e.dataTransfer)) { e.preventDefault(); setDragOver(true); } }}
            onDragLeave={(e) => {
              // Leaving a row or cell inside the zone also fires dragleave: only react to really leaving it.
              if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragOver(false);
            }}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              if (busy) return;
              const { files: dropped, problems } = droppedFiles(e.dataTransfer);
              if (dropped.length || problems.length) void upload(dropped, problems);
            }}>
        {dragOver && <div className="drop-hint">Drop files to upload them to your drive</div>}
        {error && <p className="error" role="alert">{error}</p>}
        <table>
          <thead>
            <tr>
              {COLUMNS.map((c) => c.title === "Created" ? (
                <th key={c.title} aria-sort={sortOrder === "asc" ? "ascending" : "descending"}>
                  <button className="sort" title={`Sorted ${sortOrder === "asc" ? "oldest" : "newest"} first. Click to reverse.`}
                          onClick={() => setSortOrder(sortOrder === "asc" ? "desc" : "asc")}>
                    Created {sortOrder === "asc" ? "▲" : "▼"}
                  </button>
                </th>
              ) : <th key={c.title} className={c.className}>{c.title}</th>)}
            </tr>
          </thead>
          <tbody>
            {shown?.map((f) => (
              <tr key={f.id} onClick={() => setSelectedId(f.id)} aria-selected={f.id === selectedId}>
                {COLUMNS.map((c) => <td key={c.title} className={c.className}>{c.show(f)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {files?.length === 0 && <p className="muted empty">Your drive is empty.</p>}
        {!!files?.length && shown?.length === 0 && (
          <p className="muted empty">No files match “{FILTERS[filter]}”.</p>
        )}
      </main>

      <footer className="status">
        {files === null || shown === null ? "Loading…"
          : shown.length === files.length ? `${files.length} file(s)` : `${shown.length} of ${files.length} file(s) shown`}
        {notice && ` · ${notice}`}
      </footer>
    </div>
  );
}
