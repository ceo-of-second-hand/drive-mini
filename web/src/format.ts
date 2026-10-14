/** How the file table shows times and sizes: the same as the desktop table (client/file_model.py). */

const pad = (n: number) => String(n).padStart(2, "0");

/** Server times are UTC; show them in this computer's local time, with seconds (so the
 *  sort-by-created order is visible even for files uploaded in the same minute). */
export function formatTime(iso: string): string {
  const t = new Date(iso);
  return `${t.getFullYear()}-${pad(t.getMonth() + 1)}-${pad(t.getDate())} ` +
    `${pad(t.getHours())}:${pad(t.getMinutes())}:${pad(t.getSeconds())}`;
}

export function formatSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}
