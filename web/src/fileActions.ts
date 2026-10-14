/**
 * Upload, download and delete, with the same questions and messages as the desktop app
 * (client/main_window.py: upload_paths, download_selected, delete_selected).
 */
import { ApiError, type ApiClient, type FileOut } from "./api";
import { MAX_UPLOAD_BYTES, nameKey } from "./rules";

export interface UploadResult {
  uploaded: number;
  problems: string[]; // one line per file that wasn't uploaded
}

const message = (e: unknown) => (e instanceof ApiError ? e.detail : String(e));

/** Upload each file; on a taken name ask "Replace?" and send the new content (PUT). */
export async function uploadFiles(api: ApiClient, files: File[],
                                  ask = (text: string) => window.confirm(text)): Promise<UploadResult> {
  const result: UploadResult = { uploaded: 0, problems: [] };
  for (const file of files) {
    if (file.size > MAX_UPLOAD_BYTES) { // checked before sending, so a big file isn't uploaded for nothing
      result.problems.push(`'${file.name}' is larger than ${MAX_UPLOAD_BYTES / (1024 * 1024)} MB.`);
      continue;
    }
    try {
      await api.upload(file);
      result.uploaded++;
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 409)) {
        result.problems.push(`${file.name}: ${message(e)}`);
      } else if (ask(`“${file.name}” already exists on your drive.\nReplace it with this file?`)) {
        try {
          // Names match ignoring case, as on the server ("A.js" = "a.js").
          const existing = (await api.listFiles()).find((f) => nameKey(f.name) === nameKey(file.name));
          if (!existing) throw new Error("it was deleted meanwhile, try again");
          await api.replace(existing.id, file);
          result.uploaded++;
        } catch (e2) {
          result.problems.push(`${file.name}: ${message(e2)}`);
        }
      }
    }
  }
  return result;
}

/** Fetch the file (the request needs the login token, so a plain link can't do it) and hand it to
 *  the browser as a download with its real name. Where it's saved is up to the browser's settings. */
export async function downloadFile(api: ApiClient, file: FileOut): Promise<void> {
  const url = URL.createObjectURL(await api.download(file.id));
  const link = document.createElement("a");
  link.href = url;
  link.download = file.name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Ask first; true if the file was deleted. */
export async function deleteFile(api: ApiClient, file: FileOut,
                                 ask = (text: string) => window.confirm(text)): Promise<boolean> {
  if (!ask(`Delete “${file.name}” from your drive?\nThis can't be undone.`)) return false;
  await api.delete(file.id);
  return true;
}
