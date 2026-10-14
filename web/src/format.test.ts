import { expect, test } from "vitest";
import { formatSize, formatTime } from "./format";

test("sizes read like the desktop table", () => {
  expect(formatSize(0)).toBe("0 B");
  expect(formatSize(1023)).toBe("1023 B");
  expect(formatSize(1024)).toBe("1.0 KB");
  expect(formatSize(1536)).toBe("1.5 KB");
  expect(formatSize(5 * 1024 * 1024 + 300 * 1024)).toBe("5.3 MB");
});

test("server UTC times are shown in local time, with seconds", () => {
  const utc = "2026-10-02T09:05:07Z";
  const local = new Date(utc);
  const expected = new Date(local.getTime() - local.getTimezoneOffset() * 60_000)
    .toISOString().slice(0, 19).replace("T", " "); // the same moment written in local time
  expect(formatTime(utc)).toBe(expected);
  expect(formatTime(utc)).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
});
