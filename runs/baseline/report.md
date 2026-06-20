# Benchmark run `20260620T072527Z-nogit`

> Every size/speed number below is gated on **equal SSIMULACRA2**, never an equal quality-number. Bytes are read off at a fixed perceptual score; a smaller file at a different score is not a result.

## Environment

- **CPU:** None (None physical / 14 logical)
- **RAM:** 7.7 GiB
- **OS:** Linux 6.12.76-linuxkit  ·  kernel `#1 SMP Fri May 29 10:00:01 UTC 2026`
- **CPU scaling:** governor=None, turbo=None
- **Primary grader:** `ssimulacra2` (independent C reference by default)
- **Bench:** v0.1.0 @ `nogit`

_Grader agreement: second SSIMULACRA2 implementation not installed; cross-check skipped_

## Fairness controls

- threads pinned to **1**, AVIF effort **6** across all tools
- metadata stripping: **True** (byte deltas are not EXIF/ICC)
- timing: best-of-5 after 1 warmup, median + MAD reported

> ⚠️ **Fast mode** (`--fast`): best-of-1, parallel encodes. Bytes/quality are exact, but **wall-clock here is NOT trustworthy** — use this run for size/quality gating only.

- grade cache: 744 hit / 126 miss (scores memoized by content hash; never bytes or timing)

## Bytes at equal SSIMULACRA2

### AVIF

| image | tool | @ss2≈80 | @ss2≈90 |
|---|---|---|---|
| alpha_logo.png | `avifenc` | ~3129 (extrapolated @ score 82.0) | 3.9 KiB |
| alpha_logo.png | `sharp` | ~3140 (extrapolated @ score 82.2) | 3.9 KiB |
| photo_exif.jpg | `avifenc` | 610.2 KiB | 990.7 KiB |
| photo_exif.jpg | `sharp` | 546.4 KiB | 915.7 KiB |
| photo_foliage.png | `avifenc` | 93.9 KiB | 366.4 KiB |
| photo_foliage.png | `sharp` | 89.3 KiB | 330.3 KiB |
| photo_lowlight.png | `avifenc` | 363.5 KiB | 1073.4 KiB |
| photo_lowlight.png | `sharp` | 349.8 KiB | 1003.0 KiB |
| photo_portrait.png | `avifenc` | 194.4 KiB | 679.4 KiB |
| photo_portrait.png | `sharp` | 188.4 KiB | 641.0 KiB |
| photo_sky.png | `avifenc` | 48.3 KiB | 337.0 KiB |
| photo_sky.png | `sharp` | 46.7 KiB | 305.1 KiB |
| screenshot_text.png | `avifenc` | ~133160 (extrapolated @ score 82.2) | 210.2 KiB |
| screenshot_text.png | `sharp` | ~124588 (extrapolated @ score 82.9) | 194.1 KiB |
| screenshot_ui.png | `avifenc` | 18.1 KiB | 34.2 KiB |
| screenshot_ui.png | `sharp` | 18.1 KiB | 33.5 KiB |

### JPEG

| image | tool | @ss2≈80 | @ss2≈90 |
|---|---|---|---|
| alpha_logo.png | `cjpeg` | — | — |
| alpha_logo.png | `sharp` | — | — |
| photo_exif.jpg | `cjpeg` | 588.0 KiB | 1087.4 KiB |
| photo_exif.jpg | `sharp` | 685.9 KiB | 1101.1 KiB |
| photo_foliage.png | `cjpeg` | 151.5 KiB | 401.8 KiB |
| photo_foliage.png | `sharp` | 163.2 KiB | 450.5 KiB |
| photo_lowlight.png | `cjpeg` | 507.3 KiB | 1481.6 KiB |
| photo_lowlight.png | `sharp` | 537.7 KiB | ~1742173 (extrapolated @ score 86.1) |
| photo_portrait.png | `cjpeg` | 310.2 KiB | 1024.0 KiB |
| photo_portrait.png | `sharp` | 345.2 KiB | 945.9 KiB |
| photo_sky.png | `cjpeg` | 72.8 KiB | 580.8 KiB |
| photo_sky.png | `sharp` | 95.2 KiB | 600.5 KiB |
| screenshot_text.png | `cjpeg` | 348.9 KiB | 746.2 KiB |
| screenshot_text.png | `sharp` | 428.3 KiB | 622.5 KiB |
| screenshot_ui.png | `cjpeg` | 72.6 KiB | 175.7 KiB |
| screenshot_ui.png | `sharp` | 91.9 KiB | ~239695 (extrapolated @ score 88.8) |

### PNG

| image | tool | @ss2≈80 | @ss2≈90 |
|---|---|---|---|
| alpha_logo.png | `pngquant` | 12.9 KiB | 14.2 KiB |
| photo_exif.jpg | `pngquant` | — | — |
| photo_foliage.png | `pngquant` | ~842867 (extrapolated @ score 74.7) | ~842867 (extrapolated @ score 74.7) |
| photo_lowlight.png | `pngquant` | ~1239717 (extrapolated @ score 70.0) | ~1239717 (extrapolated @ score 70.0) |
| photo_portrait.png | `pngquant` | ~1834768 (extrapolated @ score 76.9) | ~1834768 (extrapolated @ score 76.9) |
| photo_sky.png | `pngquant` | 453.7 KiB | 1050.8 KiB |
| screenshot_text.png | `pngquant` | ~94713 (extrapolated @ score 87.4) | 97.7 KiB |
| screenshot_ui.png | `pngquant` | 38.9 KiB | 46.5 KiB |

### WEBP

