import { useState, type FormEvent } from "react";
import { ApiError, type ApiClient, type UserOut } from "./api";

const LAST_USERNAME_KEY = "driveMini.lastUsername";

// Friendlier wording for the server's validation messages (the same hints as on desktop).
const FIELD_HINTS: Record<string, string> = {
  username: "Username: 3–32 characters, only letters, digits and _ . -",
  display_name: "Display name: 1–64 characters.",
};

function readable(error: unknown): string {
  if (!(error instanceof ApiError)) return String(error);
  const field = error.detail.split(":")[0];
  return error.status === 422 && FIELD_HINTS[field] ? FIELD_HINTS[field] : error.detail;
}

/** Log in, or create an account and log straight in with it (like the desktop login window). */
export default function LoginPage({ api, onLogin }: { api: ApiClient; onLogin: (user: UserOut) => void }) {
  const [registering, setRegistering] = useState(false);
  const [username, setUsername] = useState(() => localStorage.getItem(LAST_USERNAME_KEY) ?? "");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (registering) await api.register(username.trim(), displayName.trim(), password);
      const user = await api.login(username.trim(), password);
      localStorage.setItem(LAST_USERNAME_KEY, user.username);
      onLogin(user);
    } catch (e) {
      setError(readable(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <h1>Drive Mini</h1>
      <p className="muted">Your files on a remote server</p>
      <form onSubmit={submit}>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus={!username} />
        </label>
        {registering && (
          <label>
            Display name
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
          </label>
        )}
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
                 autoFocus={!!username} />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>{registering ? "Create account" : "Log in"}</button>
      </form>
      <button className="link" onClick={() => { setRegistering(!registering); setError(""); }}>
        {registering ? "I already have an account" : "Register…"}
      </button>
    </main>
  );
}
