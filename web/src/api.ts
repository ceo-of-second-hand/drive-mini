/**
 * ApiClient: the web client's only link to the server (the twin of client/api.py on desktop).
 *
 * The data shapes come from api-types.ts, which is generated from the shared contract
 * common/openapi.json (npm run gen:api), so they always match the server.
 * Errors of any kind become ApiError with a readable message. The login token is kept in
 * sessionStorage: it survives a page reload and is gone when the tab is closed.
 */
import type { components } from "./api-types";

type Schemas = components["schemas"];
export type FileOut = Schemas["FileOut"];
export type UserOut = Schemas["UserOut"];
type TokenOut = Schemas["TokenOut"];
type ErrorOut = Schemas["ErrorOut"];

const TOKEN_KEY = "driveMini.token";

/** A failed request. status is the HTTP code, or 0 if the server couldn't be reached. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

export class ApiClient {
  /** Called when the server rejects our token (expired or invalid): the page goes back to login. */
  onUnauthorized: () => void = () => {};

  get loggedIn(): boolean {
    return this.token !== null;
  }

  private get token(): string | null {
    return sessionStorage.getItem(TOKEN_KEY);
  }

  private async request(method: string, url: string, body?: BodyInit): Promise<Response> {
    const token = this.token;
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    if (typeof body === "string") headers["Content-Type"] = "application/json";
    let response: Response;
    try {
      response = await fetch(url, { method, headers, body });
    } catch {
      throw new ApiError(0, "Cannot reach the server. Is it running?");
    }
    if (!response.ok) {
      if (response.status === 401 && token) {
        // Only a request made WITH a token means "your session is over"; a wrong password is
        // also 401, but then we weren't logged in.
        this.logout();
        this.onUnauthorized();
      }
      throw new ApiError(response.status, await errorDetail(response));
    }
    return response;
  }

  // --- accounts ---

  async register(username: string, displayName: string, password: string): Promise<UserOut> {
    const body = JSON.stringify({ username, display_name: displayName, password });
    return (await this.request("POST", "/auth/register", body)).json();
  }

  async login(username: string, password: string): Promise<UserOut> {
    // The server takes the standard OAuth2 password form, not JSON.
    const form = new URLSearchParams({ username, password });
    const reply: TokenOut = await (await this.request("POST", "/auth/login", form)).json();
    sessionStorage.setItem(TOKEN_KEY, reply.access_token);
    return this.me();
  }

  logout(): void {
    sessionStorage.removeItem(TOKEN_KEY); // tokens are stateless: forgetting it is the logout
  }

  async me(): Promise<UserOut> {
    return (await this.request("GET", "/auth/me")).json();
  }

  // --- files ---

  async listFiles(): Promise<FileOut[]> {
    return (await this.request("GET", "/files")).json();
  }

  /** New file. A taken name fails with status 409 (then offer to replace). */
  async upload(file: File): Promise<FileOut> {
    return (await this.request("POST", "/files", formWith(file))).json();
  }

  /** New content for an existing file; its name, created time and uploader stay. */
  async replace(fileId: number, file: File): Promise<FileOut> {
    return (await this.request("PUT", `/files/${fileId}`, formWith(file))).json();
  }

  async download(fileId: number): Promise<Blob> {
    return (await this.request("GET", `/files/${fileId}/content`)).blob();
  }

  async delete(fileId: number): Promise<void> {
    await this.request("DELETE", `/files/${fileId}`);
  }
}

function formWith(file: File): FormData {
  const form = new FormData(); // the browser sets the multipart Content-Type itself
  form.append("file", file);
  return form;
}

/** The server's one-line message from {"detail": "..."}, or the HTTP status text. */
async function errorDetail(response: Response): Promise<string> {
  try {
    const body: ErrorOut = await response.clone().json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // not JSON: fall through
  }
  return (await response.text()) || response.statusText || `HTTP ${response.status}`;
}
