"""rimage — the fairest 1:1 target (Rust, single binary, WebP/AVIF/...).

Verify flags against your installed rimage: the CLI surface changed across
0.9/0.10/0.11. The form below targets recent rimage where the codec is a
subcommand. Use ``bench run --dry-run`` to print commands before a real run.
"""

from __future__ import annotations

from pathlib import Path

from .base import Adapter, EncodeConfig


class Rimage(Adapter):
    name, binary, formats = "rimage", "rimage", ("webp", "avif")
    # rimage writes into a directory with -d; we point it at the point's
    # scratch dir and the runner normalises the produced file to ``outp``.
    writes_to_dir = True

    def cmd(self, inp: Path, outp: Path, fmt: str, q, cfg: EncodeConfig):
        cmd = [self.binary, fmt, "--quality", str(q)]
        if fmt == "avif":
            # rimage exposes AVIF speed (0..10, lower=slower/better). Map the
            # shared "effort" so all tools sit at the same operating point.
            cmd += ["--speed", str(max(0, 10 - cfg.avif_effort))]
        cmd += ["--threads", str(cfg.threads)]
        # rimage strips metadata by default; there is no carry flag to add.
        cmd += [str(inp), "-d", str(outp.parent)]
        return cmd
