"""DSSIM grader — a third cross-check metric.

DSSIM reports structural DIS-similarity (lower = better; 0 = identical), via
Kornel Lesiński's ``dssim`` Rust binary: ``dssim <orig> <dist>`` prints
``<score> <dist-path>``.
"""

from __future__ import annotations

from pathlib import Path

from .base import Grader


class Dssim(Grader):
    name, binary = "dssim", "dssim"
    higher_is_better = False
    identical_score = 0.0

    def score(self, orig: Path, dist: Path):
        out = self._run([self.binary, str(orig), str(dist)])
        if out is None:
            return None
        # First token of the first line is the score.
        for line in out.splitlines():
            parts = line.split()
            if parts:
                try:
                    return float(parts[0])
                except ValueError:
                    continue
        return None
