import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { ApiClient, type FileOut } from "./api";
import DrivePage from "./DrivePage";
import { formatTime } from "./format";
import { fakeServer, inOrder, reply } from "./test-server";

const USER = { id: 1, username: "ivanka", display_name: "Ivanka" };

function file(id: number, name: string, extra: Partial<FileOut> = {}): FileOut {
  return { id, name, extension: name.split(".").pop() ?? "", size: 2048, mime_type: "text/plain",
           created_at: "2026-10-02T09:00:00Z", modified_at: "2026-10-03T10:30:15Z",
           uploader_name: "Ivanka", editor_name: "Bob", ...extra };
}

function renderDrive() {
  const onLogout = vi.fn();
  render(<DrivePage api={new ApiClient()} user={USER} onLogout={onLogout} />);
  return onLogout;
}

test("the table shows every attribute of each file", async () => {
  fakeServer({ "/files": [file(1, "app.js")] });
  renderDrive();

  const row = (await screen.findByText("app.js")).closest("tr")!;
  const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
  expect(headers).toEqual(["Name", "Created ▼", "Modified", "Uploader", "Editor", "Size"]);
  const cells = within(row).getAllByRole("cell").map((c) => c.textContent);
  expect(cells).toEqual(["app.js", formatTime("2026-10-02T09:00:00Z"), formatTime("2026-10-03T10:30:15Z"),
                         "Ivanka", "Bob", "2.0 KB"]);
  expect(screen.getByText("1 file(s)")).toBeInTheDocument();
});

test("an empty drive says so", async () => {
  fakeServer({ "/files": [] });
  renderDrive();
  expect(await screen.findByText("Your drive is empty.")).toBeInTheDocument();
  expect(screen.getByText("0 file(s)")).toBeInTheDocument();
});

test("Refresh loads the list again", async () => {
  fakeServer({ "/files": inOrder([file(1, "a.js")], [file(1, "a.js"), file(2, "b.png")]) });
  renderDrive();
  await screen.findByText("a.js");
  expect(screen.queryByText("b.png")).toBeNull();

  await userEvent.click(screen.getByRole("button", { name: "Refresh" }));
  expect(await screen.findByText("b.png")).toBeInTheDocument();
  expect(screen.getByText("2 file(s)")).toBeInTheDocument();
});

test("a server error is shown instead of the list", async () => {
  fakeServer({ "/files": reply(500, { detail: "Database is locked." }) });
  renderDrive();
  expect(await screen.findByRole("alert")).toHaveTextContent("Database is locked.");
});

