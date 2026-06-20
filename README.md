# imgbench

A small, rigorous, reproducible benchmark for image-optimization tools.

**The one non-negotiable rule:** every size and speed number is gated on **equal
perceptual quality (SSIMULACRA2)** — never on an equal quality-*number*. A
smaller file at a *different* score is not a result; it's a confound. We pin the
quality axis and read off bytes and time.

The harness compares **crustyimg** (the subject) against **rimage** (the fairest
1:1 Rust CLI), **sharp** (the ecosystem baseline), and the single-format
encoders (`cwebp`, `avifenc`, `oxipng`, `pngquant`). Full reasoning lives in
[`benchmark-methodology.md`](benchmark-methodology.md).

---

## Quickstart

```sh
# 1. See what's installed (works with ZERO tools — reports them missing)
just check                 # or: python3 -m bench check

# 2. Print the exact encode commands without running them
just dry-run

# 3. Run the sweep against the corpus -> a new immutable runs/<UTC>-<sha>/ dir
just run                   # writes manifest.json, sweep.csv, summary.json, report.md

# 4. Diff two runs; exits NONZERO on a size/quality regression (CI gate)
just compare runs/<A> runs/<B>

# 5. Verify the committed corpus hashes
just corpus-verify

# 6. Tests (no external tools needed — synthetic images)
just test
```

The core is **Python 3.14 standard library only**, so it runs in CI with no
venv. (The stdlib-only core also runs on 3.11+, but 3.14 is what's pinned and
tested — `justfile`, `tools/Dockerfile`, and `.python-version` all point at it.)
The sole optional extra is plotting (`scripts/plot.py`, needs
`requirements-optional.txt`).

> **Platform:** Unix/macOS only — measurement uses `os.wait4` for per-child peak
> RSS. **Windows is unsupported.**

---

## The equal-quality protocol (why this is fair)

The contenders have *different control surfaces*. crustyimg can target a
SSIMULACRA2 score directly; rimage/sharp/cwebp/avifenc only take a fixed quality
number. Comparing "crustyimg hits 90" to "rimage at q=80" is the single most
likely way to produce a misleading result. Instead, for every fixed-quality
tool the harness:

1. **Sweeps** the quality parameter (coarse pass, `bench/sweep.py`).
2. **Grades** each output with an *independent* SSIMULACRA2 build.
3. **Interpolates** the byte count at the exact target score (80 and 90 by
   default), then **bisection-refines** near each target to tighten the estimate.
4. Optionally reports a single-number **BD-rate** across the whole curve.

Two operating points: **≈90** (visually-lossless) and **≈80** (high-but-lossy).

### Grader independence (anti-collusion)

crustyimg optimizes against the Rust `ssimulacra2` crate. Grading with that same
implementation would be teaching-to-the-test, so the **default grader is the
Cloudinary C reference** (`ssimulacra2`). The harness also runs an **agreement
check**: it confirms the C and Rust implementations track each other within
tolerance on a few images and records the result in `manifest.json`.

### crustyimg build requirement

crustyimg **must** be built with lossy codecs:

```sh
cargo build --release --features webp-lossy,avif
```

The default build encodes WebP losslessly only. If you request a lossy
comparison against a lossless-only crustyimg, the run **fails loudly**
(`bench/adapters/crustyimg.py:feature_check`).

---

## Run versioning & provenance

Every `run` writes to an **immutable** `runs/<UTC-timestamp>-<bench-git-sha>/`
and updates the `runs/latest` symlink — nothing is ever overwritten. Each run's
`manifest.json` captures:

- CPU model, physical/logical cores, RAM, OS + kernel, CPU governor / turbo state
- every tool's and grader's version string (and which grader binary graded)
- corpus sha256 (per-image + aggregate)
- crustyimg's `--version` + build features
- the grader-agreement result and the footprint snapshot

`bench compare` reads two manifests back and **refuses to diff runs whose tool
versions drifted** (override with `--allow-version-drift`) — a byte delta across
encoder versions isn't a clean result.

---

## Running it many times (performance)

The harness is **subprocess-bound** — it spends ~all its time spawning encoder
and grader binaries, so the levers are *fewer*, *cached*, and *parallel*
subprocess calls (Python-level speed is irrelevant here). Three controls, none
of which compromise the equal-quality gate:

