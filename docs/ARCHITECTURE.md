# Architecture

How the code is built — module responsibilities, the run lifecycle, the data
model, the design decisions and their rationale, the concurrency invariants, and
the extension points. For *why the benchmark is fair* (the methodology), see
[`benchmark-methodology.md`](../benchmark-methodology.md); for *how to use it*,
see [`README.md`](../README.md).

---

## 1. Design goals (what every decision serves)

1. **Equal-quality gating is sacred.** Bytes/time are only meaningful at a fixed
   perceptual score. The code must never let a tool "win" at a different score.
2. **Reproducible & traceable.** Any number must be attributable to an exact
   machine, tool version, grader, and corpus. Runs are immutable.
3. **Runs in CI with no venv.** The core is **Python standard library only**.
   Optional extras (plotting) are quarantined behind `requirements-optional.txt`.
4. **Honest about its own limits.** Where a comparison can't be perfectly fair
   (Node startup, codec effort, metric monoculture), the harness records the
   caveat rather than hiding it.

---

## 2. Module map

```
bench/
  __init__.py        package version + MANIFEST_SCHEMA
  cli.py             argparse entrypoint; orchestrates a run; owns run-dir lifecycle
  imageio.py         stdlib PNG writer + PNG/JPEG/WebP/AVIF/GIF header probing
  measure.py         per-process wall-clock (best-of-N) + peak RSS; load/throttle warn
  sweep.py           coarse sweep + bisection refine + interpolation + BD-rate (the core)
  validate.py        output-validity checks (dimensions + alpha preserved)
  provenance.py      manifest: machine, tool/grader versions, corpus hashes
  report.py          write sweep.csv / summary.json; render report.md
  compare.py         diff two runs; regression gate; version-drift refusal
  footprint.py       per-tool binary size, deps, runtime, cold-install
  adapters/          one module per encoder (the .cmd() pattern)
    base.py          Adapter ABC + EncodeConfig (the fairness knobs)
    rimage/sharp/cwebp/avifenc/mozjpeg/oxipng/crustyimg.py
  grade/             pluggable perceptual metrics
    base.py          Grader ABC
    ssimulacra2.py   C reference (primary) + Rust (cross-check only)
    butteraugli.py / dssim.py
    cache.py         content-addressed score cache (GradeCache + CachingGrader)
```

**Dependency direction.** `cli` depends on everything; `sweep` depends on
`measure`/`validate`; `adapters` and `grade` depend on nothing else in the
package (leaf modules). `imageio` is a leaf used by `validate` and the tests.
There are no cycles.

### Responsibilities, sharply divided

- **Adapters describe *how to drive a tool*** — they build a command string and
  declare format support. They never run anything and never decide the sweep.
- **`measure` runs and times a command** — and only that. It knows nothing about
  quality or formats.
- **`grade` scores two images** — a pure metric. It knows nothing about encoders.
- **`sweep` is the brain** — it asks adapters for commands, hands them to
  `measure`, hands outputs to `grade` and `validate`, and turns the points into
  RD curves and bytes-at-target.
- **`cli` owns the run** — selection, the immutable run dir, provenance,
  parallelism policy, and writing artifacts.

This separation is what makes adding a tool or a metric a one-file change.

---

## 3. The run lifecycle (`bench run`)

```
cli.cmd_run
  ├─ find_images()                     collect corpus sources
  ├─ select grader (default: C ref)    + wrap in CachingGrader unless --no-grade-cache
  ├─ crustyimg feature gate            fail loudly if lossy run vs lossless-only build
  ├─ warn_if_loaded()                  loadavg / CPU-governor sanity warning
  ├─ make_run_dir()                    runs/<UTC>-<sha>/ ; update runs/latest symlink
  ├─ run_agreement_check()             C vs Rust SSIMULACRA2 agree within tol (RAW graders)
  ├─ for each (adapter, format, image) work unit:
  │     sweep_image()                  << the core; see §4 >>
  ├─ compute_bd_rates()                each tool vs an anchor, per (fmt, image)
  ├─ build_manifest()                  machine + versions + corpus hash + footprint + cache stats
  └─ write manifest.json / sweep.csv / summary.json / report.md  (+ copy report to reports/)
```

