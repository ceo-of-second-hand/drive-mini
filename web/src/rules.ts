/**
 * The few shared rules the web client needs, mirrored from common/rules.py by hand: the shared
 * contract (openapi.json) describes data, not functions. Validation itself stays on the server.
 */

export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024; // 50 MB, as MAX_UPLOAD_BYTES in common/rules.py

/** Case-insensitive form of a file name: 'A.js' and 'a.js' are the same file (name_key in Python). */
export const nameKey = (name: string): string => name.toLowerCase();

/** Lower-case extension without the dot: 'photo.JPG' -> 'jpg'; 'Makefile' and '.c' -> '' (file_extension in Python). */
export function fileExtension(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : "";
}
