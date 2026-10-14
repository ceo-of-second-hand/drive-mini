// @vitest-environment node
// Variant 57: the individual operation. The cases come from common/variant_cases.json, the same
// file tests/test_sorting.py checks the desktop's Python version with.
import { readFileSync } from "node:fs";
import { expect, test } from "vitest";
import { fileExtension } from "./rules";
import { filterFiles, sortByCreated } from "./sorting";

const CASES = JSON.parse(readFileSync(new URL("../../common/variant_cases.json", import.meta.url), "utf-8"));
const names = (files: { name: string }[]) => files.map((f) => f.name);

test("sort by creation date, oldest first and newest first (shared cases)", () => {
  expect(names(sortByCreated(CASES.files, "asc"))).toEqual(CASES.oldest_first);
  expect(names(sortByCreated(CASES.files, "desc"))).toEqual(CASES.newest_first);
});

test("equal creation times fall back to id, so the order is stable (shared cases)", () => {
  const ties = CASES.equal_times;
  expect(sortByCreated(ties.files, "asc").map((f: { id: number }) => f.id)).toEqual(ties.oldest_first_ids);
  expect(sortByCreated(ties.files, "desc").map((f: { id: number }) => f.id)).toEqual(ties.newest_first_ids);
});

test("the filter keeps only .c and .jpg, ignoring case and look-alikes (shared cases)", () => {
  const files = CASES.filter_c_jpg.names.map((name: string, id: number) => ({ id, name, created_at: "2026-10-01T09:00:00Z" }));
  expect(names(filterFiles(files, "c_jpg"))).toEqual(CASES.filter_c_jpg.kept);
  expect(names(filterFiles(files, "all"))).toEqual(CASES.filter_c_jpg.names);
});

test("filter then sort, as the table does (shared cases)", () => {
  expect(names(sortByCreated(filterFiles(CASES.files, "c_jpg"), "desc"))).toEqual(CASES.filter_then_newest_first);
});

test("sorting doesn't change the list it was given", () => {
  const original = [...CASES.files];
  sortByCreated(CASES.files, "asc");
  expect(CASES.files).toEqual(original);
});

test("fileExtension matches the Python rule", () => {
  expect(["photo.JPG", "Makefile", ".c", "a.", "notes.c.txt"].map(fileExtension)).toEqual(["jpg", "", "", "", "txt"]);
});
