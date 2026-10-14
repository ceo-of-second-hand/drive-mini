import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import App from "./App";
import { ApiClient } from "./api";
import { fakeServer, reply } from "./test-server";

const USER = { id: 1, username: "ivanka", display_name: "Ivanka" };

test("without a token the login page is shown", () => {
  render(<App api={new ApiClient()} />);
  expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
});

test("a reload keeps you logged in, and Log out goes back to the login page", async () => {
  sessionStorage.setItem("driveMini.token", "abc");
  fakeServer({ "/auth/me": USER, "/files": [] });
  render(<App api={new ApiClient()} />);

  expect(await screen.findByText("Ivanka (ivanka)")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Log out" }));
  expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
  expect(sessionStorage.getItem("driveMini.token")).toBeNull();
});

test("one Log out is enough, and the session is checked only once", async () => {
  // Rendered exactly like main.tsx does (no client passed in), which is where the bug was:
  // a new client on every render re-ran the session check in a loop, and a late answer
  // logged the user back in after Log out.
  sessionStorage.setItem("driveMini.token", "abc");
  const fetchMock = fakeServer({ "/auth/me": USER, "/files": [] });
  render(<App />);
  await screen.findByText("Ivanka (ivanka)");

  await userEvent.click(screen.getByRole("button", { name: "Log out" }));
  await new Promise((resolve) => setTimeout(resolve, 100)); // let any late answers arrive
  expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
  expect(fetchMock.mock.calls.filter(([url]) => url === "/auth/me")).toHaveLength(1);
});

test("an expired token on reload shows the login page", async () => {
  sessionStorage.setItem("driveMini.token", "expired");
  fakeServer({ "/auth/me": reply(401, { detail: "Token expired." }) });
  render(<App api={new ApiClient()} />);
  expect(await screen.findByRole("button", { name: "Log in" })).toBeInTheDocument();
});
