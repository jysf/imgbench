"""avifenc — single-format AVIF encoder (libavif).

Quality surface changed across versions: modern avifenc takes ``-q 0..100``;
older builds used ``--min``/``--max`` QP. We use ``-q`` and pin ``--speed`` so
AVIF effort matches the other tools (avifenc speed: 0 slowest/best .. 10
fastest). Verify with ``--dry-run`` against your installed version.
"""

from __future__ import annotations

from pathlib import Path

from .base import Adapter, EncodeConfig


class Avifenc(Adapter):
    name, binary, formats = "avifenc", "avifenc", ("avif",)
    version_args = ("--version",)

    def cmd(self, inp: Path, outp: Path, fmt: str, q, cfg: EncodeConfig):
        cmd = [self.binary, "-q", str(q),
               "--speed", str(max(0, 10 - cfg.avif_effort)),
               "--jobs", str(cfg.threads)]
        if cfg.strip_metadata:
            cmd += ["--ignore-exif", "--ignore-xmp"]
        cmd += [str(inp), str(outp)]
        return cmd
