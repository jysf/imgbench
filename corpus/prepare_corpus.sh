#!/usr/bin/env sh
# prepare_corpus.sh — turn the raw staging pile (corpus/images/initial_import,
# corpus/images/screenshots — both gitignored) into the curated, privacy-scrubbed
# corpus slot files that ARE committed (corpus/images/*.{png,jpg}).
#
# What it does:
#   * photo lanes: resize to <=2048px long edge + strip ALL metadata (GPS gone)
#   * metadata-strip source: keep benign EXIF, drop GPS only (so tools have
#     something to strip), full res
#   * screenshots: flatten RGBA -> RGB (so the JPEG/lossless lanes don't trip
#     the alpha-validity check on an opaque/!= -used alpha channel); no resize
#     (keep text crisp)
#   * alpha_logo.png: generated with real transparency for the alpha test
#
# Requires macOS `sips` + `exiftool`. Re-run after changing the mapping below.
# This is a one-time staging step; the inputs are not committed, so it won't
# run in CI — it documents how the committed corpus was produced.

set -eu
cd "$(dirname "$0")/.."          # -> imgbench/
IMG=corpus/images
PY=${PY:-python3.14}

# Idempotent: clear prior slot outputs so re-runs don't trip `exiftool -o`
# (which refuses to overwrite) or stale files.
rm -f "$IMG"/photo_*.png "$IMG"/photo_exif.jpg \
      "$IMG"/screenshot_*.png "$IMG"/alpha_logo.png

echo "== photo lanes (resize 2048 + strip all metadata) =="
for pair in \
    "photo_foliage:DSCN2670" \
    "photo_sky:DSCN2084" \
    "photo_lowlight:DSCN2261" \
    "photo_portrait:DSCN2201"; do
  slot="${pair%%:*}"; src="${pair##*:}"
  sips -Z 2048 "$IMG/initial_import/$src.png" --out "$IMG/$slot.png" >/dev/null
  exiftool -all= -overwrite_original "$IMG/$slot.png" >/dev/null 2>&1 || true
  echo "  $slot.png  <- $src.png"
done

echo "== metadata-strip source (keep EXIF, drop GPS, full res) =="
exiftool -gps:all= -o "$IMG/photo_exif.jpg" "$IMG/initial_import/DSCN2270.JPG" >/dev/null 2>&1
echo "  photo_exif.jpg  <- DSCN2270.JPG (GPS removed, EXIF kept)"

echo "== screenshots (flatten RGBA -> RGB, no resize) =="
$PY - "$IMG" <<'PYEOF'
import sys
from pathlib import Path
from bench import imageio
img = Path(sys.argv[1])
mapping = {
    "screenshot_ui.png":   "screenshots/screenshot-figma-desktop-06-19-2026.png",
    "screenshot_text.png": "screenshots/screenshot-craigslist-home-06-19-2026.png",
}
for slot, src in mapping.items():
    w, h, ch, px = imageio.read_png(img / src)
    rgb = imageio.flatten_to_rgb(w, h, ch, px)
    imageio.write_png(img / slot, w, h, rgb, alpha=False)
    print(f"  {slot}  <- {Path(src).name}  ({w}x{h}, {ch}ch -> RGB)")
PYEOF

echo "== alpha_logo.png (generated, real transparency) =="
$PY - "$IMG" <<'PYEOF'
import math, sys
from pathlib import Path
from bench import imageio
W = H = 512
cx = cy = W / 2
clamp = lambda v: max(0, min(255, int(v)))
buf = bytearray()
for y in range(H):
    for x in range(W):
        d = math.hypot(x - cx, y - cy)
        if d < 150:                      # opaque colored disc
            ang = math.atan2(y - cy, x - cx)
            r = clamp(128 + 120 * math.cos(ang))
            g = clamp(128 + 120 * math.sin(ang))
            b, a = 210, 255
        elif d < 200:                    # semi-transparent ring
            r, g, b, a = 40, 170, 220, 110
        else:                            # transparent background
            r = g = b = a = 0
        buf += bytes((r, g, b, a))
imageio.write_png(Path(sys.argv[1]) / "alpha_logo.png", W, H, bytes(buf), alpha=True)
print("  alpha_logo.png  (512x512 RGBA, transparent bg + semi-transparent ring)")
PYEOF

echo "Done. Verify with: bench corpus"