**Two execution policies** (chosen in `cli`, executed by `sweep_image`):

- **Timed (default).** Work units run **serially and uncontended** so wall-clock
  is trustworthy. Within a unit, grading is parallel (see §6).
- **Fast (`--fast`).** `best-of-1` and work units run **concurrently** across
  cores for throughput. Timing is *not recorded* (`Point.timing is None`,
  manifest `timing_trustworthy: false`). Bytes are deterministic, so the RD
  curve is identical — this mode is for size/quality gating only.

---

## 4. The sweep (`sweep.py`) — the fairness keystone

For one `adapter × image × format`:

1. **Coarse pass.** Encode at each quality in `adapter.quality_range(fmt)`.
   Phase 1 encodes *all* points (serial, timed); Phase 2 grades+validates them
   (parallel). Splitting the phases is what keeps grading from contending with a
   timed encode (§6).
2. **Bisection refine.** For each target score (80/90), find the two coarse
   points that bracket it, then do a few extra encodes between them to tighten
   the bytes-at-target estimate. Sequential, because each step needs the prior
   score.
3. **Interpolate.** `interp_bytes_at_score()` linearly interpolates bytes at the
   exact target between the bracketing points; out-of-range targets return a
   flagged `"~N (extrapolated …)"` string (never silently wrong).
4. **BD-rate.** `bd_rate()` integrates `log10(bytes)` over the overlapping
   quality range (cubic Bjøntegaard via a stdlib least-squares `_polyfit` +
   Gaussian elimination), giving one quality-normalized number.

**Numeric core is pure and unit-tested without encoders:**
`interp_bytes_at_score`, `bracket_for_target`, `bd_rate`, `_polyfit`. The
orchestration around them (`_encode_only`, `_grade_and_validate`, `sweep_image`)
is covered by the fake-encoder integration tests.

**Validity feeds the curve.** `_usable()` excludes any point whose output failed
the dimension/alpha check, so a tool that silently drops alpha or resizes can't
score a bytes "win" — its invalid points simply aren't on the curve.

---

## 5. Data model

| Type | Where | Holds |
|---|---|---|
| `Point` | sweep | one quality point: quality, bytes, score, timing, validity, refined-flag |
| `SweepResult` | sweep | coarse[] + refined[] points, per-target interpolations, bd_rate_vs |
| `RunStats` | measure | post-warmup timing samples → min / median / MAD, peak RSS |
| `Validity` | validate | ok + dims_preserved + alpha_preserved + notes |
| `EncodeConfig` | adapters | the fairness knobs (threads, avif_effort, strip_metadata) |
| `GradeCache` | grade | content-addressed score memo (`OrderedDict`, LRU, JSON-persisted) |

**On-disk artifacts (per run):**

- `manifest.json` — provenance; `compare` reads it to detect version drift.
- `sweep.csv` — every point (coarse + refined), flat; the source for plots.
- `summary.json` — structured results; the contract `compare` consumes.
- `report.md` — rendered human report.

`MANIFEST_SCHEMA` (in `bench/__init__.py`) versions the manifest/summary shape;
`compare` refuses to diff across schema mismatches.

---

## 6. Concurrency & timing-integrity invariants

The one rule that must never break:

> **Grading (or any non-timed subprocess) must never run while an encode is
> being timed.** CPU contention from a concurrent grader would corrupt the
> wall-clock.

How the code guarantees it:

- In **timed mode**, `sweep_image` encodes the *entire* coarse sweep serially
  **first**, then grades in a `ThreadPoolExecutor` (`--grade-jobs`). Grading runs
  only after that image's timed encodes are done, and `sweep_image` blocks until
  grading finishes before returning — so the *next* unit's encodes can't overlap
  it either. Work units themselves run serially in timed mode.
- The bisection refine grades inline between its (few) timed encodes — identical
  to the original design, and no worse than it: a grade completes before the next
  timed encode starts.
- In **fast mode**, timing isn't recorded, so the contention constraint doesn't
  apply and encodes run concurrently for throughput.

Threads are the right primitive here: every encode and grade is a *subprocess*,
so the GIL is released during the work. The only shared mutable state under
threads is `GradeCache`, which guards its dict and file writes with a
`threading.Lock`.

