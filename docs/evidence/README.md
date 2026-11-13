# Model integration evidence

This directory preserves actual observations, not just a list of proposed checks. No model was trained, refitted, substituted or modified by these checks.

## Initial integration run

`20261113T105419Z/` records a fresh run initiated on 13 November 2026:

- `evidence.json`: start/end times, every command and exit status, raw-log SHA-256 values, installed dependency versions, Git HEAD, dirty working-tree status, source-file fingerprints, full archive fingerprint and per-version artifact fingerprints.
- `model-structure.json`: fitted estimator types/classes/tree counts, raw and transformed preprocessing feature names, widths and agreement with the supplied schemas. V1 has 5 raw/13 transformed inputs; V2 has 14/22.
- `pytest.xml`: machine-readable current pytest outcomes, including both model-helper parity tests, V1 golden-score agreement, permissions, persistence, null imputation, missing/tampered artifacts and configuration diagnostics.
- `00.log`–`08.log`: actual command output; the Playwright JSON reporter is in `08.log` after the npm preamble. It includes individual browser test outcomes and aggregate counts.

The run identifies an uncommitted working tree, not a clean released commit. Fingerprints identify the exact source tested. Archive/member hashes pin supplied artifacts; locally generated hashes establish identity and subsequent tamper detection, not independent scientific validation or a third-party signature. The V1 model/pipeline hashes also agree with fingerprints in the teammate's supplied report. Model performance figures quoted elsewhere come from teammate reports and were not re-estimated here.

`source-access.json` separately records source-documentation/download HEAD probes. All were blocked by CONNECT 403 and retrieved no provider data. It is not evidence of successful dataset access, licensing verification or location-based raster extraction. See [the feature-to-source table](../FEATURE_SOURCES.md).

## Reproduce

Prepare the standard environment and separate test databases using the README. Stop development API/frontend processes (Playwright owns ports 8000/4173), then from the checkout root run:

```bash
backend/.venv/bin/python scripts/capture-model-evidence.py
```

The script creates a new timestamped directory, verifies supplied file fingerprints, runs the listed commands without suppressing failures, preserves each exit code/log and returns nonzero if any command fails. Test success demonstrates software integration only. It does not demonstrate compatible raster extraction, model calibration, independent validation or warning capability. Avoid simultaneously running another suite against the same test databases.

## Supplied-example and incident-response milestone

`20261113T112652Z/` preserves the later milestone run, with the same command/log/hash format. It adds example isolation/reference checks, reported evaluation context, and verified-incident association/deployment checks. Earlier evidence is retained unchanged; consult each run's `evidence.json` for its exact sources and command outcomes. See `../MILESTONE_DEMO.md` for the reproducible application walkthrough.

`20261113T112840Z/` is the subsequent run after adding explicit column-header scope to the evaluation table. The preceding `20261113T112652Z/` run is retained with its one browser accessibility assertion failure (42 Python checks passed; 22 browser checks passed and one failed). Do not treat that earlier run as fully passing. Final outcomes are in each run's command records and, when present, `outcomes.json`.

The `20261113T112840Z/` run passed the table-header check but exposed a separate version-switching issue: the prior example remained visible. That run also has one browser failure and is retained. After fixing example state handling, the focused example test passed. `20261113T113120Z/` captures the subsequent full run of the final code; use its recorded command statuses rather than assuming every earlier run passed.

The `20261113T113120Z/` full run passed all new milestone tests, but an existing offline account-switching test failed: trace evidence showed POST /api/reports succeeded after GET /api/records/reports had already returned, leaving the visible list stale. The focused offline test passed on retry, confirming timing sensitivity. The application now refreshes the report list after queue completion instead of depending on ordering. `20261113T113333Z/` captures the full run after that correction. Prior failures remain retained and must not be reported as all-pass runs.

Final milestone outcome: `20261113T113333Z/outcomes.json` confirms 42 Python tests and 23 browser tests passed (zero browser failures/skips), with all recorded command exit codes zero and log hashes verified. This is the passing evidence bundle for the current milestone.

## Current report-first response run

`20261113T132736Z/outcomes.json` records 50 passed Python checks and 25 passed browser tests, with all command exit codes zero. Source and log hashes were verified. It supersedes the earlier monitoring-location-required UI walkthrough; historical evidence is preserved unchanged. See `../MILESTONE_DEMO.md` for the current report-first workflow and stated limitations.

## Coordinate extraction integration

`20261113T164942Z/outcomes.json` records 58 Python and 27 browser tests passed with verified source/log hashes. Eight Python cases are synthetic raster tests. Real-data acceptance is separately gated by `npm run prepare:rasters` in the Codespace holding the large archive; it is explicitly unrun here. `20261113T164546Z` retains the earlier failed browser selector run. The small extraction handoff is pinned by `model-handoff/extraction-sha256.txt`; the large rasters remain private local files and are not committed. See `../AUTOMATIC_ASSESSMENT.md`.

## Shared location-picker run

`20261113T172700Z/outcomes.json` records 58 passed Python and 31 passed browser tests, with no unexpected/skipped browser outcomes and all command exit codes zero. Source/log hashes were verified. It covers confirm/cancel semantics across raw coordinate forms and explicit existing-record map selection. See `../MAP_PICKERS.md`. Real raster acceptance remains separate from synthetic raster tests.
