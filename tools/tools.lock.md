# tools.lock — exact versions used for reproducible runs

Human-readable companion to `Dockerfile`. Every benchmark run records the
*actual* resolved versions in its `manifest.json`; this file documents the
*intended* pins. When they diverge, `bench compare` flags version drift and
refuses to diff (unless `--allow-version-drift`).

| component | role | pinned version / commit | source | notes |
|---|---|---|---|---|
| **ssimulacra2** (C ref, via libjxl) | **primary grader** | libjxl `v0.11.1` (built in Dockerfile) | github.com/libjxl/libjxl `tools/ssimulacra2` | the canonical C implementation (Jon Sneyers); NOT the Rust crate crustyimg optimises against |
| ssimulacra2_rs | grader cross-check only | `0.5.0` | `cargo install ssimulacra2_rs` | used solely for the agreement sanity-check |
| butteraugli (libjxl) | visually-lossless cross-check | TODO | libjxl | optional |
| dssim | cross-check | TODO | `cargo install dssim` | optional |
| rimage | contender (1:1) | 0.11.0 (TODO confirm) | `cargo install rimage` | shares fast_image_resize + kamadak-exif with crustyimg |
| sharp-cli | contender (ecosystem baseline) | 4.2.0 (TODO) | `npm i -g sharp-cli` | Node + libvips; report cold-start separately |
| cwebp (libwebp) | single-format WebP | TODO | `apt install webp` | |
| avifenc (libavif) | single-format AVIF | TODO | `apt install libavif-bin` | match `--speed` to shared effort |
| cjpeg (MozJPEG) | single-format JPEG | TODO | build mozjpeg (or a pkg that ships MozJPEG's cjpeg) | MUST be MozJPEG's cjpeg, NOT libjpeg-turbo's — they differ in output size |
| oxipng | lossless PNG | 9.1.2 (TODO) | `cargo install oxipng` | |
| pngquant | lossy palette PNG | TODO | `apt install pngquant` | |
| **crustyimg** (subject) | subject under test | TODO `0.1.x` + commit | build locally | MUST build `--features webp-lossy,avif` |
| Rust toolchain | builds the above | 1.79.0 (TODO) | rustup | pin so codegen doesn't drift |
| Node | sharp runtime | TODO | apt | |
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
