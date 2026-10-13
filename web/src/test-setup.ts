// Runs before every test file: DOM matchers like toHaveTextContent, and a clean page, clean storage
// and the real fetch back after each test.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  globalThis.sessionStorage?.clear(); // absent in tests that run in plain Node
  globalThis.localStorage?.clear();
});
