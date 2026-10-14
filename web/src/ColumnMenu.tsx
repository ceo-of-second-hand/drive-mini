/** Right-click menu on the table header: show or hide columns. Name always stays (greyed out). */
import { useEffect } from "react";

export const NAME_COLUMN = "Name";

export function loadHidden(username: string): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(`driveMini.hiddenColumns.${username}`) ?? "[]"));
  } catch {
    return new Set(); // a broken value just means "all columns visible"
  }
}

export function saveHidden(username: string, hidden: Set<string>): void {
  localStorage.setItem(`driveMini.hiddenColumns.${username}`, JSON.stringify([...hidden]));
}

export default function ColumnMenu({ titles, hidden, at, onToggle, onClose }: {
  titles: string[];
  hidden: Set<string>;
  at: { x: number; y: number };
  onToggle: (title: string) => void;
  onClose: () => void;
}) {
  useEffect(() => {
    const closeOnEscape = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", closeOnEscape);
    window.addEventListener("click", onClose); // a click anywhere else closes it
    return () => {
      window.removeEventListener("keydown", closeOnEscape);
      window.removeEventListener("click", onClose);
    };
  }, [onClose]);

  return (
    <div className="column-menu" role="menu" style={{ left: at.x, top: at.y }} onClick={(e) => e.stopPropagation()}>
      {titles.map((title) => (
        <label key={title} role="menuitemcheckbox" aria-checked={!hidden.has(title)}>
          <input type="checkbox" checked={!hidden.has(title)} disabled={title === NAME_COLUMN}
                 onChange={() => onToggle(title)} />
          {title}
        </label>
      ))}
    </div>
  );
}
