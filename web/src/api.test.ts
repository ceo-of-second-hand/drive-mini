import { describe, expect, test, vi } from "vitest";
import { ApiClient, ApiError } from "./api";

const USER = { id: 1, username: "ivanka", display_name: "Ivanka" };

function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** A fake server: each call to fetch gets the next prepared reply. */
function fakeFetch(...replies: Response[]) {
  const fetchMock = vi.fn();
  for (const r of replies) fetchMock.mockResolvedValueOnce(r);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("ApiClient", () => {
  test("login sends the OAuth2 form, keeps the token and sends it with later requests", async () => {
    const fetchMock = fakeFetch(reply(200, { access_token: "abc", token_type: "bearer" }), reply(200, USER));
    const api = new ApiClient();

    expect(await api.login("ivanka", "secret")).toEqual(USER);

    const [loginUrl, loginInit] = fetchMock.mock.calls[0];
    expect(loginUrl).toBe("/auth/login");
    expect(loginInit.method).toBe("POST");
    expect(String(loginInit.body)).toBe("username=ivanka&password=secret");
    const [meUrl, meInit] = fetchMock.mock.calls[1];
    expect(meUrl).toBe("/auth/me");
    expect(meInit.headers.Authorization).toBe("Bearer abc");
    expect(api.loggedIn).toBe(true);
  });

  test("an error reply becomes ApiError with the server's message", async () => {
    fakeFetch(reply(409, { detail: "Username 'ivanka' is already taken." }));
    const error = await new ApiClient().register("ivanka", "Ivanka", "secret").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(409);
    expect(error.detail).toBe("Username 'ivanka' is already taken.");
  });

  test("a 401 on a request with a token logs out and tells the page", async () => {
    sessionStorage.setItem("driveMini.token", "expired");
    fakeFetch(reply(401, { detail: "Token expired." }));
    const api = new ApiClient();
    api.onUnauthorized = vi.fn();

    await expect(api.me()).rejects.toThrow("Token expired.");
    expect(api.loggedIn).toBe(false);
    expect(api.onUnauthorized).toHaveBeenCalledOnce();
  });

  test("a wrong password (401 without a token) is just an error, not a logout", async () => {
    fakeFetch(reply(401, { detail: "Wrong username or password." }));
    const api = new ApiClient();
    api.onUnauthorized = vi.fn();

    await expect(api.login("ivanka", "wrong")).rejects.toThrow("Wrong username or password.");
    expect(api.onUnauthorized).not.toHaveBeenCalled();
  });

  test("an unreachable server gives a readable message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const error = await new ApiClient().me().catch((e) => e);
    expect(error.status).toBe(0);
    expect(error.detail).toBe("Cannot reach the server. Is it running?");
  });
});
