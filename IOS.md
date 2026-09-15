# iOS builds in the Checkbox fork

This fork merges upstream gm-cli 2.3.0 (`93364a2455c2`) and uses upstream's Android SDK, APK/AAB and keystore support. iOS builds run locally on a Mac with Xcode. CocoaPods must be available on PATH when the generated project has a Podfile.

## Generate a project for Fastlane

```sh
gm-cli package Game.yyp --target ios --runtime native \
  --toolchain GMS2@2024.14.4.268 \
  --output /absolute/new-project-directory \
  --result-file /absolute/new-result.json
```

The default iOS package is a **directory containing a verified Xcode project**, with extension framework ZIPs prepared and `pod install` run when needed. The output directory and result file must be new. Omitting `--output` keeps the project under the fresh build invocation directory. The result's `outputs.projectDirectory`, `outputs.xcodeProject` and optional `outputs.workspace` are authoritative; callers must not search old IDE or cache directories.

Igor's remote build and Organizer launch are suppressed. A copied IDE `devices.json`, fake device, SSH password, and remote Mac configuration are unnecessary for this local flow. Each invocation has separate generated files, local settings and Xcode DerivedData. Temporary license/settings copies are protected and removed when the invocation finishes.

## Compile and run

`gm-cli compile Game.yyp --target ios --runtime native` generates the project, prepares dependencies and runs a full unsigned Xcode device build. This checks native linking as well as GML compilation.

To build, install and launch on an installed simulator:

```sh
gm-cli run Game.yyp --target ios --runtime native \
  --toolchain-options '{"ios":{"simulatorId":"YOUR-SIMULATOR-UDID"}}'
```

Select a simulator UDID from `xcrun simctl list devices available`. Physical-device installation and distribution remain available through Xcode or the delivery pipeline.

## Signed IPA export

```sh
gm-cli package Game.yyp --target ios --runtime native \
  --toolchain-options-file /private/ios-options.json \
  --output /absolute/new-game.ipa --result-file /absolute/new-result.json
```

Example options:

```json
{
  "ios": {
    "packageType": "ipa",
    "teamId": "ABCDEFGHIJ",
    "signingIdentity": "Apple Distribution",
    "provisioningProfile": "Your App Store profile",
    "exportOptionsPlist": "/private/ExportOptions.plist",
    "developerDir": "/Applications/Xcode.app/Contents/Developer",
    "configuration": "Release",
    "allowProvisioningUpdates": false
  }
}
```

Xcode must already have the required signing identity and provisioning profile. Manual signing uses the Ruby `xcodeproj` gem (installed with CocoaPods) to configure only the generated app target. Omit both `signingIdentity` and `provisioningProfile` to use Xcode automatic signing. The export plist controls the signing/export method. The CLI archives and exports locally; it does not upload to App Store Connect. Jenkins can instead request the default project output and use Fastlane for signing and upload.

The JSON result identifies the archive, IPA and symbols. Native builds verify the runner library staged in Xcode's products against the generated project's hash before export or simulator installation.

Other iOS options: `scheme` overrides the inferred scheme; `podInstall: false` leaves CocoaPods preparation to the caller. Options can be saved under `gms2.ios` in `gm-options.json`, or supplied as an `ios` object using the CLI option flags. File-based options keep secrets out of command arguments. Never commit signing passwords.

## Verification

`npm test` covers output discovery, stale and ambiguous outputs, framework extraction, path traversal, conflicts, symlinks, configuration and staged runner identity. `npm run build` type-checks and bundles the distributable CLI. Native validation is performed with the real IOM project; see the integration acceptance record for verified and outstanding modes.
