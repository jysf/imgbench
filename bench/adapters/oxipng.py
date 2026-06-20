"""oxipng + pngquant — the PNG lane.

LOSSLESS sub-lane: oxipng (one operating point, score ~100; compare bytes+speed)
vs sharp-png (in sharp.py). LOSSY/palette sub-lane: pngquant sits on a real
quality sweep, so equal-SSIMULACRA2 interpolation applies like the photo lane.
"""

from __future__ import annotations

from pathlib import Path

from .base import Adapter, EncodeConfig


class Oxipng(Adapter):
    name, binary, formats, lossless = "oxipng", "oxipng", ("png",), True

    def cmd(self, inp: Path, outp: Path, fmt: str, q, cfg: EncodeConfig):
        strip = "safe" if cfg.strip_metadata else "none"
        cmd = [self.binary, "-o", "max", "--strip", strip,
               "--threads", str(cfg.threads), "--out", str(outp), str(inp)]
        return cmd


class Pngquant(Adapter):
    """Lossy palette PNG — pngquant maps quality to a 0-Q acceptance window."""
    name, binary, formats = "pngquant", "pngquant", ("png",)
    version_args = ("--version",)

    def quality_range(self, fmt: str):
        return [50, 60, 70, 80, 90, 100]

    def cmd(self, inp: Path, outp: Path, fmt: str, q, cfg: EncodeConfig):
        cmd = [self.binary, f"--quality=0-{q}", "--force", "--output", str(outp)]
        if cfg.strip_metadata:
            cmd += ["--strip"]
        cmd += [str(inp)]
        return cmd
