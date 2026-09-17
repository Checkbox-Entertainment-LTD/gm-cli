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

import { createHash } from "node:crypto";
import { promisify } from "node:util";
import { unzipSync } from "fflate";
import { z } from "zod";
import { exists, type Context } from "~/context";
import { KnownError } from "~/error";
import type { Log } from "~/log";
import type { ProjectPath } from "~/project";
import { nativeRuntimeCommand } from "./custom-runtime";
import { spawnProcess } from "~/spawn";
import type { Gms2ToolchainOptions } from "./options";

type IosOptions = Gms2ToolchainOptions["ios"];
export type IosCommand =
  { type: "compile" | "run" } | { type: "package"; outputPath?: string };

export interface IosOutput {
  projectDirectory: string;
  xcodeProject: string;
  workspace?: string;
  derivedData?: string;
  archive?: string;
  ipa?: string;
  app?: string;
  simulatorId?: string;
  symbols?: string[];
  runnerLibraries: Record<string, string>;
}

export async function preflightIos(
  ctx: Context,
  command: IosCommand,
  options: IosOptions,
) {
  if (ctx.process.platform !== "darwin") {
    throw new KnownError("iOS builds require a Mac with Xcode installed");
  }
  if (command.type === "run" && !options.simulatorId) {
    throw new KnownError(
      "iOS run requires gms2.ios.simulatorId (an installed simulator UDID)",
    );
  }
  if (
    command.type === "package" &&
    options.packageType === "ipa" &&
    !options.exportOptionsPlist
  ) {
    throw new KnownError(
      "iOS IPA packaging requires gms2.ios.exportOptionsPlist for signing and export",
    );
  }
  if (options.signingIdentity && !options.provisioningProfile) {
    throw new KnownError(
      "An explicit iOS signing identity requires a provisioning profile",
    );
  }
  if (
    options.exportOptionsPlist &&
    !(await exists(ctx, options.exportOptionsPlist))
  ) {
    throw new KnownError("The iOS export options plist does not exist");
  }
  if (command.type === "package" && command.outputPath) {
    if (options.packageType === "ipa" && !command.outputPath.endsWith(".ipa")) {
      throw new KnownError("iOS IPA output must end in .ipa");
    }
    if (
      options.packageType !== "ipa" &&
      /\.(zip|ipa)$/.test(command.outputPath)
    ) {
      throw new KnownError(
        "iOS project output is a directory; use packageType ipa for a signed IPA",
      );
    }
  }
  const exec = promisify(ctx.child_process.execFile);
  if (options.exportOptionsPlist) {
    const { stdout } = await exec("plutil", [
      "-convert",
      "json",
      "-o",
      "-",
      ctx.path.resolve(options.exportOptionsPlist),
    ]);
    const plist = z
      .object({ destination: z.string().optional() })
      .parse(JSON.parse(stdout));
    if (plist.destination && plist.destination !== "export") {
      throw new KnownError(
        "IPA packaging requires local export; use the delivery pipeline for uploads",
      );
    }
  }
  await exec("xcodebuild", ["-version"], { env: iosEnv(ctx, options) });
}

function iosEnv(ctx: Context, options: IosOptions) {
  return {
    ...ctx.process.env,
    ...(options.developerDir
      ? { DEVELOPER_DIR: ctx.path.resolve(options.developerDir) }
      : {}),
  };
}

/** Find only in the new invocation's output, never the user's IDE directories. */
export async function findGeneratedIosProject(
  ctx: Context,
  output: string,
): Promise<string> {
  const projects: string[] = [];
  async function visit(dir: string) {
    for (const entry of await ctx.fs.readdir(dir, { withFileTypes: true })) {
      if (!entry.isDirectory() || ["Pods", "Fw"].includes(entry.name)) {
        continue;
      }
      const path = ctx.path.join(dir, entry.name);
      if (entry.name.endsWith(".xcodeproj")) {
        if (!(await exists(ctx, ctx.path.join(path, "project.pbxproj")))) {
          throw new KnownError("Generated Xcode project is incomplete");
        }
        projects.push(path);
      } else if (
        !entry.name.endsWith(".xcframework") &&
        !entry.name.endsWith(".framework")
      ) {
        await visit(path);
      }
    }
  }
  if (await exists(ctx, output)) {
    await visit(output);
  }
  if (projects.length !== 1) {
    throw new KnownError(
      `Expected one fresh Xcode project in ${output}; found ${String(projects.length)}`,
    );
  }
  const [project] = projects;
  if (!project) {
    throw new KnownError("Missing generated iOS project");
  }
  return project;
}

