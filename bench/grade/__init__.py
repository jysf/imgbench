"""Grader registry + selection + cross-implementation agreement check.

Default grader: the Cloudinary C reference SSIMULACRA2 (``ssimulacra2``), per the
grader-independence control. The agreement check confirms two SSIMULACRA2
implementations track each other within tolerance on a few images, and records
the result in the manifest so a reader can trust the gate.
"""

from __future__ import annotations

from pathlib import Path

from .base import Grader
from .butteraugli import Butteraugli
from .cache import CachingGrader, GradeCache
from .dssim import Dssim
from .ssimulacra2 import Ssimulacra2C, Ssimulacra2Rs

# Order matters: the first available SSIMULACRA2 grader is the primary, and we
# deliberately prefer the C reference over the Rust crate.
PRIMARY_PREFERENCE = ("ssimulacra2", "ssimulacra2_rs")

GRADERS: dict[str, Grader] = {
    g.name: g for g in (Ssimulacra2C(), Ssimulacra2Rs(), Butteraugli(), Dssim())
}


def by_name(name: str) -> Grader | None:
    return GRADERS.get(name)


def all_graders() -> list[Grader]:
    return list(GRADERS.values())


def default_grader() -> Grader | None:
    """The primary SSIMULACRA2 grader, preferring the independent C reference."""
    for name in PRIMARY_PREFERENCE:
        g = GRADERS.get(name)
        if g and g.available():
            return g
    return None


def available_graders() -> list[Grader]:
    return [g for g in GRADERS.values() if g.available()]


def agreement_check(images: list[tuple[Path, Path]], *, tol: float = 5.0) -> dict:
    """Run both SSIMULACRA2 implementations on a handful of (orig, dist) pairs
    and report whether they agree within ``tol`` points.

    Returns a manifest-ready dict. ``agree`` is None when the second
    implementation isn't installed (can't cross-check, not a failure).
    """
    c, rs = GRADERS["ssimulacra2"], GRADERS["ssimulacra2_rs"]
    result: dict = {
        "implementations": ["ssimulacra2 (C ref)", "ssimulacra2_rs (Rust)"],
        "tolerance": tol, "pairs": [], "agree": None,
    }
    if not (c.available() and rs.available()):
        result["note"] = ("second SSIMULACRA2 implementation not installed; "
                          "cross-check skipped")
        return result

    worst = 0.0
    for orig, dist in images:
        sc, sr = c.score(orig, dist), rs.score(orig, dist)
        if sc is None or sr is None:
            continue
        delta = abs(sc - sr)
        worst = max(worst, delta)
        result["pairs"].append({
            "image": Path(dist).name,
            "ssimulacra2_c": round(sc, 3),
            "ssimulacra2_rs": round(sr, 3),
            "delta": round(delta, 3),
        })
    if result["pairs"]:
        result["max_delta"] = round(worst, 3)
        result["agree"] = worst <= tol
    return result


__all__ = [
    "Grader", "GRADERS", "by_name", "all_graders", "default_grader",
    "available_graders", "agreement_check",
    "Ssimulacra2C", "Ssimulacra2Rs", "Butteraugli", "Dssim",
    "GradeCache", "CachingGrader",
]
