"""Output-validity checks (methodology §7).

After each encode we decode the output header and assert dimensions are
preserved and alpha is preserved where the source had it. A tool that silently
drops alpha or resizes must not score a bytes "win" — an invalid output is
excluded from the curve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import imageio


@dataclass
class Validity:
    ok: bool = True
    dims_preserved: bool = True
    alpha_preserved: bool = True
    notes: list[str] = field(default_factory=list)
    src_size: tuple[int, int] | None = None
    out_size: tuple[int, int] | None = None

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "dims_preserved": self.dims_preserved,
            "alpha_preserved": self.alpha_preserved,
            "src_size": list(self.src_size) if self.src_size else None,
            "out_size": list(self.out_size) if self.out_size else None,
            "notes": self.notes,
        }


def check_output(src: Path, out: Path) -> Validity:
    """Compare encoded ``out`` against original ``src``. Best-effort: if a
    format can't be probed we record a note rather than failing the encode."""
    v = Validity()
    try:
        si = imageio.probe(src)
    except (ValueError, OSError) as e:
        v.notes.append(f"could not probe source ({e}); validity unverified")
        return v
    try:
        oi = imageio.probe(out)
    except (ValueError, OSError) as e:
        v.notes.append(f"could not probe output ({e}); validity unverified")
        return v

    v.src_size = (si.width, si.height)
    v.out_size = (oi.width, oi.height)

    if (si.width, si.height) != (oi.width, oi.height):
        v.dims_preserved = False
        v.ok = False
        v.notes.append(
            f"dimensions changed {si.width}x{si.height} -> {oi.width}x{oi.height}")

    if si.has_alpha and not oi.has_alpha:
        v.alpha_preserved = False
        v.ok = False
        v.notes.append("source had alpha; output dropped it")

    return v