export function safeArchivePath(name: string): boolean {
  return (
    name.length > 0 &&
    !name.includes("\\") &&
    !name.includes("\0") &&
    !name.startsWith("/") &&
    !/^[A-Za-z]:/.test(name) &&
    !name
      .replace(/\/$/, "")
      .split("/")
      .some((part) => ["", ".", ".."].includes(part))
  );
}

// GameMaker resources use trailing commas; leave all string contents intact.
export function parseYy(text: string): unknown {
  return JSON.parse(
    text.replace(
      /("(?:\\.|[^"\\])*")|,\s*(?=[}\]])/g,
      (_match, quoted: string | undefined) => quoted ?? "",
    ),
  );
}

const projectSchema = z.object({
  resources: z.array(z.object({ id: z.object({ path: z.string() }) })),
});

/** Stage only extensions actually included in the selected project. */
export async function prepareIosFrameworks(
  ctx: Context,
  projectPath: ProjectPath,
  generated: string,
) {
  const projectDir = ctx.path.dirname(projectPath);
  const project = projectSchema.parse(
    parseYy(await ctx.fs.readFile(projectPath, "utf-8")),
  );
  const fw = ctx.path.join(generated, "Fw");
  await ctx.fs.mkdir(fw, { recursive: true });
  for (const resource of project.resources) {
    const resourcePath = resource.id.path;
    if (!resourcePath.startsWith("extensions/")) {
      continue;
    }
    if (!safeArchivePath(resourcePath)) {
      throw new KnownError("Invalid extension resource path");
    }
    const dir = ctx.path.join(
      projectDir,
      ctx.path.dirname(resourcePath),
      "iOSSourceFromMac",
    );
    if (!(await exists(ctx, dir))) {
      continue;
    }
    for (const entry of await ctx.fs.readdir(dir, { withFileTypes: true })) {
      if (!entry.isFile() || !entry.name.endsWith(".zip")) {
        continue;
      }
      const seen = new Set<string>();
      const files = unzipSync(
        await ctx.fs.readFile(ctx.path.join(dir, entry.name)),
        {
          filter(file) {
            if (!safeArchivePath(file.name)) {
              throw new KnownError(`Unsafe framework ZIP path: ${file.name}`);
            }
            const normalized = file.name.replace(/\/$/, "").toLowerCase();
            if (seen.has(normalized)) {
              throw new KnownError(
                `Duplicate framework ZIP path: ${file.name}`,
              );
            }
            seen.add(normalized);
            return true;
          },
        },
      );
      for (const [name, bytes] of Object.entries(files)) {
        if (!safeArchivePath(name)) {
          throw new KnownError(`Unsafe framework ZIP path: ${name}`);
        }
        if (name.startsWith("__MACOSX/") || name.endsWith(".DS_Store")) {
          continue;
        }
        const dest = ctx.path.join(fw, name);
        // Never write through a link created by the input project or another dependency.
        for (
          let parent = dest;
          parent !== generated;
          parent = ctx.path.dirname(parent)
        ) {
          try {
            if ((await ctx.fs.lstat(parent)).isSymbolicLink()) {
              throw new KnownError(
                "Framework destination contains a symbolic link",
              );
            }
          } catch (error) {
            if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
              throw error;
            }
          }
        }
        if (name.endsWith("/")) {
          await ctx.fs.mkdir(dest, { recursive: true });
          continue;
        }
        // A fresh project can already have files staged by newer Igor versions.
        // Identical duplicates are fine; conflicting frameworks are never overwritten.
        if (await exists(ctx, dest)) {
          if (!Buffer.from(bytes).equals(await ctx.fs.readFile(dest))) {
            throw new KnownError(`Conflicting iOS framework file: ${name}`);
          }
          continue;
        }
        await ctx.fs.mkdir(ctx.path.dirname(dest), { recursive: true });
        await ctx.fs.writeFile(dest, bytes, { flag: "wx" });
      }
    }
  }
}

export async function runnerHashes(
  ctx: Context,
  root: string,
): Promise<Record<string, string>> {
  const result: Record<string, string> = {};
  async function visit(dir: string) {
    for (const entry of await ctx.fs.readdir(dir, { withFileTypes: true })) {
      const file = ctx.path.join(dir, entry.name);
      if (
        entry.isDirectory() &&
        !["Pods", "build", "DerivedData"].includes(entry.name)
      ) {
        await visit(file);
      } else if (entry.isFile() && /^libyoyo.*\.a$/.test(entry.name)) {
        result[ctx.path.relative(root, file)] = createHash("sha256")
          .update(await ctx.fs.readFile(file))
          .digest("hex");
      }
    }
  }
  await visit(root);
  if (Object.keys(result).length === 0) {
    throw new KnownError("Generated project has no iOS runner libraries");
  }
  return result;
}

