// @vitest-environment node
// api-types.ts must be exactly what `npm run gen:api` makes from the current common/openapi.json.
// Together with tests/test_openapi.py this closes the chain: schemas.py -> openapi.json -> api-types.ts.
import { readFileSync } from "node:fs";
import openapiTS, { astToString, COMMENT_HEADER } from "openapi-typescript";
import { expect, test } from "vitest";

const unify = (text: string) => text.replace(/\r\n/g, "\n").trimEnd();

test("api-types.ts is generated from the current common/openapi.json", async () => {
  const contract = new URL("../../common/openapi.json", import.meta.url);
  const expected = COMMENT_HEADER + astToString(await openapiTS(contract));
  const actual = readFileSync(new URL("./api-types.ts", import.meta.url), "utf-8");
  expect(unify(actual), "api-types.ts is out of date: run `npm run gen:api`").toBe(unify(expected));
});