test("Download and Delete need a selected row", async () => {
  fakeServer({ "/files": [file(1, "a.js")] });
  renderDrive();
  await userEvent.click(await screen.findByText("a.js"));
  expect(screen.getByRole("button", { name: "Download" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Delete" })).toBeEnabled();
  expect(screen.getByText("a.js").closest("tr")).toHaveAttribute("aria-selected", "true");
});

test("nothing selected: Download and Delete are disabled", async () => {
  fakeServer({ "/files": [file(1, "a.js")] });
  renderDrive();
  await screen.findByText("a.js");
  expect(screen.getByRole("button", { name: "Download" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
});

test("Upload sends the chosen files, refreshes the list and says how many", async () => {
  const fetchMock = fakeServer({ "GET /files": inOrder([], [file(1, "notes.txt")]), "POST /files": file(1, "notes.txt") });
  renderDrive();
  await screen.findByText("Your drive is empty.");

  await userEvent.upload(screen.getByTestId("file-picker"), new File(["hello"], "notes.txt"));
  expect(await screen.findByText("notes.txt")).toBeInTheDocument();
  expect(screen.getByText("1 file(s) · Uploaded 1 file(s).")).toBeInTheDocument();
  const [, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "POST")!;
  expect((init!.body as FormData).get("file")).toHaveProperty("name", "notes.txt");
});

test("a failed upload is listed above the table", async () => {
  fakeServer({ "GET /files": [], "POST /files": reply(422, { detail: "'CON' is a reserved name on Windows." }) });
  renderDrive();
  await screen.findByText("Your drive is empty.");
  await userEvent.upload(screen.getByTestId("file-picker"), new File(["x"], "CON"));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Some files were not uploaded: CON: 'CON' is a reserved name on Windows.");
});

test("Download hands the file to the browser under its real name", async () => {
  fakeServer({ "/files": [file(3, "app.js")], "/files/3/content": new Response("console.log(1)") });
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() }));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  renderDrive();

  await userEvent.click(await screen.findByText("app.js"));
  await userEvent.click(screen.getByRole("button", { name: "Download" }));
  expect(await screen.findByText("1 file(s) · Downloaded app.js.")).toBeInTheDocument();
  const link = click.mock.contexts[0] as HTMLAnchorElement;
  expect(link.download).toBe("app.js");
  expect(link.href).toBe("blob:x");
  click.mockRestore();
});

test("Delete asks, removes the file and refreshes", async () => {
  const fetchMock = fakeServer({ "GET /files": inOrder([file(3, "old.c")], []), "DELETE /files/3": new Response(null, { status: 204 }) });
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderDrive();

  await userEvent.click(await screen.findByText("old.c"));
  await userEvent.click(screen.getByRole("button", { name: "Delete" }));
  expect(await screen.findByText("Your drive is empty.")).toBeInTheDocument();
  expect(confirm).toHaveBeenCalledWith("Delete “old.c” from your drive?\nThis can't be undone.");
  expect(fetchMock.mock.calls.some(([url, init]) => url === "/files/3" && init?.method === "DELETE")).toBe(true);
  expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled(); // the deleted file isn't selected anymore
  confirm.mockRestore();
});

// --- variant 57 in the table ---

const MIXED = [ // ids, names and creation times in different orders
  file(1, "b-middle.js", { created_at: "2026-10-01T11:00:00Z" }),
  file(2, "c-newest.png", { created_at: "2026-10-01T14:00:00Z" }),
  file(3, "a-oldest.c", { created_at: "2026-10-01T09:00:00Z" }),
  file(4, "d-second.jpg", { created_at: "2026-10-01T10:00:00Z" }),
];
const rowNames = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent);

test("newest first by default; clicking Created reverses the order", async () => {
  fakeServer({ "/files": MIXED });
  renderDrive();
  await screen.findByText("a-oldest.c");
  expect(rowNames()).toEqual(["c-newest.png", "b-middle.js", "d-second.jpg", "a-oldest.c"]);

  await userEvent.click(screen.getByRole("button", { name: "Created ▼" }));
  expect(rowNames()).toEqual(["a-oldest.c", "d-second.jpg", "b-middle.js", "c-newest.png"]);
  expect(screen.getByRole("button", { name: "Created ▲" })).toHaveAttribute("title", "Sorted oldest first. Click to reverse.");

  await userEvent.click(screen.getByRole("button", { name: "Created ▲" }));
  expect(rowNames()).toEqual(["c-newest.png", "b-middle.js", "d-second.jpg", "a-oldest.c"]);
});

test("Show: Only .c and .jpg hides the rest and the status line says so", async () => {
  fakeServer({ "/files": MIXED });
  renderDrive();
  await screen.findByText("a-oldest.c");

  await userEvent.selectOptions(screen.getByLabelText("Show:"), "Only .c and .jpg");
  expect(rowNames()).toEqual(["d-second.jpg", "a-oldest.c"]); // still newest first
  expect(screen.getByText("2 of 4 file(s) shown")).toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText("Show:"), "All files");
  expect(rowNames()).toHaveLength(4);
  expect(screen.getByText("4 file(s)")).toBeInTheDocument();
});

test("a selected file that the filter hides can't be downloaded or deleted", async () => {
  fakeServer({ "/files": MIXED });
  renderDrive();
  await userEvent.click(await screen.findByText("b-middle.js"));
  expect(screen.getByRole("button", { name: "Delete" })).toBeEnabled();

  await userEvent.selectOptions(screen.getByLabelText("Show:"), "Only .c and .jpg");
  expect(screen.getByRole("button", { name: "Delete" })).toBeDisabled();
});

test("when the filter hides everything, the table says why", async () => {
  fakeServer({ "/files": [file(1, "app.js")] });
  renderDrive();
  await screen.findByText("app.js");
  await userEvent.selectOptions(screen.getByLabelText("Show:"), "Only .c and .jpg");
  expect(screen.getByText("No files match “Only .c and .jpg”.")).toBeInTheDocument();
  expect(screen.getByText("0 of 1 file(s) shown")).toBeInTheDocument();
});

test("Log out is passed up to the app", async () => {
  fakeServer({ "/files": [] });
  const onLogout = renderDrive();
  await userEvent.click(screen.getByRole("button", { name: "Log out" }));
  expect(onLogout).toHaveBeenCalledOnce();
});