/** Verify the archive staged by Xcode before any export or device installation. */
export async function verifyStagedIosRunner(
  ctx: Context,
  derivedData: string,
  expected: Record<string, string>,
  simulator: boolean,
) {
  const actual = await runnerHashes(ctx, ctx.path.join(derivedData, "Build"));
  const selected = Object.entries(expected).filter(
    ([name]) => ctx.path.basename(name).endsWith("_sim.a") === simulator,
  );
  if (selected.length !== 1) {
    throw new KnownError("Ambiguous iOS runner slice");
  }
  const [entry] = selected;
  if (!entry) {
    throw new KnownError("Missing iOS runner slice");
  }
  const [name, hash] = entry;
  const matching = Object.entries(actual).filter(
    ([path]) => ctx.path.basename(path) === ctx.path.basename(name),
  );
  if (
    !matching.length ||
    matching.some(([, actualHash]) => actualHash !== hash)
  ) {
    throw new KnownError(
      "Xcode did not consume the selected iOS runner; distribution blocked",
    );
  }
}

/** Complete the local Xcode flow. Igor's remote build/Organizer UI is suppressed. */
export async function finishIos(
  ctx: Context,
  log: Log,
  command: IosCommand,
  options: IosOptions,
  inputProject: ProjectPath,
  buildDir: string,
  assemblyRecord?: string,
): Promise<IosOutput> {
  let xcodeProject = await findGeneratedIosProject(
    ctx,
    ctx.path.join(buildDir, "output"),
  );
  let projectDirectory = ctx.path.dirname(xcodeProject);
  if (assemblyRecord) {
    await nativeRuntimeCommand(ctx, [
      "install-ios",
      "--record",
      assemblyRecord,
      "--project",
      projectDirectory,
    ]);
  }
  await prepareIosFrameworks(ctx, inputProject, projectDirectory);
  const isProjectPackage =
    command.type === "package" && options.packageType !== "ipa";
  if (isProjectPackage && command.outputPath) {
    const destination = ctx.path.resolve(
      ctx.path.dirname(inputProject),
      command.outputPath,
    );
    if (await exists(ctx, destination)) {
      throw new KnownError(
        "iOS project output already exists; choose a fresh directory",
      );
    }
    await ctx.fs.mkdir(ctx.path.dirname(destination), { recursive: true });
    await ctx.fs.cp(projectDirectory, destination, {
      recursive: true,
      force: false,
      errorOnExist: true,
    });
    xcodeProject = ctx.path.join(destination, ctx.path.basename(xcodeProject));
    projectDirectory = destination;
  }
  const env = iosEnv(ctx, options);
  const run = async (cmd: string, args: string[]) => {
    await spawnProcess(ctx, log, {
      cmd,
      args,
      errorLabel: cmd,
      cwd: projectDirectory,
      env,
    });
  };
  if (
    command.type === "package" &&
    options.packageType === "ipa" &&
    options.provisioningProfile
  ) {
    // Set signing only on the app target. Global xcodebuild profile overrides
    // also reach Pods, which cannot use application provisioning profiles.
    await run("ruby", [
      "-rxcodeproj",
      "-e",
      `
project = Xcodeproj::Project.open(ARGV[0])
apps = project.native_targets.select { |target| target.product_type == 'com.apple.product-type.application' }
abort 'Expected exactly one generated iOS app target' unless apps.length == 1
apps.first.build_configurations.each do |config|
  next unless config.name == ARGV[1]
  config.build_settings['CODE_SIGN_STYLE'] = 'Manual'
  config.build_settings['CODE_SIGN_IDENTITY'] = ARGV[2]
  config.build_settings['PROVISIONING_PROFILE_SPECIFIER'] = ARGV[3]
  config.build_settings['DEVELOPMENT_TEAM'] = ARGV[4] unless ARGV[4].empty?
end
project.save
`,
      xcodeProject,
      options.configuration ?? "Release",
      options.signingIdentity ?? "Apple Distribution",
      options.provisioningProfile,
      options.teamId ?? "",
    ]);
  }
  if (
    options.podInstall !== false &&
    (await exists(ctx, ctx.path.join(projectDirectory, "Podfile")))
  ) {
    await run("pod", ["install"]);
  }
  const workspace = ctx.path.join(
    projectDirectory,
    ctx.path.basename(xcodeProject, ".xcodeproj") + ".xcworkspace",
  );
  const result: IosOutput = {
    projectDirectory,
    xcodeProject,
    workspace: (await exists(ctx, workspace)) ? workspace : undefined,
    runnerLibraries: await runnerHashes(ctx, projectDirectory),
  };
  if (isProjectPackage) {
    return result;
  }

  const scheme =
    options.scheme ?? ctx.path.basename(xcodeProject, ".xcodeproj");
  const derivedData = ctx.path.join(buildDir, "DerivedData");
  const common = [
    result.workspace ? "-workspace" : "-project",
    result.workspace ?? xcodeProject,
    "-scheme",
    scheme,
    "-configuration",
    options.configuration ?? "Release",
    "-derivedDataPath",
    derivedData,
    "-jobs",
    String(options.jobs ?? 4),
    ...(options.teamId ? [`DEVELOPMENT_TEAM=${options.teamId}`] : []),
    ...(options.allowProvisioningUpdates ? ["-allowProvisioningUpdates"] : []),
  ];
  result.derivedData = derivedData;
  if (command.type === "package") {
    const archive = ctx.path.join(buildDir, "game.xcarchive");
    const exportDir = ctx.path.join(buildDir, "export");
    await run("xcodebuild", [
      ...common,
      "-destination",
      "generic/platform=iOS",
      "-archivePath",
      archive,
      "archive",
    ]);
    await verifyStagedIosRunner(
      ctx,
      derivedData,
      result.runnerLibraries,
      false,
    );
    await run("xcodebuild", [
      "-exportArchive",
      "-archivePath",
      archive,
      "-exportPath",
      exportDir,
      "-exportOptionsPlist",
      ctx.path.resolve(options.exportOptionsPlist ?? ""),
      ...(options.allowProvisioningUpdates
        ? ["-allowProvisioningUpdates"]
        : []),
    ]);
    const ipas = (await ctx.fs.readdir(exportDir)).filter((name) =>
      name.endsWith(".ipa"),
    );
    if (ipas.length !== 1) {
      throw new KnownError("Xcode did not export exactly one IPA");
    }
    const [ipaName] = ipas;
    if (!ipaName) {
      throw new KnownError("Missing exported IPA");
    }
    let ipa = ctx.path.join(exportDir, ipaName);
    if (command.outputPath) {
      const destination = ctx.path.resolve(
        ctx.path.dirname(inputProject),
        command.outputPath,
      );
      await ctx.fs.copyFile(ipa, destination, ctx.fs.constants.COPYFILE_EXCL);
      ipa = destination;
    }
    result.symbols = (await ctx.fs.readdir(ctx.path.join(archive, "dSYMs")))
      .filter((name) => name.endsWith(".dSYM"))
      .map((name) => ctx.path.join(archive, "dSYMs", name));
    if (!result.symbols.length) {
      throw new KnownError("iOS archive is missing debug symbols");
    }
    result.archive = archive;
    result.ipa = ipa;
  } else {
    const simulator = command.type === "run" ? options.simulatorId : undefined;
    await run("xcodebuild", [
      ...common,
      "-destination",
      simulator ? `id=${simulator}` : "generic/platform=iOS",
      "CODE_SIGNING_ALLOWED=NO",
      "CODE_SIGNING_REQUIRED=NO",
      "build",
    ]);
    await verifyStagedIosRunner(
      ctx,
      derivedData,
      result.runnerLibraries,
      !!simulator,
    );
    if (simulator) {
      const products = ctx.path.join(
        derivedData,
        "Build",
        "Products",
        `${options.configuration ?? "Release"}-iphonesimulator`,
      );
      const apps = (await ctx.fs.readdir(products)).filter((name) =>
        name.endsWith(".app"),
      );
      if (apps.length !== 1) {
        throw new KnownError("Expected exactly one simulator app");
      }
      const [appName] = apps;
      if (!appName) {
        throw new KnownError("Missing simulator app");
      }
      const app = ctx.path.join(products, appName);
      const exec = promisify(ctx.child_process.execFile);
      const { stdout: state } = await exec(
        "xcrun",
        ["simctl", "list", "devices", "available", "--json"],
        { env },
      );
      const devices = z
        .object({
          devices: z.record(
            z.string(),
            z.array(z.object({ udid: z.string(), state: z.string() })),
          ),
        })
        .parse(JSON.parse(state));
      const device = Object.values(devices.devices)
        .flat()
        .find((d) => d.udid === simulator);
      if (!device) {
        throw new KnownError("Requested iOS simulator is unavailable");
      }
      if (device.state !== "Booted") {
        await run("xcrun", ["simctl", "boot", simulator]);
      }
      await run("xcrun", ["simctl", "bootstatus", simulator, "-b"]);
      await run("xcrun", ["simctl", "install", simulator, app]);
      const { stdout: bundle } = await exec("/usr/libexec/PlistBuddy", [
        "-c",
        "Print :CFBundleIdentifier",
        ctx.path.join(app, "Info.plist"),
      ]);
      await run("xcrun", ["simctl", "launch", simulator, bundle.trim()]);
      result.app = app;
      result.simulatorId = simulator;
    }
  }
  return result;
}
