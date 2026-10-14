import { describe, expect, test, vi } from "vitest";
import { ApiError, type ApiClient, type FileOut } from "./api";
import { deleteFile, uploadFiles } from "./fileActions";

const existing = { id: 7, name: "App.js" } as FileOut;
const taken = new ApiError(409, "A file named 'app.js' already exists. Replace it instead.");

function fakeApi(upload: () => Promise<unknown>) {
  return {
    upload: vi.fn(upload),
    replace: vi.fn().mockResolvedValue(existing),
    listFiles: vi.fn().mockResolvedValue([{ id: 1, name: "other.c" }, existing]),
    delete: vi.fn().mockResolvedValue(undefined),
  } as unknown as ApiClient & Record<"upload" | "replace" | "delete", ReturnType<typeof vi.fn>>;
}

describe("uploadFiles", () => {
  test("new files are uploaded", async () => {
    const api = fakeApi(async () => ({}));
    const files = [new File(["a"], "a.js"), new File(["b"], "b.png")];
    expect(await uploadFiles(api, files)).toEqual({ uploaded: 2, problems: [] });
    expect(api.upload).toHaveBeenCalledTimes(2);
  });

  test("a taken name asks, and Yes replaces the existing file (matched ignoring case)", async () => {
    const api = fakeApi(async () => { throw taken; });
    const ask = vi.fn().mockReturnValue(true);
    const file = new File(["v2"], "app.js");

    expect(await uploadFiles(api, [file], ask)).toEqual({ uploaded: 1, problems: [] });
    expect(ask).toHaveBeenCalledWith("“app.js” already exists on your drive.\nReplace it with this file?");
    expect(api.replace).toHaveBeenCalledWith(7, file); // the id of "App.js"
  });

  test("No keeps the existing file and reports nothing", async () => {
    const api = fakeApi(async () => { throw taken; });
    expect(await uploadFiles(api, [new File(["v2"], "app.js")], () => false)).toEqual({ uploaded: 0, problems: [] });
    expect(api.replace).not.toHaveBeenCalled();
  });

  test("a file over 50 MB is refused before sending; other errors are listed per file", async () => {
    const api = fakeApi(async () => { throw new ApiError(422, "File name contains characters that are not allowed: :"); });
    const big = new File(["x"], "video.mp4");
    Object.defineProperty(big, "size", { value: 60 * 1024 * 1024 });

    const result = await uploadFiles(api, [big, new File(["x"], "a:b.js")]);
    expect(result.uploaded).toBe(0);
    expect(result.problems).toEqual(["'video.mp4' is larger than 50 MB.",
                                     "a:b.js: File name contains characters that are not allowed: :"]);
    expect(api.upload).toHaveBeenCalledTimes(1); // only a:b.js reached the server
  });
});

describe("deleteFile", () => {
  test("asks first; only Yes deletes", async () => {
    const api = fakeApi(async () => ({}));
    const ask = vi.fn().mockReturnValueOnce(false).mockReturnValueOnce(true);

    expect(await deleteFile(api, existing, ask)).toBe(false);
    expect(api.delete).not.toHaveBeenCalled();
    expect(await deleteFile(api, existing, ask)).toBe(true);
    expect(api.delete).toHaveBeenCalledWith(7);
    expect(ask).toHaveBeenCalledWith("Delete “App.js” from your drive?\nThis can't be undone.");
  });
});
