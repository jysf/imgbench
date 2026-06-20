"""Decode an encoded output to a grader-readable image.

The C-reference SSIMULACRA2 / Butteraugli (libjxl) read PNG/JPEG/PPM but NOT
WebP or AVIF. Grading is supposed to compare *decoded pixels* anyway, so before
grading we decode WebP/AVIF outputs to a lossless PNG (exact decoded pixels — no
quality change) and pass PNG/JPEG straight through.

Uses fast format-specific decoders already present in the tools image
(``dwebp``/``avifdec``), falling back to ``sharp`` (libvips, universal) if a
specific decoder is missing.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# Formats the C grader reads natively — no decode needed.
_NATIVE = {".png", ".jpg", ".jpeg", ".ppm", ".pgm"}


def _run(cmd: list[str]) -> bool:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=120).returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def decode_for_grading(src: Path, scratch_dir: Path | None = None) -> Path | None:
    """Return a path to a PNG/JPEG the grader can read. Decodes WebP/AVIF to a
    sibling ``<name>.decoded.png``; returns ``src`` unchanged for native formats;
    returns None if no decoder succeeds."""
    src = Path(src)
    if src.suffix.lower() in _NATIVE:
        return src
    out = (scratch_dir or src.parent) / f"{src.stem}.decoded.png"

    if src.suffix.lower() == ".webp" and shutil.which("dwebp"):
        if _run(["dwebp", "-quiet", str(src), "-o", str(out)]) and out.exists():
            return out
    if src.suffix.lower() == ".avif" and shutil.which("avifdec"):
        # avifdec <in> <out.png>
        if _run(["avifdec", str(src), str(out)]) and out.exists():
            return out

    # Universal fallback: sharp/libvips writes <stem>.png into the output dir.
    if shutil.which("sharp"):
        d = scratch_dir or src.parent
        if _run(["sharp", "-i", str(src), "-o", str(d), "-f", "png"]):
            cand = d / f"{src.stem}.png"
            if cand.exists() and cand != src:
                return cand
    return None
