"""Grader interface — a perceptual metric the harness can gate on.

The primary grader is SSIMULACRA2 from the Cloudinary C reference (NOT
``ssimulacra2_rs``): crustyimg optimises against the Rust ``ssimulacra2`` crate,
so grading on the same implementation would be teaching-to-the-test. Butteraugli
and DSSIM/PSNR are interchangeable cross-checks.

A grader maps (original, distorted) → a single float. ``higher_is_better`` and
``identical_score`` let the harness reason about direction and the ~lossless
endpoint without hard-coding SSIMULACRA2's 0..100 scale.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


class Grader:
    name = "abstract"
    binary: str | None = None
    higher_is_better = True
    identical_score: float = 100.0  # score for a perfect (==original) output

    def available(self) -> bool:
        return self.binary is not None and shutil.which(self.binary) is not None

    def resolved_binary(self) -> str | None:
        return shutil.which(self.binary) if self.binary else None

    def version(self) -> str | None:
        path = self.resolved_binary()
        if not path:
            return None
        for args in (("--version",), ("-version",), ("version",)):
            try:
                out = subprocess.run([path, *args], capture_output=True,
                                     text=True, timeout=15)
            except (subprocess.SubprocessError, OSError):
                continue
            text = ((out.stdout or "") + (out.stderr or "")).strip()
            if text:
                return text.splitlines()[0].strip()
        return path

    def score(self, orig: Path, dist: Path) -> float | None:
        """Return the metric value, or None on failure."""
        raise NotImplementedError

    @staticmethod
    def _last_float(text: str) -> float | None:
        for tok in reversed(text.replace("\n", " ").split()):
            try:
                return float(tok)
            except ValueError:
                continue
        return None

    @staticmethod
    def _run(cmd: list[str]) -> str | None:
        try:
            return subprocess.run(cmd, capture_output=True, text=True,
                                  check=True, timeout=120).stdout
        except (subprocess.SubprocessError, OSError):
            return None
