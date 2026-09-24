# iOS Real-Device Deep Link Testing Runbook

This runbook documents the real-device testing workflow for the existing `healthquantification://export-all` route. It covers sequential Xcode signing, in-place installation, deep-link launch and database readback. It is not a replacement for simulator XCTest or a general-purpose iOS automation skill. A successful app launch alone is not evidence of export.

## Scope And Authorization

- This flow sends actual HealthKit samples to the already configured, authorized Tailnet backend. Do not use it for a read-only diagnostic or against an untrusted server.
- Simulator UI tests use fixtures; they cannot validate the real HealthKit store, permissions, or phone-to-backend network path.
- Do not copy device logs, personal readings, endpoint URLs, signing identifiers, or screenshots into Git or a public PR.

## Preconditions

The FastAPI backend is a separately managed service, not hot-reloaded when its Python files change. Check `/health` and `/openapi.json` on the running instance before testing a new metric; never start a second process on its port. The app persists its server URL in `AppStorage`; the default `http://localhost:7996` points to the **iPhone**, not the Mac. Before a headless run, configure an authorized, phone-reachable Tailnet URL in the app UI. A Mac-only health check does not prove iPhone reachability.

Ensure the iPhone is paired, connected, unlocked, and already authorized to read the exported HealthKit types. Keep the same bundle ID and development team; do not delete the app to refresh a build.

## Build, Install, Launch

Build and install sequentially. Use an ignored `tmp/` location for all derived files, and substitute the connected device's UDID without recording it in public files:

```bash
mkdir -p tmp/ios_device_qa
xcodebuild -project HealthQuantification/HealthQuantification.xcodeproj \
  -scheme HealthQuantificationIOS -configuration Debug \
  -destination 'platform=iOS,id=<DEVICE_UDID>' \
  -derivedDataPath tmp/ios_device_qa/DerivedData build

xcrun devicectl device install app --device '<DEVICE_UDID>' \
  tmp/ios_device_qa/DerivedData/Build/Products/Debug-iphoneos/HealthQuantificationIOS.app

xcrun devicectl device process launch --device '<DEVICE_UDID>' \
  --terminate-existing --payload-url 'healthquantification://export-all' \
  --json-output tmp/ios_device_qa/launch.json com.yage.HealthQuantificationIOS
```

`Info.plist` registers `healthquantification` and the app accepts `export-all` / `export/all` (with an optional strict OpenCode callback). `--console` waits for a newly launched app to exit and may contain unrelated OS messages, so it is not a bounded completion protocol.

## Verified Real-Device Run

- A signed physical build was installed in place via `devicectl`. The install output reported `launchServicesIdentifier: unknown`, but launch by bundle ID succeeded; do not treat that field alone as a failure.
- `devicectl device copy from --domain-type appDataContainer` retrieved the app's Preferences plist into ignored scratch. The stored backend URL was unchanged after installation. Copying a future diagnostic JSON artifact has **not** been implemented or tested.
- `devicectl --payload-url 'healthquantification://export-all'` launched the app; its JSON result showed process launch, **not** completion of the URL handler. Immediately afterward, backend write times advanced for sleep, vitals, activity and workouts. Body and lifestyle had no recent samples to send. Readback confirmed the new vitals metrics' units and unique source IDs without publishing raw data.

## Evidence Of Success

Capture a **small aggregate** before and after, not a full `/ingest/{type}` dump of private samples. The local SQLite file is ignored by Git; check that the CLI's configured DB path corresponds to the active backend. For example:

```bash
sqlite3 -readonly data/health_quantification.db \
  'SELECT metric_type, count(*), max(updated_at) FROM vitals_samples GROUP BY metric_type;'
```

- Check that `sleep`, `vitals`, `activity`, and `workouts` have recent write activity or explain why not; `body` and `lifestyle` can legitimately skip when the window contains no samples.
- Compare the new vitals metrics' units, counts, source UUID uniqueness, and backend readback. A repeat export is idempotent: unchanged counts alone do **not** prove the deep link failed; inspect write timestamps or a bounded app-owned completion signal.
- Check `/health` again, and distinguish an app dispatch failure from a phone-to-backend connection failure (especially a stale `localhost` URL).

If no evidence appears after launch, inspect the strict URL parser, permission/query errors, and the saved server URL. A manual tap of `Export All Data` can isolate deep-link delivery from HealthKit or network issues, but is a fallback, not a passed headless test. Never infer success from `devicectl` exit code alone. Preserve only minimal, ignored local QA evidence.