- **Persistent grade cache** (on by default). Memoizes the *deterministic*
  SSIMULACRA2 score keyed on `sha256(source) + sha256(output) + grader
  version`. It caches **only scores** — never bytes (stat'd fresh) or timing
  (measured fresh). Re-running the same corpus with a deterministic encoder
  yields byte-identical outputs → 100% cache hits → no re-grading. Invalidated
  automatically by any content/grader change; clear with `bench cache --clear`;
  bypass with `--no-grade-cache` (do this for a final authoritative result).

- **Parallel grading in timed mode** (`--grade-jobs`, default = CPU count).
  Grading runs *after* each image's timed encodes complete, so it never
  contends with — and never corrupts — a wall-clock measurement.

- **Fast/throughput mode** (`--fast`). For **size/quality-gated** runs (your CI
  gate): `best-of-1` (bytes are deterministic, so the RD curve is *identical*)
  plus encodes parallelized across cores (`--jobs`). Dramatically faster, but
  **wall-clock is not recorded** — the run is flagged `timing_trustworthy:false`
  in its manifest. Use timed mode (the default) when you need speed numbers.

```sh
just run                       # timed + cached + parallel grading (trustworthy timing)
just run-fast                  # fast: size/quality only, maximum throughput
bench cache --clear            # wipe the score cache
```

## Activating crustyimg (one line)

The adapter is stubbed until SPEC-016 ships. To activate, point it at the binary
— no code edit needed:

```sh
export CRUSTYIMG_BIN=../path/to/target/release/crustyimg
just run --tools crustyimg rimage sharp
```

(or set `CrustyImg.binary` in `bench/adapters/crustyimg.py`).

---

## Adding a tool

1. Create `bench/adapters/<tool>.py` subclassing `Adapter`:

   ```python
   from .base import Adapter, EncodeConfig

   class MyTool(Adapter):
       name, binary, formats = "mytool", "mytool", ("webp", "avif")

       def cmd(self, inp, outp, fmt, q, cfg: EncodeConfig):
           cmd = [self.binary, "--quality", str(q), "--threads", str(cfg.threads)]
           if fmt == "avif":
               cmd += ["--effort", str(cfg.avif_effort)]   # equal effort across tools
           if cfg.strip_metadata:
               cmd += ["--strip"]                          # so byte deltas aren't EXIF
           return cmd + [str(inp), "-o", str(outp)]
   ```

   - Set `lossless = True` for one-operating-point tools (oxipng-style).
   - Set `writes_to_dir = True` if the tool writes into a directory rather than a
     file path; the runner normalises the produced file to one output path.
   - Honour the `EncodeConfig` **fairness knobs** (`threads`, `avif_effort`,
     `strip_metadata`) or the comparison isn't clean.

2. Register it in `bench/adapters/__init__.py` (`ADAPTERS` list).
3. `just dry-run --tools mytool` to review the commands against your installed
   version *before* a real run. **Always verify CLI flags against the version you
   have** — encoders change flags between releases (rimage's output handling,
   avifenc `-q` vs `--min/--max`, sharp-cli `--compressionLevel`).

---

## Where each methodology rule lives

| Rule | Code |
|---|---|
| Equal-SSIMULACRA2 gate, interpolation, bisection, BD-rate | `bench/sweep.py` |
| Independent grader (C ref default) + agreement check | `bench/grade/` |
| Wall-clock best-of-N, median + MAD, warmup discard, affinity, load warning | `bench/measure.py` |
| Fairness knobs (threads / AVIF effort / metadata strip) | `bench/adapters/base.py` |
| crustyimg `--features webp-lossy,avif` gate | `bench/adapters/crustyimg.py` |
| Provenance manifest (machine, versions, corpus hash) | `bench/provenance.py` |
| Output validity (dims + alpha preserved) | `bench/validate.py`, `bench/imageio.py` |
| Run versioning + immutable dirs + `latest` symlink | `bench/cli.py` |
| Regression gate, version-drift refusal, size-vs-speed split | `bench/compare.py` |
| Footprint (binary size, deps, runtime, cold install) | `bench/footprint.py` |
| Grade cache (content-addressed, deterministic-safe) | `bench/grade/cache.py` |
| Parallel grading (timed mode) + fast throughput mode | `bench/sweep.py`, `bench/cli.py` |

---

## Reproducibility

`tools/Dockerfile` pins exact encoder + grader versions; `tools/tools.lock.md`
documents them. `just bench-docker` runs the benchmark inside the pinned image.
CI (`.github/workflows/bench.yml`) gates on **size/quality only** — wall-clock is
too noisy on GitHub-hosted runners and is gated only on a pinned self-hosted
runner.

## Commands

```
bench check                          report tool/grader availability
bench run    [--inputs DIR] [...]    sweep -> versioned run dir
bench compare RUN_A RUN_B [...]      delta report + CI gate (nonzero on regression)
bench corpus [--corpus DIR]          verify corpus sha256 + probe images
bench footprint [--cold-install]     per-tool footprint snapshot
bench cache [--clear]                inspect or clear the grade cache
```

Useful `run` flags: `--formats webp avif png`, `--targets 80 90`, `--best-of 5`,
`--warmup 1`, `--threads 1`, `--avif-effort 6`, `--pin-cpu N` (taskset, Linux),
`--no-strip`, `--grader ssimulacra2`, `--tools rimage sharp`, `--dry-run`,
`--fast`, `--jobs N`, `--grade-jobs N`, `--no-grade-cache`, `--grade-cache PATH`.

## License

Dual-licensed under either of:

- Apache License, Version 2.0 ([`LICENSE-APACHE`](LICENSE-APACHE))
- MIT license ([`LICENSE-MIT`](LICENSE-MIT))

at your option — matching crustyimg's `MIT OR Apache-2.0` profile and the
Rust-ecosystem norm. Unless you explicitly state otherwise, any contribution
intentionally submitted for inclusion in this work shall be dual-licensed as
above, without any additional terms or conditions.
