import { useEffect, useState } from "react";
import { ApiClient, type UserOut } from "./api";
import LoginPage from "./LoginPage";

/** Login page or the drive. A reload keeps you logged in (the token is in sessionStorage). */
export default function App({ api = new ApiClient() }: { api?: ApiClient }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [restoring, setRestoring] = useState(api.loggedIn);

  useEffect(() => {
    api.onUnauthorized = () => setUser(null); // session expired: back to the login page
    if (!api.loggedIn) return;
    api.me()
      .then(setUser)
      .catch(() => api.logout())
      .finally(() => setRestoring(false));
  }, [api]);

  function logOut() {
    api.logout();
    setUser(null);
  }

  if (restoring) return <p className="muted">Loading…</p>;
  if (!user) return <LoginPage api={api} onLogin={setUser} />;
  // The drive itself (the file table) comes in the next commit.
  return (
    <header className="topbar">
      <strong>Drive Mini</strong>
      <span>{user.display_name} ({user.username})</span>
      <button onClick={logOut}>Log out</button>
    </header>
  );
}
