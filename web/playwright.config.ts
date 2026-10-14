/**
 * End-to-end test: a real Edge clicks through the real app against a real server.
 *
 * Everything runs apart from your own setup: the server gets a fresh temporary database and storage
 * folder and its own port (8765), Vite its own port (5199). If either port is taken, the run stops
 * instead of reusing someone else's server, so your drivemini.db and your `npm run dev` are never touched.
 * Run with:  npm run e2e   (no server needs to be running)
 */
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { defineConfig } from "@playwright/test";

const ROOT = resolve(import.meta.dirname, "..");
const TEMP = mkdtempSync(join(tmpdir(), "drivemini-e2e-"));
const API_PORT = 8765;
const WEB_PORT = 5199;

export default defineConfig({
  testDir: "e2e",
  workers: 1,
  timeout: 60_000,
  use: {
    channel: "msedge", // the Edge installed on this PC, so no browser download is needed
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
  },
  webServer: [
    {
      command: `"${join(ROOT, ".venv", "Scripts", "python.exe")}" -m uvicorn server.main:app --port ${API_PORT}`,
      cwd: ROOT,
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: false,
      env: {
        DATABASE_URL: `sqlite:///${join(TEMP, "e2e.db").replaceAll("\\", "/")}`,
        STORAGE_DIR: join(TEMP, "storage"),
        JWT_SECRET: "e2e-secret-" + "x".repeat(32),
      },
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      reuseExistingServer: false,
      env: { DRIVE_MINI_API: `http://127.0.0.1:${API_PORT}` },
    },
  ],
});
