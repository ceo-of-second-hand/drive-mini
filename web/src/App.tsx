import { useEffect, useState } from "react";
import { ApiClient, type UserOut } from "./api";
import DrivePage from "./DrivePage";
import LoginPage from "./LoginPage";

/** Login page or the drive. A reload keeps you logged in (the token is in sessionStorage). */
export default function App({ api: given }: { api?: ApiClient }) {
  // One client for the whole life of the page. (A new client on every render made the session
  // check below run again after each render, and a late answer logged the user back in.)
  const [api] = useState(() => given ?? new ApiClient());
  const [user, setUser] = useState<UserOut | null>(null);
  const [restoring, setRestoring] = useState(api.loggedIn);

  useEffect(() => {
    api.onUnauthorized = () => setUser(null); // session expired: back to the login page
    if (!api.loggedIn) return;
    api.me()
      .then((u) => { if (api.loggedIn) setUser(u); }) // ignore an answer that arrives after Log out
      .catch(() => api.logout())
      .finally(() => setRestoring(false));
  }, [api]);

  function logOut() {
    api.logout();
    setUser(null);
  }

  if (restoring) return <p className="muted">Loading…</p>;
  if (!user) return <LoginPage api={api} onLogin={setUser} />;
  return <DrivePage api={api} user={user} onLogout={logOut} />;
}
