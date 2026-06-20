"""Process measurement: wall-clock (best-of-N) + peak RSS, with variance
discipline (warmup discard, median + MAD), optional CPU-affinity pinning, and
a machine-loaded / thermal-throttle warning.

Unix/macOS only — uses ``os.wait4`` for per-child ``ru_maxrss``. Windows is
unsupported (documented in the README).
"""

from __future__ import annotations

import os
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RunStats:
    """Timing distribution for one encode command, across N timed repeats."""
    samples_ms: list[float] = field(default_factory=list)  # post-warmup, sorted
    warmup_ms: float | None = None
    peak_rss_kib: int = 0
    returncode: int = 0
    stderr: str = ""

    @property
    def min_ms(self) -> float | None:
        return min(self.samples_ms) if self.samples_ms else None

    @property
    def median_ms(self) -> float | None:
        return statistics.median(self.samples_ms) if self.samples_ms else None

    @property
    def mad_ms(self) -> float | None:
        """Median absolute deviation — a robust spread estimate (not stdev)."""
        if len(self.samples_ms) < 2:
            return 0.0 if self.samples_ms else None
        med = statistics.median(self.samples_ms)
        return statistics.median(abs(s - med) for s in self.samples_ms)

    def as_dict(self) -> dict:
        return {
            "min_ms": _round(self.min_ms),
            "median_ms": _round(self.median_ms),
            "mad_ms": _round(self.mad_ms),
            "warmup_ms": _round(self.warmup_ms),
            "n": len(self.samples_ms),
            "peak_rss_kib": self.peak_rss_kib,
        }


def _round(v):
    return round(v, 3) if isinstance(v, (int, float)) else v


def _maybe_pin(cmd: list[str], pin_cpu: int | None) -> list[str]:
    """Prefix with taskset (Linux) to pin to one core if requested+available."""
    if pin_cpu is None:
        return cmd
    taskset = shutil.which("taskset")
    if taskset and sys.platform.startswith("linux"):
        return [taskset, "-c", str(pin_cpu), *cmd]
    return cmd  # silently fall through where taskset is absent (e.g. macOS)


def run_once(cmd: list[str], *, pin_cpu: int | None = None) -> tuple[float, int, int, str]:
    """Run cmd once. Return (wall_s, peak_rss_kib, returncode, stderr)."""
    real = _maybe_pin(cmd, pin_cpu)
    t0 = time.perf_counter()
    proc = subprocess.Popen(real, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    stderr_b = proc.stderr.read() if proc.stderr else b""
    if proc.stderr:
        proc.stderr.close()
    _pid, status, rusage = os.wait4(proc.pid, 0)
    proc.returncode = os.waitstatus_to_exitcode(status)  # mark reaped for Popen
    wall = time.perf_counter() - t0
    maxrss = rusage.ru_maxrss
    if sys.platform == "darwin":  # macOS reports bytes; Linux reports KiB
        maxrss //= 1024
    rc = os.waitstatus_to_exitcode(status)
    return wall, int(maxrss), rc, stderr_b.decode("utf-8", "replace")


def measure(cmd: list[str], *, best_of: int = 5, warmup: int = 1,
            pin_cpu: int | None = None, before_each=None,
            dry_run: bool = False) -> RunStats:
    """Time ``cmd`` ``best_of`` times after ``warmup`` discarded run(s).

    ``before_each`` is an optional callable invoked before every invocation
    (e.g. to delete a stale output file). Bytes are deterministic so they are
    captured by the caller from the final output; here we only time + RSS.
    """
    if dry_run:
        print("    $", " ".join(cmd))
        return RunStats(samples_ms=[0.0], warmup_ms=0.0)

    stats = RunStats()
    total = warmup + best_of
    for i in range(total):
        if before_each:
            before_each()
        wall, rss, rc, err = run_once(cmd, pin_cpu=pin_cpu)
        if rc != 0:
            stats.returncode = rc
            stats.stderr = err
            return stats  # bail on first failure; caller reports it
        ms = wall * 1000.0
        if i < warmup:
            stats.warmup_ms = ms
        else:
            stats.samples_ms.append(ms)
        stats.peak_rss_kib = max(stats.peak_rss_kib, rss)
    stats.samples_ms.sort()
    return stats


# ---------------------------------------------------------------------------
# Machine-health warning (variance discipline §4)
# ---------------------------------------------------------------------------
def load_health() -> dict:
    """Best-effort snapshot of whether the machine looks loaded / throttled.
    Returns a dict with whatever is detectable; callers warn but don't block."""
    info: dict = {}
    try:
        la1, la5, la15 = os.getloadavg()
        info["loadavg"] = [round(la1, 2), round(la5, 2), round(la15, 2)]
        ncpu = os.cpu_count() or 1
        info["loadavg_per_cpu"] = round(la1 / ncpu, 2)
        info["loaded"] = la1 / ncpu > 0.5
    except (OSError, AttributeError):
        pass

    # Linux: read CPU governor + any thermal-throttle hints.
    gov = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    if gov.exists():
        try:
            info["governor"] = gov.read_text().strip()
            info["governor_warn"] = info["governor"] not in ("performance",)
        except OSError:
            pass
    return info


def warn_if_loaded(emit=print) -> dict:
    """Emit a hard warning if the machine looks unfit for stable timing."""
    health = load_health()
    if health.get("loaded"):
        emit(f"  ! WARNING: machine looks loaded (loadavg/cpu="
             f"{health.get('loadavg_per_cpu')}); wall-clock will be noisy.")
    if health.get("governor_warn"):
        emit(f"  ! WARNING: CPU governor is '{health.get('governor')}', not "
             f"'performance'; timing may vary with frequency scaling.")
    return health
