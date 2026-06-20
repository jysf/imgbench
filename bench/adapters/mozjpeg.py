"""cjpeg (MozJPEG) — the single-format JPEG encoder for the JPEG lane.

JPEG is lossy, so it sits on a real quality sweep + equal-SSIMULACRA2
interpolation, exactly like the WebP/AVIF lanes. MozJPEG's ``cjpeg`` is the
canonical high-quality JPEG encoder; it's the JPEG counterpart to cwebp/avifenc.

NOTE: ``cjpeg`` input-format support depends on the build (PPM/BMP/TGA always;
PNG/JPEG when compiled with libpng/libjpeg). Verify with ``--dry-run`` against
your install. Metadata: cjpeg does not copy source markers by default, so output
is already stripped (no EXIF/ICC carried over).
"""

from __future__ import annotations

from pathlib import Path

from .base import Adapter, EncodeConfig


class Cjpeg(Adapter):
    name, binary, formats = "cjpeg", "cjpeg", ("jpeg",)
    version_args = ("-version",)

    def cmd(self, inp: Path, outp: Path, fmt: str, q, cfg: EncodeConfig):
        # cjpeg is single-threaded; the threads knob doesn't apply. Default
        # behaviour already drops source metadata (no -copy all).
        return [self.binary, "-quality", str(q), "-outfile", str(outp), str(inp)]
