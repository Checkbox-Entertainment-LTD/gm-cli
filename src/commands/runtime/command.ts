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

import { buildCommand, buildRouteMap } from "@stricli/core";
import type { Context } from "~/context";
import { nativeRuntimeCommand } from "~/gms2/custom-runtime";

const resolve = buildCommand({
  async func(
    this: Context,
    flags: { version: string; platforms: string; output: string },
  ) {
    await nativeRuntimeCommand(this, [
      "resolve",
      "--version",
      flags.version,
      "--platforms",
      flags.platforms,
      "--output",
      this.path.resolve(flags.output),
    ]);
    this.process.stdout.write(
      this.path.resolve(flags.output, "lock.json") + "\n",
    );
  },
  parameters: {
    positional: { kind: "tuple", parameters: [] },
    flags: {
      version: {
        kind: "parsed",
        parse: String,
        brief: "Exact stock or custom runtime version",
      },
      platforms: {
        kind: "parsed",
        parse: String,
        brief: "Requested mobile platforms, comma separated (ios,android)",
      },
      output: {
        kind: "parsed",
        parse: String,
        brief: "New directory for the verified release lock and packages",
      },
    },
  },
  docs: {
    brief:
      "Resolve and verify every requested custom runtime package before building",
  },
});
const verifyIos = buildCommand({
  async func(
    this: Context,
    flags: {
      result: string;
      derivedData: string;
      ipa: string;
      symbols: string;
      output: string;
    },
  ) {
    await nativeRuntimeCommand(this, [
      "verify-ios",
      "--result",
      flags.result,
      "--derived-data",
      flags.derivedData,
      "--ipa",
      flags.ipa,
      "--symbols",
      flags.symbols,
      "--output",
      flags.output,
    ]);
  },
  parameters: {
    positional: { kind: "tuple", parameters: [] },
    flags: {
      result: { kind: "parsed", parse: String, brief: "CLI build result JSON" },
      derivedData: {
        kind: "parsed",
        parse: String,
        brief: "Isolated Xcode DerivedData directory",
      },
      ipa: { kind: "parsed", parse: String, brief: "Signed IPA to verify" },
      symbols: { kind: "parsed", parse: String, brief: "Matching dSYM ZIP" },
      output: {
        kind: "parsed",
        parse: String,
        brief: "New verification record path",
      },
    },
  },
  docs: {
    brief:
      "Verify the staged iOS runner and IPA/dSYM UUIDs before distribution",
  },
});
const verifyAndroid = buildCommand({
  async func(
    this: Context,
    flags: {
      result: string;
      aab: string;
      keystore: string;
      alias: string;
      output: string;
    },
  ) {
    await nativeRuntimeCommand(this, [
      "verify-android",
      "--result",
      flags.result,
      "--aab",
      flags.aab,
      "--keystore",
      flags.keystore,
      "--alias",
      flags.alias,
      "--output",
      flags.output,
    ]);
  },
  parameters: {
    positional: { kind: "tuple", parameters: [] },
    flags: {
      result: { kind: "parsed", parse: String, brief: "CLI build result JSON" },
      aab: { kind: "parsed", parse: String, brief: "Signed AAB to verify" },
      keystore: {
        kind: "parsed",
        parse: String,
        brief: "Signing keystore (password from ANDROID_KEYSTORE_PASSWORD)",
      },
      alias: { kind: "parsed", parse: String, brief: "Signing key alias" },
      output: {
        kind: "parsed",
        parse: String,
        brief: "New verification record path",
      },
    },
  },
  docs: {
    brief: "Verify AAB architecture coverage and the signing certificate",
  },
});
export const runtimeCommand = buildRouteMap({
  routes: { resolve, "verify-ios": verifyIos, "verify-android": verifyAndroid },
  docs: { brief: "Resolve immutable mobile runtimes" },
});
