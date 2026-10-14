/**
 * Variant 57 on the web: sort by creation date and the .c/.jpg filter.
 *
 * A TypeScript copy of client/sorting.py (the browser can't run Python). The two copies are kept
 * equal by common/variant_cases.json: the same cases are checked by pytest and by Vitest.
 */
import { fileExtension } from "./rules";

export type SortOrder = "asc" | "desc"; // oldest first / newest first

export const FILTERS = {
  all: "All files",
  c_jpg: "Only .c and .jpg",
} as const;
export type FileFilter = keyof typeof FILTERS;

const C_JPG_EXTENSIONS = new Set(["c", "jpg"]); // exactly as the variant says (.jpeg, .cpp etc. don't count)

interface HasIdAndCreated {
  id: number;
  name: string;
  created_at: string; // ISO time from the server
}

/** Files by creation date. Equal dates fall back to id, so the order is always stable. */
export function sortByCreated<F extends HasIdAndCreated>(files: readonly F[], order: SortOrder): F[] {
  const sign = order === "asc" ? 1 : -1;
  return [...files].sort((a, b) =>
    sign * (Date.parse(a.created_at) - Date.parse(b.created_at) || a.id - b.id));
}

/** All files, or only .c and .jpg (extension case doesn't matter: photo.JPG counts). */
export function filterFiles<F extends HasIdAndCreated>(files: readonly F[], filter: FileFilter): F[] {
  return filter === "all" ? [...files] : files.filter((f) => C_JPG_EXTENSIONS.has(fileExtension(f.name)));
}
