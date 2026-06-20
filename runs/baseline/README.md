# `runs/baseline/` — the committed baseline for the CI gate

`.github/workflows/bench.yml` compares each PR's fresh run against **this**
directory and fails the build on a size/quality regression. This is a
**placeholder**: the `manifest.json` / `summary.json` here are empty, so the gate
passes trivially (nothing to regress against) until you replace them with a real
baseline.

## How to set a real baseline

1. Populate `corpus/images/` and record sha256s (`bench corpus`).
2. Produce a run on the **pinned tools image** for reproducibility:
   ```sh
   just bench-docker            # writes runs/<UTC>-<sha>/
   ```
3. Copy that run's artifacts over this placeholder and commit:
   ```sh
   cp runs/<UTC>-<sha>/{manifest.json,summary.json,sweep.csv,report.md} runs/baseline/
   git add runs/baseline && git commit -m "Set CI baseline from <run-id>"
   ```
4. Re-baseline deliberately (not casually) whenever you intend the new numbers to
   become the reference — e.g. after a tool-version bump. `compare` refuses to
   diff across tool-version drift unless `--allow-version-drift`, so a stale
   baseline fails loudly rather than silently.

The placeholder JSON below is valid against `MANIFEST_SCHEMA` so the CI step runs
cleanly before a real baseline exists.
