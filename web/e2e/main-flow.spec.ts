/**
 * The main flow in a real browser, with real clicks, against the real server (temporary database):
 * register, upload, sort by creation date, filter, preview, hide a column, delete, log out and in.
 * The unit tests run in a simulated browser; this one catches what only a real browser shows.
 */
import { expect, test, type Page } from "@playwright/test";

// The Name cells, top to bottom. expect(...).toHaveText waits until they match (lists load async).
const nameCells = (page: Page) => page.locator("tbody tr td:first-child");

async function upload(page: Page, name: string, content: string) {
  await page.getByTestId("file-picker").setInputFiles({ name, mimeType: "text/plain", buffer: Buffer.from(content) });
  await expect(page.getByText(/Uploaded 1 file\(s\)\./)).toBeVisible();
}

test("register, upload, sort, filter, preview, columns, delete, log out and in", async ({ page }) => {
  // Register: a new account goes straight to its (empty) drive.
  await page.goto("/");
  await page.getByRole("button", { name: "Register…" }).click();
  await page.getByLabel("Username").fill("e2e");
  await page.getByLabel("Display name").fill("E2E User");
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText("E2E User (e2e)")).toBeVisible();
  await expect(page.getByText("Your drive is empty.")).toBeVisible();

  // Upload two files one after the other, so their creation times differ.
  await upload(page, "old.c", "int main(void) { return 0; }");
  await upload(page, "new.js", "console.log('Drive Mini');");

  // Variant 57: newest first by default; one click on Created gives oldest first.
  await expect(nameCells(page)).toHaveText(["new.js", "old.c"]);
  await page.getByRole("button", { name: "Created ▼" }).click();
  await expect(nameCells(page)).toHaveText(["old.c", "new.js"]);

  // Variant 57: the .c / .jpg filter.
  await page.getByLabel("Show:").selectOption({ label: "Only .c and .jpg" });
  await expect(nameCells(page)).toHaveText(["old.c"]);
  await expect(page.getByText("1 of 2 file(s) shown")).toBeVisible();
  await page.getByLabel("Show:").selectOption({ label: "All files" });

  // Variant 57: a .js file is previewed as text.
  await page.getByRole("cell", { name: "new.js" }).click();
  await expect(page.getByTestId("text-preview")).toHaveText("console.log('Drive Mini');");

  // Hide a column from the header's right-click menu.
  await page.getByRole("columnheader", { name: "Uploader" }).click({ button: "right" });
  await page.getByRole("checkbox", { name: "Uploader" }).uncheck();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("columnheader", { name: "Uploader" })).toHaveCount(0);

  // Delete asks first (a real browser dialog), then the file is gone.
  await page.getByRole("cell", { name: "old.c" }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByRole("cell", { name: "old.c" })).toHaveCount(0);

  // Log out, log back in: the drive and the hidden column are still there.
  await page.getByRole("button", { name: "Log out" }).click();
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(nameCells(page)).toHaveText(["new.js"]);
  await expect(page.getByRole("columnheader", { name: "Uploader" })).toHaveCount(0);
});
