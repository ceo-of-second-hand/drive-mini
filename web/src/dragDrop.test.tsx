import { createEvent, fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { ApiClient } from "./api";
import DrivePage from "./DrivePage";
import { fakeServer, inOrder } from "./test-server";

const USER = { id: 1, username: "ivanka", display_name: "Ivanka" };

/** What the browser hands over when files (or a folder) are dragged from Explorer. */
function transfer(files: File[], folders: string[] = []) {
  const items = [
    ...files.map((f) => ({ kind: "file", getAsFile: () => f, webkitGetAsEntry: () => ({ isDirectory: false, name: f.name }) })),
    ...folders.map((name) => ({ kind: "file", getAsFile: () => null, webkitGetAsEntry: () => ({ isDirectory: true, name }) })),
  ];
  return { types: ["Files"], files, items };
}

async function renderDrive() {
  render(<DrivePage api={new ApiClient()} user={USER} onLogout={() => {}} />);
  await screen.findByText(/file\(s\)/);
  return screen.getByTestId("drop-zone");
}

test("the drop zone accepts every dragover, so the browser allows the drop", async () => {
  fakeServer({ "GET /files": [] });
  const zone = await renderDrive();
  // The web twin of the Stage 2 bug: an unhandled dragover means "drop not allowed".
  for (let move = 0; move < 3; move++) {
    const dragover = createEvent.dragOver(zone, { dataTransfer: transfer([new File(["x"], "a.js")]) });
    fireEvent(zone, dragover);
    expect(dragover.defaultPrevented).toBe(true);
  }
});

test("dragging text (not files) is left alone", async () => {
  fakeServer({ "GET /files": [] });
  const zone = await renderDrive();
  const dragover = createEvent.dragOver(zone, { dataTransfer: { types: ["text/plain"], items: [], files: [] } });
  fireEvent(zone, dragover);
  expect(dragover.defaultPrevented).toBe(false);
});

test("dragging files over the table shows a hint, which goes away when they leave", async () => {
  fakeServer({ "GET /files": [] });
  const zone = await renderDrive();
  fireEvent.dragEnter(zone, { dataTransfer: transfer([new File(["x"], "a.js")]) });
  expect(screen.getByText("Drop files to upload them to your drive")).toBeInTheDocument();
  fireEvent.dragLeave(zone, { relatedTarget: document.body });
  expect(screen.queryByText("Drop files to upload them to your drive")).toBeNull();
});

test("dropped files are uploaded like chosen ones; a dropped folder is skipped with a message", async () => {
  const fetchMock = fakeServer({
    "GET /files": inOrder([], [{ id: 1, name: "a.js" }, { id: 2, name: "b.png" }]),
    "POST /files": { id: 1, name: "a.js" },
  });
  const zone = await renderDrive();
  fireEvent.dragEnter(zone, { dataTransfer: transfer([new File(["x"], "a.js")]) });
  const drop = createEvent.drop(zone, {
    dataTransfer: transfer([new File(["x"], "a.js"), new File(["y"], "b.png")], ["photos"]),
  });
  fireEvent(zone, drop);

  expect(drop.defaultPrevented).toBe(true); // the browser must not open the files itself
  expect(await screen.findByText("2 file(s) · Uploaded 2 file(s).")).toBeInTheDocument();
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(2);
  expect(screen.getByRole("alert")).toHaveTextContent("photos: folders can't be uploaded, only files");
  expect(screen.queryByText("Drop files to upload them to your drive")).toBeNull();
});

test("a file dropped outside the table doesn't make the browser leave the app", async () => {
  fakeServer({ "GET /files": [] });
  await renderDrive();
  const drop = createEvent.drop(window, { dataTransfer: transfer([new File(["x"], "a.js")]) });
  fireEvent(window, drop);
  expect(drop.defaultPrevented).toBe(true);
});
