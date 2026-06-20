"""Provenance capture — the run manifest.

Records everything needed to trust and reproduce a run: machine identity, OS,
CPU governor / turbo state, every tool + grader version, the corpus hashes, and
the crustyimg build-feature gate. ``compare`` reads this back to refuse diffing
runs whose tool versions drifted.

Stdlib only; every probe is best-effort and degrades to ``None`` off-platform.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from . import MANIFEST_SCHEMA, __version__


def _run(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return (out.stdout or "").strip() or None
    except (subprocess.SubprocessError, OSError):
        return None


# ---------------------------------------------------------------------------
# Machine
# ---------------------------------------------------------------------------
def cpu_model() -> str | None:
    if sys.platform == "darwin":
        return _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or None


def core_counts() -> dict:
    logical = os.cpu_count()
    physical = None
    if sys.platform == "darwin":
        v = _run(["sysctl", "-n", "hw.physicalcpu"])
        physical = int(v) if v and v.isdigit() else None
    elif sys.platform.startswith("linux"):
        try:
            ids = set()
            cur = {}
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if ":" in line:
                    k, val = (x.strip() for x in line.split(":", 1))
                    cur[k] = val
                elif not line.strip():
                    key = (cur.get("physical id"), cur.get("core id"))
                    if key != (None, None):
                        ids.add(key)
                    cur = {}
            physical = len(ids) or None
        except OSError:
            pass
    return {"logical": logical, "physical": physical}


def ram_bytes() -> int | None:
    if sys.platform == "darwin":
        v = _run(["sysctl", "-n", "hw.memsize"])
        return int(v) if v and v.isdigit() else None
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) * 1024  # kB -> bytes
        except OSError:
            pass
    return None


def cpu_scaling() -> dict:
    """Governor + turbo/boost state, where detectable (Linux)."""
    info: dict = {"governor": None, "turbo": None}
    gov = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    if gov.exists():
        try:
            info["governor"] = gov.read_text().strip()
        except OSError:
            pass
    no_turbo = Path("/sys/devices/system/cpu/intel_pstate/no_turbo")
    if no_turbo.exists():
        try:
            info["turbo"] = "off" if no_turbo.read_text().strip() == "1" else "on"
        except OSError:
            pass
    boost = Path("/sys/devices/system/cpu/cpufreq/boost")
    if info["turbo"] is None and boost.exists():
        try:
            info["turbo"] = "on" if boost.read_text().strip() == "1" else "off"
        except OSError:
            pass
    return info


def machine() -> dict:
    uname = platform.uname()
    return {
        "cpu_model": cpu_model(),
        "cores": core_counts(),
        "ram_bytes": ram_bytes(),
        "os": f"{uname.system} {uname.release}",
        "kernel": uname.version,
        "machine": uname.machine,
        "python": platform.python_version(),
        "scaling": cpu_scaling(),
    }


# ---------------------------------------------------------------------------
# Corpus hashing
# ---------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def corpus_hashes(images: list[Path]) -> dict:
    per_image = {}
    agg = hashlib.sha256()
    for img in sorted(images, key=lambda p: p.name):
        digest = sha256_file(img)
        per_image[img.name] = {"sha256": digest, "bytes": img.stat().st_size}
        agg.update(img.name.encode())
        agg.update(bytes.fromhex(digest))
    return {"per_image": per_image, "aggregate_sha256": agg.hexdigest(),
            "count": len(per_image)}


# ---------------------------------------------------------------------------
# Tool + grader versions
# ---------------------------------------------------------------------------
def tool_versions(adapters) -> dict:
    out = {}
    for a in adapters:
        entry = {
            "available": a.available(),
            "binary": a.resolved_binary(),
            "version": a.version() if a.available() else None,
        }
        if a.name == "crustyimg" and a.available():
            entry["build_features"] = a.build_features()
        out[a.name] = entry
    return out


def grader_versions(graders) -> dict:
    return {
        g.name: {
            "available": g.available(),
            "binary": g.resolved_binary(),
            "version": g.version() if g.available() else None,
        }
        for g in graders
    }


# ---------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------
def build_manifest(*, bench_sha: str, images: list[Path], adapters, graders,
                   primary_grader, config: dict, agreement: dict | None = None,
                   extra: dict | None = None) -> dict:
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "bench_version": __version__,
        "bench_git_sha": bench_sha,
        "argv": sys.argv,
        "machine": machine(),
        "config": config,
        "corpus": corpus_hashes(images),
        "tools": tool_versions(adapters),
        "graders": grader_versions(graders),
        "primary_grader": primary_grader.name if primary_grader else None,
        "grader_agreement": agreement,
    }
    if extra:
        manifest.update(extra)
    return manifest


def bench_git_sha(root: Path | None = None) -> str:
    """Short git SHA of the harness, or 'nogit' when not in a repo."""
    cwd = str(root) if root else None
    sha = _run(["git", "-C", cwd or ".", "rev-parse", "--short", "HEAD"]) \
        if shutil.which("git") else None
    return sha or "nogit"
