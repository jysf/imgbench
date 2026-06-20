# Test corpus

Small, fixed, **version-controlled** set. Every size/speed claim in this
benchmark is read off these exact bytes, so the corpus is part of the result —
its aggregate sha256 is recorded in every run's `manifest.json`.

**License rule:** every image must be redistributable, and its source URL +
license + sha256 recorded below. Two corpora are **deliberately excluded**:

- **Kodak** — murky/contested redistribution license.
- **CID22** — Cloudinary's subjective dataset; SSIMULACRA 2's weights were tuned
  partly on it, so grading our outputs against images drawn from it would bias
  the grader (metric-circularity). Keep the corpus independent of CID22.

Verify the committed set at any time with `just corpus-verify` (or
`bench corpus`), which recomputes each sha256 and checks it against this file.

## Composition (the agreed set)

| # | file | kind | why it's included | source URL | license | sha256 |
|---|------|------|-------------------|-----------|---------|--------|
| 1 | `photo_foliage.png`   | photo — high-freq foliage   | exercises lossy WebP/AVIF on detail | TODO (imagecompression.info "New Test Images") | TODO ("may be used freely … not for resale" — record exact text) | TODO |
| 2 | `photo_sky.png`       | photo — smooth gradient sky | banding / smooth-gradient stress      | TODO (imagecompression.info "New Test Images") | TODO | TODO |
| 3 | `photo_portrait.png`  | photo — skin tones          | chroma fidelity on skin               | TODO (imagecompression.info "New Test Images") | TODO | TODO |
| 4 | `photo_lowlight.png`  | photo — low-light noise     | noise retention vs smearing           | TODO (imagecompression.info "New Test Images") | TODO | TODO |
| 5 | `screenshot_ui.png`   | PNG screenshot — flat UI    | lossless / palette path; sharp text   | TODO (self-captured)        | CC0 (own capture) | TODO |
| 6 | `screenshot_text.png` | PNG screenshot — dense text | text edges, palette PNG               | TODO (self-captured)        | CC0 (own capture) | TODO |
| 7 | `phone_exif.jpg`      | EXIF-oriented phone photo   | auto-orient + metadata-strip path     | TODO (self-captured)        | CC0 (own capture) | TODO |
| 8 | `alpha_logo.png`      | alpha PNG                   | transparency-correctness check        | TODO (self-made)            | CC0 (own creation) | TODO |

Notes:

- Photos 1–4 come from **imagecompression.info → "New Test Images"** (redistributable,
  no-sell license — record the exact license text in the table, not just "no-sell").
- Keep originals ≥ 2–3 MP so encode time is measurable and not startup-dominated.
- `phone_exif.jpg` MUST retain its orientation flag + GPS/EXIF so the
  metadata-strip lane has something to strip.
- `alpha_logo.png` MUST have a real alpha channel; the output-validity check
  fails any encode that drops it.

## Filling in the TODOs

1. Drop the eight files into `images/`.
2. Run `bench corpus --corpus .` (or `just corpus-verify`) — it prints each
   file's real sha256.
3. Paste each sha256 into the table above and record the precise source URL +
   license string. The verifier then passes (exit 0).

`fetch_corpus.sh` can pull + subset the imagecompression.info ZIPs so the large
originals don't have to be committed; the redistributable subset does.
