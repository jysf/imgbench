# tools.lock — exact versions used for reproducible runs

Human-readable companion to `Dockerfile`. Every benchmark run records the
*actual* resolved versions in its `manifest.json`; this file documents the
*intended* pins. When they diverge, `bench compare` flags version drift and
refuses to diff (unless `--allow-version-drift`).

| component | role | pinned version / commit | source | notes |
|---|---|---|---|---|
| **ssimulacra2** (C ref, libjxl) | **primary grader** | Debian trixie `libjxl-devtools` (libjxl 0.11.x) | `apt install libjxl-devtools` | canonical C impl (Jon Sneyers); reads PNG/JPEG — outputs are decoded to PNG before grading (`bench/decode.py`) |
| butteraugli_main (libjxl) | visually-lossless cross-check | Debian trixie `libjxl-devtools` | `apt install libjxl-devtools` | ships alongside ssimulacra2 |
| ssimulacra2_rs | grader cross-check only | **omitted** | `cargo install ssimulacra2_rs` | needs vapoursynth + fontconfig; agreement check records "not installed" |
| dssim | cross-check | TODO | `cargo install dssim` | optional |
| rimage | contender (1:1) | 0.12.3 (**fails to install** — see note) | `cargo install rimage` | non-fatal in Dockerfile; investigate build before relying on it |
| sharp-cli | contender (ecosystem baseline) | 4.2.0 | `npm i -g sharp-cli` | Node + libvips; report cold-start separately |
| cwebp (libwebp) | single-format WebP | 1.5.0 | `apt install webp` | provides `dwebp` (used to decode for grading) |
| avifenc (libavif) | single-format AVIF | 1.2.1 | `apt install libavif-bin` | provides `avifdec` (decode for grading); match `--speed` to shared effort |
| cjpeg (MozJPEG) | single-format JPEG | 4.1.1 (built from source) | build mozjpeg | MUST be MozJPEG's cjpeg, NOT libjpeg-turbo's — they differ in output size |
| oxipng | lossless PNG | 9.1.2 | `cargo install oxipng` | |
| pngquant | lossy palette PNG | 2.18.0 | `apt install pngquant` | |
| **crustyimg** (subject) | subject under test | TODO `0.1.x` + commit | build locally | MUST build `--features webp-lossy,avif` |
| Rust toolchain | builds the above | stable (1.96.0 at last build) | rustup | pin to an exact version once the build is settled |
| Node | sharp runtime | 20.x (Debian trixie) | apt | |
| Python | harness runtime | 3.14.x | `python:3.14-slim-trixie` base image | core is stdlib-only; see `.python-version` |

## crustyimg build requirement

```
cargo build --release --features webp-lossy,avif
```

The default build encodes WebP **losslessly only**. Benchmarking that against
lossy WebP from rimage/sharp/cwebp is apples-to-oranges. The harness's
`feature_check` fails the run if a lossy comparison is requested against a
crustyimg whose reported features lack `webp-lossy`/`avif`.

## How to refresh this file

1. Set the `ARG …_VERSION` pins in `Dockerfile`.
2. `just bench-docker` (or `docker build -f tools/Dockerfile .`).
3. Inside the image, `bench check` prints resolved versions; copy them here and
   into the relevant `ARG` so image + doc agree.
