"""SSIMULACRA2 graders — the primary perceptual metric.

``Ssimulacra2C`` wraps the Cloudinary C reference (binary ``ssimulacra2``) and
is the default. ``Ssimulacra2Rs`` wraps the Rust ``ssimulacra2_rs`` and exists
only as the *second* implementation for the agreement sanity-check — never as
the grader for crustyimg numbers (collusion with crustyimg's optimiser).

Pin the exact version/commit in the manifest: v2.0→v2.1 retuned the weights.
"""

from __future__ import annotations

from pathlib import Path

from .base import Grader


class Ssimulacra2C(Grader):
    """Cloudinary C reference: ``ssimulacra2 <orig> <dist>`` → bare float."""
    name, binary = "ssimulacra2", "ssimulacra2"
    higher_is_better = True
    identical_score = 100.0

    def score(self, orig: Path, dist: Path):
        out = self._run([self.binary, str(orig), str(dist)])
        return self._last_float(out) if out is not None else None


class Ssimulacra2Rs(Grader):
    """Rust ``ssimulacra2_rs image <orig> <dist>``. Used for cross-checks only."""
    name, binary = "ssimulacra2_rs", "ssimulacra2_rs"
    higher_is_better = True
    identical_score = 100.0

    def score(self, orig: Path, dist: Path):
        out = self._run([self.binary, "image", str(orig), str(dist)])
        if out is None:  # some builds omit the `image` subcommand
            out = self._run([self.binary, str(orig), str(dist)])
        return self._last_float(out) if out is not None else None
