// Test helper: a fake server for fetch. Each route ("/files", or "POST /files" for one method only)
// gets one reply, or inOrder(...) for replies that change from call to call (the last one repeats).
import { vi } from "vitest";

export function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

class InOrder {
  readonly replies: unknown[];

  constructor(replies: unknown[]) {
    this.replies = replies;
  }
}

export const inOrder = (...replies: unknown[]) => new InOrder(replies);

export function fakeServer(routes: Record<string, unknown>) {
  const queues = new Map(Object.entries(routes).map(
    ([url, r]) => [url, r instanceof InOrder ? [...r.replies] : [r]]));
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const queue = queues.get(`${init?.method ?? "GET"} ${url}`) ?? queues.get(url);
    if (!queue) throw new Error(`no fake reply for ${init?.method ?? "GET"} ${url}`);
    const next = queue.length > 1 ? queue.shift() : queue[0];
    return next instanceof Response ? next.clone() : reply(200, next);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
