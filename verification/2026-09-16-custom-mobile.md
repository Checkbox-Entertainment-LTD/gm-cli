# IOM custom mobile runtime acceptance - 2026-09-16

This record covers the real game and delivery flow. Native publication is recorded separately in the runner repository; successful publication alone does not establish game behavior.

## iOS: actual Discord submission

- Jenkins: [IOM_Deploy/ci/runner-releases/2](https://build.frozenara.com/job/IOM_Deploy/job/ci%252Frunner-releases/2/).
- User submitted Discord `/build` for `ci/runner-releases`, with iOS and TestFlight selected. Android, Play and App Store submission were disabled; Jenkins parameters confirmed these selections.
- Game commit: `c155290051c414fcb17aca3af5d50715d952540f`.
- Runtime note: `2024.14.4.268-c1`, official base `2024.14.4.268`.
- CLI: `checkbox-2.3.0-mobile.1`, artifact SHA-256 `b41a30d98d8fcc9626321479f5c82efde7c28bef8502f236978e636aae39214f`.
- Node 24.18.0; Xcode 26.1.1 (17B100).
- Marketing version `2.2.21`; app-wide reserved build number `102`.
- Immutable runner release `389506427`, manifest SHA-256 `89fe80d83df9b7c1b11eb862822a91c872da632e4d7693492c644bff6eeae0af`.
- Runner source: `e842ab09f758cf2d2fe441ddb6437111d22e526c`.

The pinned CLI installed the exact official runtime modules, verified the expected base library hashes, assembled the custom runtime in an isolated invocation, generated a fresh Xcode project and installed the custom XCFramework. Fastlane archived and exported a signed IPA using a temporary signing keychain. The keychain was removed after export; no login-keychain changes were needed.

### Verified delivery artifacts

| Item | SHA-256 |
| --- | --- |
| Consumed device runner | `acb752de8f96d0d16e30a6f4447131a05030d182ee64fda35d3f7451d6897914` |
| Simulator library inventory | `42e4d716e65d1b6d2dbc6e1b7b3628c2752be5cbc59720a1385c986898a43e1a` |
| IPA | `2e5564c0c2503664ba990634713097f9f07348bbf4bcd50b04b5a65953077852` |
| Canonical dSYM ZIP | `14b423f8ca965f281814e987b9d07c3404a8862657008cc0ae46001af1e3a741` |

App and dSYM UUID: `593967B9-019B-3833-9827-FB047C247560` (`arm64`). Bundle identifier: `com.checkbox.idleobeliskminer`.

Independent `codesign --verify --deep --strict` verification passed after extracting the exported IPA. The signing identity is `Apple Distribution: Checkbox Entertainment LTD (87MP2AWGBS)` and the team and bundle identifiers match the expected app.

Jenkins archived the IPA, dSYMs and provenance before starting upload. The archived IPA and canonical dSYM ZIP were independently downloaded and their hashes matched the provenance. Copies and CLI/provenance records are preserved under the numbered local validation record `ci-runner-releases-2`.

App Store Connect accepted the upload at `2026-09-15T22:20:23Z`. Apple processing and TestFlight distribution are still pending at this checkpoint; upload acceptance is not a claim of availability to testers.

### Download behavior observed

The coordinator preflights on Linux in `.gm-preflight-2`; the Mac builds in `.gm-ios-2`. The CLI disables shared caching when an explicit cache directory is supplied, so each worker downloads the common and iOS official modules. Their host tool modules differ. Both assemble the same verified c1 release; the second official-base download is not a stock fallback. The current pipeline does not reuse official module downloads across these two stages.

## Remaining acceptance

- Confirm Apple processing, TestFlight distribution and final Jenkins result.
- Install build 102 and exercise save/load, restart and background/resume on a physical device.
- Run Android through Discord on the same integration branch with Play upload disabled; verify the signed AAB, c1 provenance and ARM64/x86_64 coverage.