---

## 7. The grade cache (`grade/cache.py`) — why caching is safe here

Caching results in a *benchmark* sounds dangerous; it's safe because of exactly
what is and isn't cached.

- **Cached:** only the grader's score, a *pure deterministic function* of two
  exact image byte-streams + the grader. SSIMULACRA2 is deterministic.
- **Not cached:** bytes (always `stat()`'d fresh from the new output) and timing
  (always measured fresh).
- **Key:** `sha256(source) + sha256(output) + grader name + grader version +
  CACHE_SCHEMA`. Change one byte of either image, or the grader, and the key
  changes → miss → recompute. A stale score for different bytes is impossible by
  construction.
- **Keyed on content, not path** — a deterministic encoder emitting identical
  bytes across runs legitimately has the same score; recomputing would only burn
  CPU for the same number.
- **Invalidation/clearing:** never by time; by key (content/grader change), LRU
  prune over `max_entries`, `bench cache --clear`, `--no-grade-cache`, or a
  `CACHE_SCHEMA` bump. The agreement check uses the **raw** graders, bypassing
  the cache, so it can never be hidden by it.

`CachingGrader` wraps any `Grader` and delegates identity (name/version/
availability), so the rest of the harness can't tell it's cached.

---

## 8. Provenance & comparison

- **`provenance.build_manifest`** captures CPU model / core counts / RAM, OS +
  kernel, CPU governor + turbo state (Linux), every tool's and grader's version,
  per-image + aggregate corpus sha256, crustyimg build features, the agreement
  result, footprint, and the run config (incl. mode + cache stats).
- **`compare.compare_runs`** indexes each run's `summary.json` into
  `(tool, fmt, image, metric) → (value, kind)`, computes deltas, and flags
  regressions. It separates **size/quality** (gate-worthy; deterministic) from
  **speed** (informational by default; noisy). It **refuses to diff** runs whose
  tool/grader versions drifted unless `--allow-version-drift` — a byte delta
  across encoder versions isn't a clean result. Non-zero exit gates CI.

---

## 9. Extension points

- **Add an encoder:** new `bench/adapters/<tool>.py` subclassing `Adapter`;
  implement `cmd()`, honour the `EncodeConfig` fairness knobs, set `lossless` /
  `writes_to_dir` as needed; register in `adapters/__init__.py`. See the README
  walkthrough. `--dry-run` prints commands to verify flags against your version.
- **Add a metric:** new `bench/grade/<metric>.py` subclassing `Grader`
  (`higher_is_better` + `identical_score` let the harness reason about
  direction); register in `grade/__init__.py`.
- **Add an operation** (e.g. responsive sets, batch throughput): extend `sweep`
  or add a sibling; crustyimg's `responsive_cmd` is a stubbed example.

---

## 10. Testing strategy

No external tools are needed to test. Two techniques:

- **Synthetic images.** `imageio.write_png` emits real PNGs (RGB/RGBA), so tests
  exercise validity checks and corpus hashing for free.
- **Fake encoder + grader.** `tests/test_integration.py` ships a one-line PNG
  "encoder" (a real subprocess whose output size scales with quality and whose
  quality marker the fake grader reads back). This drives the *entire*
  orchestration — sweep, bisection, parallel grading, fast mode, report, compare
  — end to end, deterministically, on any machine.

Pure-numeric tests (`test_sweep.py`) lock down interpolation/BD-rate;
`test_cache.py` proves the cache's content-addressing and invalidation;
`test_compare.py` proves the regression gate and version-drift detection;
`test_provenance.py` proves manifest shape and the crustyimg feature gate.

---

## 11. Known gaps / roadmap

- **Whole-corpus batch throughput** and **cold-start vs warm** separation are
  only partially built (warmup-discard exists; a true single-invocation batch
  op does not).
- **Responsive-set generation** is stubbed (`crustyimg.responsive_cmd`) pending
  the shipped CLI.
- **Adapter flags** are written against recent tool versions and must be
  verified with `--dry-run` against the installed builds.
- **crustyimg** itself is stubbed until SPEC-016; activation is one line
  (`CRUSTYIMG_BIN`).
