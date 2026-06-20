# Contributing to imgbench

Thanks for helping make the benchmark more rigorous. The bar for this repo is
unusual: **fairness and reproducibility come before features.** A change that
makes the numbers prettier but the comparison less fair is a regression.

## The one rule

Every size/speed number is gated on **equal SSIMULACRA2**, never an equal
quality-number. If your change could let a tool "win" at a *different* perceptual
score, it's wrong. See [`benchmark-methodology.md`](benchmark-methodology.md) and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Before opening a PR

```sh
just test        # 44 unit/integration tests — must stay green (no external tools needed)
just dry-run     # if you touched an adapter, eyeball the emitted commands
```

- Core stays **Python 3.14 standard library only**. Anything else goes behind
  `requirements-optional.txt` and an opt-in flag. (Ask before adding a core dep.)
- New behavior needs a test. Use the synthetic-image / fake-encoder patterns in
  `tests/` so tests need no installed encoders.

## Adding a tool or metric

- **Tool:** new `bench/adapters/<tool>.py` subclassing `Adapter`; honour the
  `EncodeConfig` fairness knobs (threads, AVIF effort, metadata strip); register
  it. Walkthrough in the README.
- **Metric:** new `bench/grade/<metric>.py` subclassing `Grader`; register it.
- **Verify flags against the installed version** with `--dry-run` — encoders
  change CLI flags between releases.

## Corpus changes (read this — the repo is public)

The corpus is committed and public. Any image you add is visible forever in git
history. Before adding one:

- It must be **redistributable** — record source URL + license + sha256 in
  `corpus/CORPUS.md`. No Kodak (murky license), no CID22 (biases the grader).
- **Scrub privacy.** Screenshots must contain no secrets/personal data. The
  EXIF-oriented phone photo intentionally keeps metadata — make sure its **GPS
  doesn't reveal a sensitive location** (take it somewhere neutral, or rewrite
  the GPS tag to a benign coordinate while keeping the orientation flag).

## License

By contributing you agree your contribution is dual-licensed under
**MIT OR Apache-2.0** (see [`LICENSE`](LICENSE)).
