import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { ApiError, type ApiClient } from "./api";
import LoginPage from "./LoginPage";

const USER = { id: 1, username: "ivanka", display_name: "Ivanka" };

function fakeApi(overrides: Partial<Record<"login" | "register", ReturnType<typeof vi.fn>>> = {}) {
  return { login: vi.fn().mockResolvedValue(USER), register: vi.fn().mockResolvedValue(USER), ...overrides } as
    unknown as ApiClient;
}

test("a wrong password shows the server's message", async () => {
  const api = fakeApi({ login: vi.fn().mockRejectedValue(new ApiError(401, "Wrong username or password.")) });
  const onLogin = vi.fn();
  render(<LoginPage api={api} onLogin={onLogin} />);

  await userEvent.type(screen.getByLabelText("Username"), "ivanka");
  await userEvent.type(screen.getByLabelText("Password"), "wrong");
  await userEvent.click(screen.getByRole("button", { name: "Log in" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Wrong username or password.");
  expect(onLogin).not.toHaveBeenCalled();
});

test("a successful login opens the drive and the username is remembered", async () => {
  const api = fakeApi();
  const onLogin = vi.fn();
  const { unmount } = render(<LoginPage api={api} onLogin={onLogin} />);

  await userEvent.type(screen.getByLabelText("Username"), " ivanka ");
  await userEvent.type(screen.getByLabelText("Password"), "secret");
  await userEvent.click(screen.getByRole("button", { name: "Log in" }));

  expect(api.login).toHaveBeenCalledWith("ivanka", "secret");
  expect(onLogin).toHaveBeenCalledWith(USER);
  unmount();
  render(<LoginPage api={api} onLogin={onLogin} />); // next visit
  expect(screen.getByLabelText("Username")).toHaveValue("ivanka");
});

test("register shows a friendly hint for a bad username, then creates the account and logs in", async () => {
  const register = vi.fn()
    .mockRejectedValueOnce(new ApiError(422, "username: String should match pattern '^[A-Za-z0-9_.-]+$'"))
    .mockResolvedValueOnce(USER);
  const api = fakeApi({ register });
  const onLogin = vi.fn();
  render(<LoginPage api={api} onLogin={onLogin} />);

  await userEvent.click(screen.getByRole("button", { name: "Register…" }));
  await userEvent.type(screen.getByLabelText("Username"), "iv anka");
  await userEvent.type(screen.getByLabelText("Display name"), "Ivanka");
  await userEvent.type(screen.getByLabelText("Password"), "secret");
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("only letters, digits and _ . -");

  await userEvent.clear(screen.getByLabelText("Username"));
  await userEvent.type(screen.getByLabelText("Username"), "ivanka");
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(register).toHaveBeenLastCalledWith("ivanka", "Ivanka", "secret");
  expect(api.login).toHaveBeenCalledWith("ivanka", "secret"); // straight in with the new account
  expect(onLogin).toHaveBeenCalledWith(USER);
});
