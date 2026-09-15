# Exact custom mobile runtimes

The Checkbox fork supports mobile YYC builds using `GMS2@A.B.C.D-cN`, with lowercase `c` and a positive revision. Stock versions remain available. Custom desktop and VM builds fail explicitly.

```sh
gm-cli runtime resolve --version 2024.14.4.268-c1 --platforms ios,android --output /new/release
gm-cli package Game.yyp --target ios --runtime native \
  --toolchain GMS2@2024.14.4.268-c1 --runtime-lock /new/release/lock.json \
  --result-file /new/ios-result.json
```

Private releases come from `Checkbox-Entertainment-LTD/GMS2-Runner-Main`. Supply `GH_TOKEN` (or the Jenkins-bound `GIT_PASSWORD`) through the environment. Interactive use can use an existing `gh` login. Python 3.9+ is required.

Resolution requires a published immutable release, an exact source tag, both mobile package entries, and matching GitHub asset sizes and SHA-256 hashes. It downloads and verifies every requested package before writing a lock. Package manifests bind all files, source, official base, build recipe, dependencies, toolchains and native-validation reports. Archive member headers and iOS XCFramework metadata must cover device ARM64 and simulator ARM64/x86_64, or Android ARM64/x86_64. Unsafe archive paths, links, extra libraries, missing platforms and unavailable versions fail without fallback.

Pass the same lock to all workers. `compile --preflight` verifies availability, modules and replacements without compiling a game; iOS preflight can run on Linux. A worker rechecks package and base-library hashes while creating its own isolated runtime and build cache. Existing official runtime files are never replaced. A cache containing the old Android signing wrapper is rejected; choose a fresh `--cache-dir`.

The official base's bundled Igor runs the build. A separately downloaded ProjectTool restores project resources; the build result records both tool hashes. The result also includes runtime identity, custom source/artifact/manifest hashes, replacement library hashes and exact output paths. Set `GM_GAME_COMMIT` in CI to bind game source. Build results are written only after success, and existing output/result files are rejected.

For iOS, the CLI installs and verifies the custom framework inside the newly generated project. See [iOS support](IOS.md). For Android, set `android.packageType` to `aab` explicitly; upstream defaults to APK. Use `--toolchain-options-file` with a mode-600 temporary JSON file for keystore configuration, then remove it. The CLI protects and deletes its temporary settings/license directory.

Delivery checks are separate from native publication:

```sh
gm-cli runtime verify-ios --result ios-result.json --derived-data /isolated/DerivedData \
  --ipa IOM.ipa --symbols IOM.app.dSYM.zip --output ios-provenance.json
gm-cli runtime verify-android --result android-result.json --aab IOM.aab \
  --keystore /protected/key.keystore --alias SIGNING_ALIAS --output android-provenance.json
```

The Android check reads `ANDROID_KEYSTORE_PASSWORD` from the environment. It verifies native architectures, the AAB signature and the selected signing certificate. The iOS check verifies the staged runner and matching app/dSYM UUIDs. Delivery records contain package hashes and runtime/source identity. Game behavior on real devices still requires a separate acceptance record.
