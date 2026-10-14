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
  expect(headers).toEqual(["Name", "Created", "Modified", "Uploader", "Editor", "Size"]);
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

test("Log out is passed up to the app", async () => {
  fakeServer({ "/files": [] });
  const onLogout = renderDrive();
  await userEvent.click(screen.getByRole("button", { name: "Log out" }));
  expect(onLogout).toHaveBeenCalledOnce();
});
