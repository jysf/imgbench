#!/usr/bin/env sh
# prepare_public_corpus.sh — turn the CC0/PD downloads (corpus/images/_dl/,
# gitignored) into the committed public photo slots: resize to <=2048px long
# edge, convert photo lanes to PNG, strip ALL metadata, and inject synthetic
# benign EXIF (no GPS) on the metadata-strip slot.
#
# Run `python3 corpus/fetch_cc0.py` first to populate _dl/. Requires macOS
# `sips` + `exiftool`. Screenshots + alpha_logo are produced separately.

set -eu
cd "$(dirname "$0")/.."          # -> imgbench/
IMG=corpus/images
DL=$IMG/_dl

echo "== photo lanes (resize 2048, -> PNG, strip metadata) =="
for slot in photo_foliage photo_sky photo_portrait photo_lowlight; do
  sips -s format png -Z 2048 "$DL/$slot.jpg" --out "$IMG/$slot.png" >/dev/null
  exiftool -all= -overwrite_original "$IMG/$slot.png" >/dev/null 2>&1 || true
  echo "  $slot.png"
done

echo "== metadata-strip slot (resize, strip, inject synthetic benign EXIF) =="
sips -Z 2048 "$DL/photo_exif_src.jpg" --out "$IMG/photo_exif.jpg" >/dev/null
exiftool -all= -overwrite_original "$IMG/photo_exif.jpg" >/dev/null 2>&1 || true
# Inject benign, GPS-free EXIF so the strip lane has something to strip.
exiftool -overwrite_original \
  -Make="imgbench" -Model="TestCam EXIF" -Software="imgbench corpus" \
  -DateTimeOriginal="2026:01:01 12:00:00" -Artist="imgbench" \
  -Orientation#=1 "$IMG/photo_exif.jpg" >/dev/null 2>&1 || true
echo "  photo_exif.jpg (synthetic EXIF, no GPS)"

echo "Done. Verify: bench corpus"
