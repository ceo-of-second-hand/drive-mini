import { useCallback, useEffect, useState } from "react";
import { ApiError, type ApiClient, type FileOut, type UserOut } from "./api";
import { formatSize, formatTime } from "./format";

// The same columns as the desktop table (client/file_model.py). Name always stays visible.
const COLUMNS: { title: string; show: (f: FileOut) => string; className?: string }[] = [
  { title: "Name", show: (f) => f.name },
  { title: "Created", show: (f) => formatTime(f.created_at) },
  { title: "Modified", show: (f) => formatTime(f.modified_at) },
  { title: "Uploader", show: (f) => f.uploader_name },
  { title: "Editor", show: (f) => f.editor_name },
  { title: "Size", show: (f) => formatSize(f.size), className: "size" },
];

/** The user's virtual disk: the top bar and the file table. */
export default function DrivePage({ api, user, onLogout }: { api: ApiClient; user: UserOut; onLogout: () => void }) {
  const [files, setFiles] = useState<FileOut[] | null>(null); // null = not loaded yet
  const [error, setError] = useState("");

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

  return (
    <div className="drive">
      <header className="topbar">
        <strong>Drive Mini</strong>
        <button onClick={() => void refresh()}>Refresh</button>
        <span>{user.display_name} ({user.username})</span>
        <button onClick={onLogout}>Log out</button>
      </header>

      <main className="files">
        {error && <p className="error" role="alert">{error}</p>}
        <table>
          <thead>
            <tr>{COLUMNS.map((c) => <th key={c.title} className={c.className}>{c.title}</th>)}</tr>
          </thead>
          <tbody>
            {files?.map((f) => (
              <tr key={f.id}>
                {COLUMNS.map((c) => <td key={c.title} className={c.className}>{c.show(f)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
        {files?.length === 0 && <p className="muted empty">Your drive is empty.</p>}
      </main>

      <footer className="status">{files === null ? "Loading…" : `${files.length} file(s)`}</footer>
    </div>
  );
}
