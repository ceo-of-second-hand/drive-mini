import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { ApiClient, type FileOut } from "./api";
import Preview, { previewKind } from "./Preview";
import { fakeServer, reply } from "./test-server";

function file(id: number, name: string, size = 100): FileOut {
  return { id, name, size, extension: "", mime_type: "", created_at: "2026-10-02T09:00:00Z",
           modified_at: "2026-10-02T09:00:00Z", uploader_name: "I", editor_name: "I" };
}

const contentRequests = (fetchMock: ReturnType<typeof fakeServer>) =>
  fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/content"));

test("variant 57: .js is text, .png is an image, nothing else is previewed (any letter case)", () => {
  expect(["app.js", "APP.JS", "logo.png", "Logo.PNG", "photo.jpg", "main.c", "notes.txt", "js"].map(previewKind))
    .toEqual(["text", "text", "image", "image", null, null, null, null]);
});

test("nothing selected: a hint", () => {
  render(<Preview api={new ApiClient()} file={null} />);
  expect(screen.getByText(/Select a file to preview it/)).toBeInTheDocument();
});

test("a .js file is shown as text", async () => {
  fakeServer({ "/files/1/content": new Response("console.log('Привіт');") });
  render(<Preview api={new ApiClient()} file={file(1, "app.js")} />);
  expect(await screen.findByTestId("text-preview")).toHaveTextContent("console.log('Привіт');");
});

test("a .png file is shown as an image; a broken one gets a message", async () => {
  fakeServer({ "/files/2/content": new Response("not really a png") });
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => "blob:logo"), revokeObjectURL: vi.fn() }));
  render(<Preview api={new ApiClient()} file={file(2, "logo.png")} />);

  const img = await screen.findByRole("img", { name: "logo.png" });
  expect(img).toHaveAttribute("src", "blob:logo");
  fireEvent.error(img); // the browser couldn't decode it
  expect(screen.getByText("“logo.png” can't be shown: it isn't a valid PNG image.")).toBeInTheDocument();
});

test("other types get a message and aren't downloaded", () => {
  const fetchMock = fakeServer({});
  render(<Preview api={new ApiClient()} file={file(3, "photo.jpg")} />);
  expect(screen.getByText(/No preview for “photo.jpg”/)).toBeInTheDocument();
  expect(contentRequests(fetchMock)).toHaveLength(0);
});

test("files over 2 MB aren't downloaded just to preview them", () => {
  const fetchMock = fakeServer({});
  render(<Preview api={new ApiClient()} file={file(4, "bundle.js", 3 * 1024 * 1024)} />);
  expect(screen.getByText(/“bundle.js” is too large to preview/)).toBeInTheDocument();
  expect(contentRequests(fetchMock)).toHaveLength(0);
});

test("a server error is shown in the panel", async () => {
  fakeServer({ "/files/5/content": reply(404, { detail: "File not found." }) });
  render(<Preview api={new ApiClient()} file={file(5, "gone.js")} />);
  expect(await screen.findByText("Preview failed: File not found.")).toBeInTheDocument();
});

test("a quick click on another file never shows the first file's content", async () => {
  let release: (r: Response) => void = () => {};
  const slow = new Promise<Response>((resolve) => { release = resolve; });
  vi.stubGlobal("fetch", vi.fn((url: string) =>
    url === "/files/1/content" ? slow : Promise.resolve(new Response("second file"))));
  const api = new ApiClient();
  const { rerender } = render(<Preview api={api} file={file(1, "first.js")} />);
  rerender(<Preview api={api} file={file(2, "second.js")} />);
  expect(await screen.findByText("second file")).toBeInTheDocument();

  release(new Response("FIRST FILE")); // the slow answer for the first file arrives late
  await new Promise((r) => setTimeout(r, 20));
  expect(screen.getByTestId("text-preview")).toHaveTextContent("second file");
});
