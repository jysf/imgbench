"""crustyimg — the subject under test (STUBBED until SPEC-016 lands).

To activate, point ``binary`` at the built binary — one line:

    CrustyImg.binary = "target/release/crustyimg"   # or set CRUSTYIMG_BIN

It MUST be built ``--features webp-lossy,avif``: the default build encodes WebP
losslessly only, so benchmarking it against lossy WebP from rimage/sharp/cwebp
would be apples-to-oranges. ``feature_check`` fails loudly when a lossless-only
binary is asked to do a lossy comparison.

Two operating modes are wired:
  * SWEEP (``shrink --quality``)   — sit on the same curve as the others.
  * NATIVE (``optimize --target-ssimulacra2``) — grade the single output; this
    is crustyimg's product argument (it lands ON the target by construction).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .base import Adapter, EncodeConfig

REQUIRED_FEATURES = ("webp-lossy", "avif")


class CrustyImg(Adapter):
    name, formats = "crustyimg", ("webp", "avif")
    # Resolve from env so activation needs no code edit; default stays stubbed.
    binary = os.environ.get("CRUSTYIMG_BIN")

    def resolved_binary(self):
        if self.binary and (shutil.which(self.binary) or Path(self.binary).exists()):
            return self.binary if Path(self.binary).is_absolute() or shutil.which(self.binary) \
                else str(Path(self.binary).resolve())
        return None

    def available(self) -> bool:
        return self.resolved_binary() is not None

    def build_features(self) -> list[str]:
        """Parse the feature list crustyimg reports in ``--version``. Returns
        [] when unknown. crustyimg is expected to print a line listing the
        compiled features (adjust the parse to the real output once it ships)."""
        v = self.version() or ""
        feats = []
        for token in v.replace(",", " ").split():
            if token in REQUIRED_FEATURES or token.startswith("feature"):
                feats.append(token)
        return [f for f in REQUIRED_FEATURES if f in v] or feats

    def feature_check(self, lossy: bool) -> tuple[bool, str]:
        """Return (ok, reason). When a lossy comparison is requested, a
        lossless-only crustyimg MUST be rejected — the caller fails the run."""
        if not lossy:
            return True, "lossless comparison: feature set not gating"
        feats = self.build_features()
        missing = [f for f in REQUIRED_FEATURES if f not in feats]
        if missing:
            return False, (
                f"crustyimg is missing required build features {missing}; "
                f"rebuild `cargo build --release --features "
                f"{','.join(REQUIRED_FEATURES)}`")
        return True, "features present"

    def cmd(self, inp: Path, outp: Path, fmt: str, q, cfg: EncodeConfig):
        b = self.resolved_binary() or "crustyimg"
        cmd = [b, "shrink", "--format", fmt, "--quality", str(q),
               "--threads", str(cfg.threads)]
        if fmt == "avif":
            cmd += ["--effort", str(cfg.avif_effort)]
        if cfg.strip_metadata:
            cmd += ["--strip"]
        cmd += [str(inp), "-o", str(outp)]
        return cmd

    def native_cmd(self, inp: Path, outp: Path, fmt: str, target: float,
                   cfg: EncodeConfig):
        """Outcome-driven mode: hit a SSIMULACRA2 target directly (SPEC-016)."""
        b = self.resolved_binary() or "crustyimg"
        cmd = [b, "optimize", "--format", fmt,
               "--target-ssimulacra2", str(target), "--threads", str(cfg.threads)]
        if cfg.strip_metadata:
            cmd += ["--strip"]
        cmd += [str(inp), "-o", str(outp)]
        return cmd

    def responsive_cmd(self, inp: Path, outdir: Path, widths, fmts,
                       cfg: EncodeConfig):
        """STUB (roadmap): responsive-set generation — N widths × M formats plus
        the <picture>/srcset snippet. Wired so the operation is one command away
        once crustyimg ships `responsive`; not yet exercised by the runner."""
        b = self.resolved_binary() or "crustyimg"
        return [b, "responsive",
                "--widths", ",".join(str(w) for w in widths),
                "--formats", ",".join(fmts),
                "--threads", str(cfg.threads),
                str(inp), "-o", str(outdir)]
