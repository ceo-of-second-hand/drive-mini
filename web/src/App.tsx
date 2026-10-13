import { useEffect, useState } from "react";

type ServerStatus = "checking…" | "ok" | "not reachable";

/** Placeholder page for the skeleton: proves the page, the dev proxy and the server work together. */
export default function App() {
  const [status, setStatus] = useState<ServerStatus>("checking…");

  useEffect(() => {
    fetch("/health")
      .then((response) => setStatus(response.ok ? "ok" : "not reachable"))
      .catch(() => setStatus("not reachable"));
  }, []);

  return (
    <main>
      <h1>Drive Mini</h1>
      <p>Server: {status}</p>
    </main>
  );
}
