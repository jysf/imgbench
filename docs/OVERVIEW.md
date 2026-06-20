# imgbench — overview

**One page. What it is, why it exists, and where to look next.**

## What

A small, reproducible benchmark that compares image-optimization tools
**fairly** — by holding *perceptual quality* constant and reading off bytes and
time. The subject under test is **crustyimg**; the yardsticks are **rimage** (the
closest 1:1 Rust CLI), **sharp** (the ecosystem baseline), and the single-format
encoders (`cwebp`, `avifenc`, `cjpeg`/MozJPEG, `oxipng`, `pngquant`).

## The one rule (non-negotiable)

> Every size/speed number is gated on **equal SSIMULACRA2** — never an equal
> quality-*number*. A smaller file at a *different* score is not a result.

Fixed-quality tools have no perceptual target, so for each tool×image the harness
**sweeps** the quality knob, **grades** every output with an *independent*
SSIMULACRA2 build, and **interpolates the bytes at the target score** (80 and
90). That interpolation is the fairness keystone.

## The shape

- **Lanes.** Lossy photo lane (WebP/AVIF/JPEG, full sweep + interpolation);
  lossless PNG lane (oxipng vs sharp, one operating point); lossy palette PNG
  lane (pngquant, a real sweep).
- **Grader independence.** crustyimg optimizes against the Rust `ssimulacra2`
  crate, so the default grader is the *Cloudinary C reference* — grading on the
  same implementation would be teaching-to-the-test. A built-in agreement check
  confirms the two implementations track each other.
- **Immutable runs.** Every run writes `runs/<UTC>-<bench-sha>/` and never
  overwrites; `manifest.json` captures machine, tool/grader versions, and corpus
  hashes so any number is traceable.
- **Gated comparison.** `bench compare A B` diffs two runs, flags size/quality
  regressions, and exits non-zero so CI can fail the build.

## Run it

```sh
just check        # what's installed (works with zero tools)
just run          # timed sweep -> a versioned run dir + markdown report
just run-fast     # throughput mode for size-gated CI (timing not recorded)
just compare runs/<A> runs/<B>
just test         # 44 unit/integration tests, no external tools needed
```

Core is **Python 3.14 stdlib only** (runs in CI with no venv). Unix/macOS only.

## Where to look next

| You want to… | Read |
|---|---|
| Run it / add a tool / see all flags | [`README.md`](../README.md) |
| Understand *why it's fair* (the methodology) | [`benchmark-methodology.md`](../benchmark-methodology.md) |
| Understand *how the code is built* | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |
| Know the corpus + its licenses | [`corpus/CORPUS.md`](../corpus/CORPUS.md) |
| Reproduce exact tool versions | [`tools/tools.lock.md`](../tools/tools.lock.md) |
