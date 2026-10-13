import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import App from "./App";
import { ApiClient } from "./api";

const USER = { id: 1, username: "ivanka", display_name: "Ivanka" };

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

test("without a token the login page is shown", () => {
  render(<App api={new ApiClient()} />);
  expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
});

test("a reload keeps you logged in, and Log out goes back to the login page", async () => {
  sessionStorage.setItem("driveMini.token", "abc");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(200, USER)));
  render(<App api={new ApiClient()} />);

  expect(await screen.findByText("Ivanka (ivanka)")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Log out" }));
  expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
  expect(sessionStorage.getItem("driveMini.token")).toBeNull();
});

test("an expired token on reload shows the login page", async () => {
  sessionStorage.setItem("driveMini.token", "expired");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(401, { detail: "Token expired." })));
  render(<App api={new ApiClient()} />);
  expect(await screen.findByRole("button", { name: "Log in" })).toBeInTheDocument();
});
