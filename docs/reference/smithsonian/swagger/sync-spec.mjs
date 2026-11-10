import { readFile, writeFile } from "node:fs/promises";

const source = new URL("./openapi.json", import.meta.url);
const target = new URL("./openapi-spec.js", import.meta.url);
const spec = JSON.parse(await readFile(source, "utf8"));
const expected = `window.SMITHSONIAN_OPENAPI = ${JSON.stringify(spec, null, 2)};\n`;
if (process.argv.includes("--check")) {
  if ((await readFile(target, "utf8")) !== expected) {
    throw new Error("openapi-spec.js is stale; run node sync-spec.mjs");
  }
  console.log("OpenAPI JSON and offline JavaScript mirror match.");
} else {
  await writeFile(target, expected);
  console.log("Updated openapi-spec.js from openapi.json.");
}
