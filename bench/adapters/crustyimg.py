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
        # Prefer an explicit CRUSTYIMG_BIN (path or name); otherwise fall back to
        # a `crustyimg` on PATH (e.g. built into the tools image), so no env var
        # is needed once it's installed.
        cand = self.binary or os.environ.get("CRUSTYIMG_BIN")
        if cand:
            if shutil.which(cand):
                return shutil.which(cand)
            if Path(cand).exists():
                return str(Path(cand).resolve())
        return shutil.which("crustyimg")

    def available(self) -> bool:
        return self.resolved_binary() is not None

    def build_features(self) -> list[str]:
        """crustyimg's --version doesn't list compiled features, so probe ACTUAL
        capability: encode a small synthetic image and check that (a) WebP
        responds to --quality (a lossless-only build ignores it → same bytes) and
        (b) AVIF output is produced. This is the real signal the gate cares about."""
        import subprocess
        import tempfile
        from .. import imageio

        b = self.resolved_binary()
        if not b:
            return []
        feats: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            src = d / "probe.png"
            px = bytearray()
            for y in range(96):
                for x in range(96):  # noisy gradient so quality actually matters
                    px += bytes(((x * 7 + y * 13) % 256, (x * y) % 256,
                                 (x * 3 + y * 5) % 256))
            imageio.write_png(src, 96, 96, bytes(px), alpha=False)

            def enc(fmt: str, q: int):
                out = d / f"p_{fmt}_{q}.{fmt}"
                try:
                    subprocess.run([b, "convert", "--format", fmt, "--quality",
                                    str(q), str(src), "-o", str(out)],
                                   capture_output=True, timeout=30)
                except (subprocess.SubprocessError, OSError):
                    return None
                return out.stat().st_size if out.exists() else None

            lo, hi = enc("webp", 20), enc("webp", 95)
            if lo and hi and hi > lo * 1.2:      # quality moves bytes → lossy webp
                feats.append("webp-lossy")
            if enc("avif", 60):                  # avif output produced → avif on
                feats.append("avif")
        return feats

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
        # `convert` re-encodes at the SAME dimensions (the fixed-quality sweep
        # path). `shrink` is optimize-for-web and DOWNSIZES, which would change
        # dimensions and break the equal-pixels comparison — so don't use it.
        # Caveats at 0.1.x: AVIF effort isn't CLI-controllable (ravif default),
        # and `convert` has no metadata-strip flag (mostly moot — the corpus
        # sources carry no metadata except the synthetic-EXIF JPEG).
        b = self.resolved_binary() or "crustyimg"
        return [b, "convert", "--format", fmt, "--quality", str(q),
                "--jobs", str(cfg.threads), str(inp), "-o", str(outp)]

    def native_cmd(self, inp: Path, outp: Path, fmt: str, target: float,
                   cfg: EncodeConfig):
        """Outcome-driven mode: ask for a SSIMULACRA2 target directly via
        ``shrink --ssim`` (SPEC-016). Note: at 0.1.x the auto-quality search is
        JPEG-centric, so this may be a no-op for webp/avif until it lands."""
        b = self.resolved_binary() or "crustyimg"
        cmd = [b, "shrink", "--format", fmt, "--ssim", str(target),
               "--jobs", str(cfg.threads), str(inp), "-o", str(outp)]
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
