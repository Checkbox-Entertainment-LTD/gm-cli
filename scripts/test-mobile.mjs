import { build } from "tsup";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
const dir = await mkdtemp(join(tmpdir(), "gm-cli-mobile-tests-"));
try {
  await build({
    entry: { test: "tests/mobile.test.ts" },
    outDir: dir,
    bundle: true,
    platform: "node",
    format: ["esm"],
    tsconfig: "tsconfig.json",
    config: false,
    splitting: false,
    noExternal: [/.*/],
    outExtension: () => ({ js: ".mjs" }),
    banner: {
      js: "import {createRequire as __mobileCreateRequire} from 'node:module';const require=__mobileCreateRequire(import.meta.url);",
    },
  });
  const result = spawnSync(process.execPath, [join(dir, "test.mjs")], {
    stdio: "inherit",
  });
  process.exitCode = result.status ?? 1;
} finally {
  await rm(dir, { recursive: true, force: true });
}
