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

## Follow-up: 2.2.23 on both platforms

The earlier build-2 processing poll was stopped after more than two hours without the uploaded build appearing, freeing the job for the user's new Discord-triggered [build 3](https://build.frozenara.com/job/IOM_Deploy/job/ci%252Frunner-releases/3/). Build 2 ended ABORTED after artifact archival; its Apple-side outcome was not confirmed.

Build 3 used game commit `c85e8150cc78338d051374f855d08ab19cf27e88`, including all tagged 2.2.22 game changes, with marketing version 2.2.23 and the same pinned CLI and c1 runtime. Both platform packages passed native runtime/signing verification and were archived with their symbols and provenance.

| Artifact | SHA-256 |
| --- | --- |
| iOS IPA, build 103 | `27380effce36fe33dddf9031039d1f96e7dbc7563bd38f12ffdc19db128c9a64` |
| iOS dSYM ZIP | `28486fb79411e332db45c34556de995c33ad03e64d5bdd948aa9694a4683d8ff` |
| Android AAB | `0875a93b09d9835581d77751fd0dd4aeb07b3b4c321f65c5745fe3f7f7fec690` |
| Android native symbols ZIP | `2f4ede44c17da85c5813f88b77ebda551e41518de37733b3bc02095f01412aab` |

The iOS app/dSYM UUID is `966589B4-3DAB-3874-A2ED-2AC20F8E95A3` (arm64). Apple accepted build 103 at 00:33:19 UTC, finished processing at 00:35:53, and Fastlane confirmed external TestFlight distribution at 00:36:00. The selected App Store submission then failed on mutually exclusive Fastlane `ipa` and `build_number` arguments. IOM commit `0ea1adf29` fixes both delivery paths and supports exact already-uploaded-build recovery; six regression tests passed.

The Android AAB contains only ARM64 and x86_64. Both game libraries have full matching debug information; four vendor libraries retain their available symbol/unwind data. Android delivery stopped because Sentry CLI's `--require-all` incorrectly rejected already stored vendor symbols. IOM commit `da9674c22` removes that CLI switch while preserving independent API verification of every expected debug ID and feature. [Symbol validation build 2](https://build.frozenara.com/job/IOM_Symbol_Validation/2/) passed for all nine iOS and six Android identifiers; its receipts match the exact build-3 manifests. Eleven Python tests passed.

Build 3 remains FAILURE because of the delivery-stage errors. No Play upload or App Store review submission occurred in that original build. Automatic approval review initially blocked the prepared retries because the original acceptance instructions excluded them; the user subsequently reaffirmed the full release, authorizing the recoveries below. The immutable native runner release and published CLI artifact were unchanged.

## Remaining acceptance

- Install TestFlight 2.2.23 (103) and exercise save/load, restart and background/resume on a physical device.
- Install the custom Android package and exercise the equivalent device behaviors.

## Authorized delivery recovery

On 2026-09-16 the user explicitly reaffirmed the full-release request. [Android recovery 1](https://build.frozenara.com/job/IOM_Android_Recovery/1/) successfully uploaded and committed the exact preserved AAB to Play internal testing at 08:15 UTC, with Sentry symbols and release provenance verified. [iOS recovery 1](https://build.frozenara.com/job/IOM_iOS_Recovery/1/) selected the already uploaded 2.2.23 (103) build and submitted it for App Store review at 08:19:54 UTC. Independent API read-back confirmed `WAITING_FOR_REVIEW` and `MANUAL` release. Neither binary was rebuilt. Apple approval and physical-device behavior remain unverified.
