"""Adapter interface — one encoder per subclass.

Preserves the seed harness's pattern: each adapter yields a quality range and a
``cmd()`` that builds the encode command for (input, output, format, quality).
Adds the §"Fairness controls" the methodology requires:

* ``EncodeConfig`` carries the knobs that MUST be equalised across tools —
  thread count, AVIF effort/speed, and metadata stripping — so a byte delta is
  never just EXIF or a different effort level.
* ``version()`` captures the tool's version string for the run manifest.

Adapters describe *how* to drive a tool; they never run it (that's measure.py)
and never decide the sweep (that's sweep.py).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EncodeConfig:
    """Fairness knobs applied uniformly across every adapter in a run."""
    threads: int = 1          # pin to 1 for clean per-image comparison
    avif_effort: int = 6      # equal AVIF effort/speed across tools (0..10-ish)
    strip_metadata: bool = True
    # When an adapter cannot honour a knob it records the gap here so the
    # report can flag "this number isn't strictly comparable".
    caveats: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.caveats is None:
            self.caveats = []


class Adapter:
    name = "abstract"
    binary: str | None = None
    formats: tuple[str, ...] = ("webp", "avif")
    lossless = False  # lossless tools run ONE operating point (no quality sweep)
    writes_to_dir = False  # True if the tool writes into a dir, not a file path

    # Subclasses may set a custom flag to query the version; default tries the
    # common forms.
    version_args: tuple[str, ...] = ("--version",)

    def available(self) -> bool:
        return self.binary is not None and shutil.which(self.binary) is not None

    def resolved_binary(self) -> str | None:
        return shutil.which(self.binary) if self.binary else None

    def version(self) -> str | None:
        """Return a one-line version string, or None if the tool is absent."""
        path = self.resolved_binary()
        if not path:
            return None
        for args in (self.version_args, ("--version",), ("-version",), ("-V",)):
            try:
                out = subprocess.run([path, *args], capture_output=True,
                                     text=True, timeout=15)
            except (subprocess.SubprocessError, OSError):
                continue
            text = (out.stdout or "") + (out.stderr or "")
            text = text.strip()
            if text:
                return text.splitlines()[0].strip()
        return path  # at least record the resolved path

    def quality_range(self, fmt: str) -> list:
        if self.lossless:
            return [None]
        return list(range(40, 96, 5))  # 40..95 step 5; refined near target later

    def supports_quality(self, fmt: str) -> bool:
        """True if this adapter can encode at an arbitrary quality (so the
        bisection refine can request intermediate points)."""
        return not self.lossless

    def cmd(self, inp: Path, outp: Path, fmt: str, q, cfg: EncodeConfig) -> list[str]:
        raise NotImplementedError

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _first_version_number(text: str) -> str | None:
        m = re.search(r"\d+\.\d+(?:\.\d+)?", text or "")
        return m.group(0) if m else None
