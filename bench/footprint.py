"""Footprint capture (methodology §8) — reported, never raced.

Per tool: on-disk binary size, dynamic-dependency count (``ldd`` on Linux,
``otool -L`` on macOS), whether a language runtime is required, and — only when
asked — cold-install time on a clean container via the pinned Dockerfile.

This quantifies the genuinely-different install stories (crustyimg's zero-system-
dep single binary vs sharp's Node + prebuilt native binary vs rimage's cargo
build) without folding them into encode time.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Tools that need a language runtime present to run at all.
RUNTIME_REQUIRED = {
    "sharp": "node",
    "sharp-png": "node",
}


def _run(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (out.stdout or "") + (out.stderr or "")
    except (subprocess.SubprocessError, OSError):
        return None


def dependency_count(binary: str) -> int | None:
    """Count dynamically-linked libraries for ``binary``."""
    if sys.platform.startswith("linux") and shutil.which("ldd"):
        out = _run(["ldd", binary])
        if out is None:
            return None
        return sum(1 for line in out.splitlines() if "=>" in line or ".so" in line)
    if sys.platform == "darwin" and shutil.which("otool"):
        out = _run(["otool", "-L", binary])
        if out is None:
            return None
        # First line is the binary itself; the rest are linked dylibs.
        return max(0, len([l for l in out.splitlines() if l.strip()]) - 1)
    return None


def _runtime_present(runtime: str) -> bool:
    return shutil.which(runtime) is not None


def capture(adapters) -> dict:
    """Footprint snapshot for every available adapter."""
    out: dict = {"platform": sys.platform, "tools": {}}
    seen_binaries = {}
    for a in adapters:
        b = a.resolved_binary()
        entry: dict = {"available": a.available()}
        if b:
            try:
                # Resolve symlinks so size reflects the real binary.
                real = os.path.realpath(b)
                entry["binary"] = real
                entry["binary_size_bytes"] = Path(real).stat().st_size
            except OSError:
                entry["binary"] = b
            # Cache ldd lookups per real binary (sharp/sharp-png share one).
            if entry.get("binary") in seen_binaries:
                entry["dependency_count"] = seen_binaries[entry["binary"]]
            else:
                dc = dependency_count(entry.get("binary", b))
                entry["dependency_count"] = dc
                seen_binaries[entry.get("binary", b)] = dc
        runtime = RUNTIME_REQUIRED.get(a.name)
        entry["runtime_required"] = runtime
        if runtime:
            entry["runtime_present"] = _runtime_present(runtime)
        out["tools"][a.name] = entry
    return out


def cold_install_seconds(dockerfile: Path, image_tag: str = "imgbench-tools") -> dict:
    """Measure cold-install time by building the pinned tools image from scratch.

    Only meaningful with Docker available; returns a structured result either
    way so the manifest always has the field. This is intentionally NOT run by
    default (it is slow and needs Docker) — invoke via ``bench footprint
    --cold-install``.
    """
    import time

    if not shutil.which("docker"):
        return {"measured": False, "reason": "docker not available"}
    if not dockerfile.exists():
        return {"measured": False, "reason": f"missing {dockerfile}"}
    t0 = time.perf_counter()
    proc = subprocess.run(
        ["docker", "build", "--no-cache", "-f", str(dockerfile),
         "-t", image_tag, str(dockerfile.parent)],
        capture_output=True, text=True)
    elapsed = time.perf_counter() - t0
    return {
        "measured": proc.returncode == 0,
        "seconds": round(elapsed, 1),
        "returncode": proc.returncode,
        "reason": None if proc.returncode == 0 else proc.stderr[-400:],
    }
