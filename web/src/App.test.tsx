import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import App from "./App";

test("shows the server status from /health", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response('{"status": "ok"}'));
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  expect(screen.getByRole("heading")).toHaveTextContent("Drive Mini");
  expect(await screen.findByText("Server: ok")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith("/health");
});

test("says so when the server is not running", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
  render(<App />);
  expect(await screen.findByText("Server: not reachable")).toBeInTheDocument();
});
