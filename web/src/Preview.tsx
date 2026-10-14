/**
 * Preview panel on the right of the table (variant 57): .js as text, .png as an image; other types
 * get a short message. The same rules and messages as the desktop's client/preview.py.
 */
import { useEffect, useState } from "react";
import { ApiError, type ApiClient, type FileOut } from "./api";
import { fileExtension } from "./rules";

export const PREVIEW_MAX_BYTES = 2 * 1024 * 1024; // bigger files aren't downloaded just to preview them

/** 'text', 'image' or null (no preview for this type). */
export function previewKind(name: string): "text" | "image" | null {
  return ({ js: "text", png: "image" } as const)[fileExtension(name) as "js" | "png"] ?? null;
}

type View =
  | { kind: "message"; text: string }
  | { kind: "loading" }
  | { kind: "text"; text: string }
  | { kind: "image"; url: string };

function viewBeforeLoading(file: FileOut | null): View | null {
  if (!file) return { kind: "message", text: "Select a file to preview it.\n(.js as text, .png as image)" };
  if (!previewKind(file.name)) {
    return { kind: "message", text: `No preview for “${file.name}”.\nOnly .js and .png files are previewed.` };
  }
  if (file.size > PREVIEW_MAX_BYTES) {
    return { kind: "message", text: `“${file.name}” is too large to preview.\nUse Download instead.` };
  }
  return null; // needs the file's content
}

export default function Preview({ api, file }: { api: ApiClient; file: FileOut | null }) {
  const [view, setView] = useState<View>({ kind: "loading" });

  useEffect(() => {
    const early = viewBeforeLoading(file);
    if (early || !file) {
      setView(early!);
      return;
    }
    let current = true; // a quick click on another row must not show this file's content later
    let imageUrl = "";
    setView({ kind: "loading" });
    api.download(file.id)
      .then(async (blob) => {
        if (!current) return;
        if (previewKind(file.name) === "text") {
          setView({ kind: "text", text: await blob.text() }); // UTF-8; broken bytes become �
        } else {
          imageUrl = URL.createObjectURL(blob);
          setView({ kind: "image", url: imageUrl });
        }
      })
      .catch((e) => current && setView({ kind: "message", text: `Preview failed: ${e instanceof ApiError ? e.detail : e}` }));
    return () => {
      current = false;
      if (imageUrl) URL.revokeObjectURL(imageUrl);
    };
  }, [api, file]);

  return (
    <aside className="preview" aria-label="Preview">
      {view.kind === "message" && <p className="muted message">{view.text}</p>}
      {view.kind === "loading" && <p className="muted message">Loading preview…</p>}
      {view.kind === "text" && <pre data-testid="text-preview">{view.text}</pre>}
      {view.kind === "image" && (
        <img src={view.url} alt={file?.name}
             onError={() => setView({ kind: "message", text: `“${file?.name}” can't be shown: it isn't a valid PNG image.` })} />
      )}
    </aside>
  );
}
