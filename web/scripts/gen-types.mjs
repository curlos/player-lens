// Generates TypeScript types from the JSON contracts (the Pydantic models are the source of truth).
// Run after `python scripts/export_schemas.py` changes anything in contracts/: `npm run gen:types`.
import { readdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const here = dirname(fileURLToPath(import.meta.url));
const contractsDir = join(here, "..", "..", "contracts");
const outDir = join(here, "..", "src", "types", "generated");

const files = (await readdir(contractsDir)).filter((f) => f.endsWith(".schema.json")).sort();
for (const file of files) {
  const schema = JSON.parse(await readFile(join(contractsDir, file), "utf8"));
  const name = file.replace(".schema.json", "");
  const ts = await compile(schema, schema.title ?? name, {
    bannerComment: `/* Generated from contracts/${file} by scripts/gen-types.mjs. Do not edit by hand. */`,
    additionalProperties: false,
    style: { singleQuote: false },
  });
  await writeFile(join(outDir, `${name}.ts`), ts);
  console.log(`contracts/${file} -> src/types/generated/${name}.ts`);
}
