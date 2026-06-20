"""Butteraugli grader — cross-check for visually-lossless claims.

Butteraugli reports a DISTANCE (lower = better; 0 = identical), so
``higher_is_better`` is False. Available via libjxl's ``butteraugli_main`` or
the ``butteraugli`` binary; output formats vary, so we grab the first float
(the headline 3-norm / pnorm distance some builds print) and fall back to the
last float otherwise.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .base import Grader


class Butteraugli(Grader):
    name = "butteraugli"
    binary = "butteraugli_main"
    higher_is_better = False
    identical_score = 0.0

    def available(self) -> bool:
        return self.resolved_binary() is not None

    def resolved_binary(self):
        return shutil.which("butteraugli_main") or shutil.which("butteraugli")

    def score(self, orig: Path, dist: Path):
        b = self.resolved_binary()
        if not b:
            return None
        out = self._run([b, str(orig), str(dist)])
        if out is None:
            return None
        # Prefer the first float on the first non-empty line (the headline
        # distance); fall back to the last float anywhere.
        for line in out.splitlines():
            for tok in line.split():
                try:
                    return float(tok)
                except ValueError:
                    continue
        return self._last_float(out)
