# Test corpus

Small, fixed, **version-controlled** set. Every size/speed claim in this
benchmark is read off these exact bytes, so the corpus is part of the result —
its aggregate sha256 is recorded in every run's `manifest.json`.

Verify the committed set at any time with `bench corpus`, which recomputes each
sha256 and checks it against this file.

All committed photos are **CC0 or public domain** (license-clean for a public
repo), fetched from Wikimedia Commons by [`fetch_cc0.py`](fetch_cc0.py) and
curated by [`prepare_public_corpus.sh`](prepare_public_corpus.sh) (resize to
≤2048px, metadata-strip, synthetic-EXIF injection). The alpha logo is generated;
the screenshots are self-captured. No image carries GPS or personal data.

## The set

| file | kind | why it's included | source · license | sha256 |
|------|------|-------------------|------------------|--------|
| `photo_foliage.png` | emerging fern frond, macro | high-freq detail + bokeh | [Wikimedia](https://commons.wikimedia.org/wiki/File:Close-up_of_Emerging_Fern_Frond_in_Spring.jpg) · Girela770 · **CC0** | `cdb2f486756f…1e4bfff6` |
| `photo_sky.png` | dark-to-light blue sky | smooth gradient (banding stress) | [Wikimedia](https://commons.wikimedia.org/wiki/File:Dark_to_light_blue_sky.jpg) · TheUltimateGrass · **CC0** | `ac18cedbb555…619b9019` |
| `photo_portrait.png` | 1940s color photo, woman at a lathe | skin-tone chroma + detail | [Wikimedia](https://commons.wikimedia.org/wiki/File:Woman_lathe_operator_in_the_1940s.jpg) · Howard R. Hollem (LoC) · **Public domain** | `c751b0d6e68a…ef180e40` |
| `photo_lowlight.png` | Quebec city at dusk, lit tower | low-light noise + dark gradients | [Wikimedia](https://commons.wikimedia.org/wiki/File:%C3%89difice_Price_at_night,_Quebec_city,_Canada.jpg) · Wilfredor · **CC0** | `22bd0ae644e4…090bd8098` |
| `photo_exif.jpg` | autumn leaves, w/ synthetic EXIF | metadata-strip lane (tools must drop EXIF) | [Wikimedia](https://commons.wikimedia.org/wiki/File:Colorful_leaves_in_autumn.jpg) · Tbk1101 · **CC0** | `3b8dcf2b87a6…ab9cd016` |
| `alpha_logo.png` | generated RGBA, real transparency | transparency-correctness check | generated · **CC0** | `dfa0c16e1726…0d4bdae6` |
| `screenshot_ui.png` | macOS Calculator (scientific) UI — flat color, buttons, sharp edges | lossless/near-lossless path | self-captured · **CC0** | `8e282db7b40d…57bdebc7` |
| `screenshot_text.png` | editor / terminal, dense text | text edges, palette path | self-captured · **CC0** | _TODO — pending capture_ |

(Truncated hashes shown for readability; `bench corpus` prints/checks the full
64-hex digests, which are the source of truth.)

## Notes

- **`photo_exif.jpg`** carries *synthetic* EXIF (`Make=imgbench`, `Model=TestCam
  EXIF`, a date) and **no GPS** — just enough metadata for the strip lane to have
  something to strip, with nothing personal.
- **Screenshots** are self-captured of your own editor/terminal (license-clean,
  no third-party creative content or account identifiers). Drop them into
  `corpus/images/`, then run `bench corpus` to fill the two `TODO` hashes above.
- The **personal-photo corpus** lives locally in `corpus/local/` (gitignored,
  never published); run it with `just run-local`.

## Deliberately excluded corpora

- **Kodak** — murky/contested redistribution license.
- **CID22** — Cloudinary's subjective dataset; SSIMULACRA 2's weights were tuned
  partly on it, so grading against it would bias the grader.
