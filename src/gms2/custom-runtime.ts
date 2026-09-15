/**
 * Copyright 2026, Opera Norway AS
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at:
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { z } from "zod";
import type { Context } from "~/context";
import { KnownError } from "~/error";

export async function nativeRuntimeCommand(ctx: Context, args: string[]) {
  const helper = ctx.path.join(
    ctx.path.dirname(fileURLToPath(import.meta.url)),
    "native",
    "mobile_runtime.py",
  );
  try {
    const { stdout } = await promisify(ctx.child_process.execFile)(
      "python3",
      [helper, ...args],
      {
        env: ctx.process.env,
        maxBuffer: 2 * 1024 * 1024,
      },
    );
    return JSON.parse(stdout) as unknown;
  } catch (error) {
    const message = error as { stderr?: string; message?: string };
    let stderr = message.stderr?.trim();
    if (stderr === "") {
      stderr = undefined;
    }
    throw new KnownError(
      stderr ?? message.message ?? "Custom runtime verification failed",
    );
  }
}

export const assemblySchema = z.object({
  schema: z.literal(1),
  version: z.string(),
  base: z.string(),
  platform: z.enum(["ios", "android"]),
  manifest_sha256: z.string(),
  runner_commit: z.string(),
  artifact_sha256: z.string(),
  libraries: z.record(z.string(), z.string()),
  runtimeDirectory: z.string(),
  baseLibraries: z.record(z.string(), z.string()),
});
export type Assembly = z.infer<typeof assemblySchema>;
