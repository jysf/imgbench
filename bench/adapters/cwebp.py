"""cwebp — single-format WebP encoder (libwebp). Writes directly to ``-o``."""

from __future__ import annotations

from pathlib import Path

from .base import Adapter, EncodeConfig


class Cwebp(Adapter):
    name, binary, formats = "cwebp", "cwebp", ("webp",)
    version_args = ("-version",)

    def cmd(self, inp: Path, outp: Path, fmt: str, q, cfg: EncodeConfig):
        cmd = [self.binary, "-quiet", "-q", str(q),
               "-mt" if cfg.threads != 1 else "-mt0"]
        # cwebp has no metadata by default unless -metadata is passed; ensure
        # stripping explicitly so byte deltas aren't EXIF/ICC.
        if cfg.strip_metadata:
            cmd += ["-metadata", "none"]
        cmd += [str(inp), "-o", str(outp)]
        # -mt0 isn't a real flag; drop the placeholder when single-threaded.
        return [c for c in cmd if c != "-mt0"]
