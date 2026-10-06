# Real-Device HealthKit Export Profiling

## Overview and Scope

This document defines the tooling and methodology for profiling automated 30-day HealthKit exports on physical iOS hardware. Profiling exercises the live application export pipeline against the existing authorized Tailnet backend, rather than local diagnostic stubs or synthetic mocks.

The objective is to obtain repeatable end-to-end timings across client and server phases. Profile artifacts contain aggregate metrics, not individual health readings.

## CLI Runner Contract

Activate the project's virtual environment and run:

```bash
source .venv/bin/activate
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  python scripts/ios_profile.py --device '<paired-phone>' --configuration Release --runs 5 --warmup 1
```

The defaults are Release, three measured runs, and one discarded warmup. `--skip-build-install` enables reruns without redeploying. `--cold` restarts the app before each iteration; it does not clear persistent OS or backend caches. Build and installation preserve the existing bundle, preferences, and backend configuration. The runner shares a nonblocking build/probe lock with `scripts/ios_probe.py`.

## URL Trigger and Artifact Boundary

Profiling uses the dedicated URL `healthquantification://profile-export?run_id=<UUID>`. Parsing accepts exactly one UUID parameter and no server override. Standard exports do not instantiate the profiler, create profile files, or transmit profiling headers.

Artifacts contain durations, item counts, payload byte sizes, export status and failed category names. They do not contain sample fields, endpoint URLs, error descriptions or ECG waveforms. Atomic progress and final artifacts live in `Library/Caches/ExportProfiles/<UUID>.json`, with iOS Complete File Protection. The host retrieves them under ignored `tmp/ios_device_qa/profiles/`; do not commit artifacts or device logs. The app removes profile files older than 24 hours upon a later completion.

Progress snapshots are throttled to at most one per second on event completion. They are not a continuous heartbeat during a stalled query. A terminal artifact, not a successful process launch, proves completion.

## Host Polling and Validation

The host verifies the UUID, schema, finite nonnegative durations, and terminal export status `success`. All seven categories must have fetch spans: sleep, vitals, body, lifestyle, activity, workouts and ECG. For every category, accepted record counts must equal sent counts; empty categories may skip uploading. These counts represent processed records, not newly inserted records. Failures, partial exports, a busy app, invalid artifacts and timeouts exit nonzero.

The runner reports progress while polling and produces a summary with p50, nearest-rank p90, phase totals, and per-run sample counts. Repeated spans, such as one HTTP transaction per ECG record, are summed within each run before computing percentiles.

## Timing Accounting

The export total starts immediately before category fetches and ends during terminal snapshot preparation. It excludes process startup, host dispatch and polling, and the final file write/cleanup. Client durations use monotonic nanosecond timestamps; backend durations use `perf_counter`.

Fetch spans cover authorization, local queries, conversion and sorting. Vitals has separate query, map and sort spans. Encoding records request size and sample count. HTTP spans cover the request/response operation, while `URLSessionTaskMetrics` exposes connect, send, wait and receive intervals. These intervals are useful observations, not independent pure-wire measurements.

Valid `X-Health-Profile: <UUID>` headers opt into backend `Server-Timing`: total and initialize for ingest routes, plus convert, upsert and count for vitals. Backend total includes request-body reception and validation. It overlaps client send/wait phases and must not be added to HTTP or network totals. Detailed endpoint spans exclude body parsing and validation.

`profiling.progress_overhead` measures event recording and progress snapshots, including lock acquisition. It excludes the terminal snapshot and cleanup. The measured progress overhead was approximately 51 ms median, below 1% of the corresponding roughly 9.5-second baseline. Keep instrumentation opt-in; ordinary exports perform no snapshot I/O.

## Comparison Rules and Baseline Findings

Discard warmup runs. Compare p50 and nearest-rank p90 on the same phone, OS, build configuration, network and backend. For five measurements p90 is the maximum; this is an engineering check, not a production-tail guarantee. Compare sample counts because a rolling 30-day window can change slightly between sessions. Fetch and nested query/map spans overlap; do not sum parent and child spans.

The baseline identified per-record date formatter allocation during client conversion and full historical `SELECT *` materialization for backend counting as optimization candidates. A subsequent optimization change will report verification against this method. Raw records, personal sample counts and benchmark traces remain private.
