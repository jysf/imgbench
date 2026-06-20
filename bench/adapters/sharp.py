"""sharp (sharp-cli) — the ecosystem baseline (Node + libvips).

Two adapters share the binary: ``sharp`` for lossy WebP/AVIF and ``sharp-png``
for the lossless PNG lane (the direct "oxipng vs sharp" comparison). sharp-cli's
``-o`` is a DIRECTORY, so the runner normalises the produced file to ``outp``.

NOTE on fairness: sharp runs on Node, so its single-invocation wall-clock
includes Node startup. The methodology requires reporting cold per-invocation
time separately from warm batch throughput — see measure/cold-start handling.
"""

from __future__ import annotations

from pathlib import Path

from .base import Adapter, EncodeConfig


class SharpCli(Adapter):
    name, binary, formats = "sharp", "sharp", ("webp", "avif", "jpeg")
    writes_to_dir = True

    def cmd(self, inp: Path, outp: Path, fmt: str, q, cfg: EncodeConfig):
        cmd = [self.binary, "-i", str(inp), "-o", str(outp.parent), "-f", fmt,
               "-q", str(q)]
        if fmt == "avif":
            cmd += ["--effort", str(cfg.avif_effort)]
        if cfg.strip_metadata:
            # sharp-cli keeps metadata only with --withMetadata; default strips.
            pass
        return cmd


class SharpPng(Adapter):
    """sharp's LOSSLESS png path — the direct oxipng-vs-sharp comparison."""
    name, binary, formats, lossless = "sharp-png", "sharp", ("png",), True
    writes_to_dir = True

    def cmd(self, inp: Path, outp: Path, fmt: str, q, cfg: EncodeConfig):
        return [self.binary, "-i", str(inp), "-o", str(outp.parent),
                "-f", "png", "--compressionLevel", "9"]