| image | tool | @ss2≈80 | @ss2≈90 |
|---|---|---|---|
| alpha_logo.png | `cwebp` | 9.7 KiB | ~15148 (extrapolated @ score 81.0) |
| alpha_logo.png | `sharp` | 9.7 KiB | ~15148 (extrapolated @ score 81.0) |
| photo_exif.jpg | `cwebp` | 656.4 KiB | 1366.4 KiB |
| photo_exif.jpg | `sharp` | 656.4 KiB | 1366.4 KiB |
| photo_foliage.png | `cwebp` | 144.2 KiB | ~430356 (extrapolated @ score 86.6) |
| photo_foliage.png | `sharp` | 144.2 KiB | ~430356 (extrapolated @ score 86.6) |
| photo_lowlight.png | `cwebp` | 490.6 KiB | ~955774 (extrapolated @ score 84.1) |
| photo_lowlight.png | `sharp` | 490.6 KiB | ~955774 (extrapolated @ score 84.1) |
| photo_portrait.png | `cwebp` | 321.5 KiB | ~905308 (extrapolated @ score 87.4) |
| photo_portrait.png | `sharp` | 321.5 KiB | ~905308 (extrapolated @ score 87.4) |
| photo_sky.png | `cwebp` | 91.9 KiB | ~362138 (extrapolated @ score 87.2) |
| photo_sky.png | `sharp` | 91.9 KiB | ~362138 (extrapolated @ score 87.2) |
| screenshot_text.png | `cwebp` | 180.6 KiB | ~459214 (extrapolated @ score 89.6) |
| screenshot_text.png | `sharp` | 180.6 KiB | ~459214 (extrapolated @ score 89.6) |
| screenshot_ui.png | `cwebp` | 38.5 KiB | ~92910 (extrapolated @ score 88.2) |
| screenshot_ui.png | `sharp` | 38.5 KiB | ~92910 (extrapolated @ score 88.2) |

## Lossless PNG lane (bytes + speed at score ~100)

| image | tool | bytes | score | median ms |
|---|---|---|---|---|
| alpha_logo.png | `oxipng` | 23.5 KiB | 100.00 | — |
| alpha_logo.png | `sharp-png` | 31.7 KiB | 100.00 | — |
| photo_exif.jpg | `oxipng` | — | — | — |
| photo_exif.jpg | `sharp-png` | 6905.9 KiB | 100.00 | — |
| photo_foliage.png | `oxipng` | 1860.1 KiB | 100.00 | — |
| photo_foliage.png | `sharp-png` | 2888.6 KiB | 100.00 | — |
| photo_lowlight.png | `oxipng` | 3339.5 KiB | 100.00 | — |
| photo_lowlight.png | `sharp-png` | 4524.8 KiB | 100.00 | — |
| photo_portrait.png | `oxipng` | 3560.4 KiB | 100.00 | — |
| photo_portrait.png | `sharp-png` | 5544.4 KiB | 100.00 | — |
| photo_sky.png | `oxipng` | 1134.3 KiB | 100.00 | — |
| photo_sky.png | `sharp-png` | 1511.6 KiB | 93.01 | — |
| screenshot_text.png | `oxipng` | 241.4 KiB | 100.00 | — |
| screenshot_text.png | `sharp-png` | 250.3 KiB | 100.00 | — |
| screenshot_ui.png | `oxipng` | 106.8 KiB | 100.00 | — |
| screenshot_ui.png | `sharp-png` | 107.2 KiB | 100.00 | — |

## BD-rate (vs anchor, % bytes at equal quality — negative is better)

| image | format | tool | anchor | BD-rate % |
|---|---|---|---|---|
| alpha_logo.png | avif | `avifenc` | `sharp` | +0.3% |
| alpha_logo.png | webp | `sharp` | `cwebp` | +0.0% |
| photo_exif.jpg | avif | `avifenc` | `sharp` | +10.7% |
| photo_exif.jpg | jpeg | `cjpeg` | `sharp` | -13.0% |
| photo_exif.jpg | webp | `sharp` | `cwebp` | +0.0% |
| photo_foliage.png | avif | `avifenc` | `sharp` | +3.7% |
| photo_foliage.png | jpeg | `cjpeg` | `sharp` | -15.9% |
| photo_foliage.png | webp | `sharp` | `cwebp` | +0.0% |
| photo_lowlight.png | avif | `avifenc` | `sharp` | +2.7% |
| photo_lowlight.png | jpeg | `cjpeg` | `sharp` | -15.3% |
| photo_lowlight.png | webp | `sharp` | `cwebp` | +0.0% |
| photo_portrait.png | avif | `avifenc` | `sharp` | +1.8% |
| photo_portrait.png | jpeg | `cjpeg` | `sharp` | -12.4% |
| photo_portrait.png | webp | `sharp` | `cwebp` | +0.0% |
| photo_sky.png | avif | `avifenc` | `sharp` | -4.0% |
| photo_sky.png | jpeg | `cjpeg` | `sharp` | -41.5% |
| photo_sky.png | webp | `sharp` | `cwebp` | +0.0% |
| screenshot_text.png | avif | `avifenc` | `sharp` | +6.9% |
| screenshot_text.png | jpeg | `cjpeg` | `sharp` | -13.0% |
| screenshot_text.png | webp | `sharp` | `cwebp` | +0.0% |
| screenshot_ui.png | avif | `avifenc` | `sharp` | +1.1% |
| screenshot_ui.png | jpeg | `cjpeg` | `sharp` | -22.5% |
| screenshot_ui.png | webp | `sharp` | `cwebp` | +0.0% |

## Output validity

Per-point dimension/alpha checks are in `sweep.csv` (`valid` column). Invalid outputs are excluded from the curves above.

## Methodology

See [`benchmark-methodology.md`](../../benchmark-methodology.md). Footprint, startup-vs-batch, and the quality-sweep scatter are additional artifacts in this run dir.

