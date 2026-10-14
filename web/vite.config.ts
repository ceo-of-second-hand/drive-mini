/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the page is served by Vite (:5173) and API calls are forwarded to uvicorn,
// so the browser sees one origin and no CORS setup is needed. The end-to-end test points it at
// its own temporary server instead (DRIVE_MINI_API), never at the real one.
const API = process.env.DRIVE_MINI_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/auth": API, "/files": API, "/sync": API, "/health": API },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
    include: ["src/**/*.test.{ts,tsx}"], // e2e/ is Playwright's, run with npm run e2e
  },
});
