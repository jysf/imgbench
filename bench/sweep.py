"""Quality sweep + equal-quality interpolation + bisection refine + BD-rate.

This is the fairness keystone. Fixed-quality tools have no perceptual target, so
for each tool×image we sweep the quality parameter, grade every output, then read
off "bytes at the target score". The coarse sweep brackets each target; a short
bisection then tightens the bytes-at-target estimate. BD-rate gives a single
quality-normalised number across the whole curve.

The numeric core (``interp_bytes_at_score``, ``bd_rate``, ``bracket_for_target``)
is pure and unit-tested with synthetic points — no encoders needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from concurrent.futures import ThreadPoolExecutor

from .decode import decode_for_grading
from .measure import RunStats, measure, run_once
from .validate import Validity, check_output


@dataclass
class Point:
    quality: float | None
    bytes: int
    score: float | None
    timing: RunStats | None = None
    valid: Validity | None = None
    refined: bool = False

    def as_row(self) -> list:
        t = self.timing
        return [
            self.quality, self.bytes, self.score,
            t.min_ms if t else None,
            t.median_ms if t else None,
            t.mad_ms if t else None,
            t.peak_rss_kib if t else None,
            int(self.refined),
            int(bool(self.valid and self.valid.ok)) if self.valid else 1,
        ]


# ---------------------------------------------------------------------------
# Pure numeric core
# ---------------------------------------------------------------------------
def _usable(points: list[Point]) -> list[Point]:
    """Points with a score and a valid output, eligible for the curve."""
    return [p for p in points
            if p.score is not None and (p.valid is None or p.valid.ok)]


def bracket_for_target(points: list[Point], target: float, higher_is_better=True):
    """Return (lo, hi) points whose scores bracket ``target``, else (None, None).
    lo is the point on the worse-quality side, hi on the better-quality side."""
    pts = sorted(_usable(points), key=lambda p: p.score)
    lo = hi = None
    for p in pts:
        on_low_side = p.score <= target if higher_is_better else p.score >= target
        on_high_side = p.score >= target if higher_is_better else p.score <= target
        if on_low_side:
            lo = p
        if on_high_side and hi is None:
            hi = p
    return lo, hi


def interp_bytes_at_score(points: list[Point], target: float,
                          higher_is_better: bool = True):
    """Linear-interpolate output bytes at ``target`` between the two bracketing
    points. Returns an int when bracketed; a flagged ``"~N (extrapolated ...)"``
    string when the target lies outside the swept range; None when no usable
    points exist."""
    pts = _usable(points)
    if not pts:
        return None
    lo, hi = bracket_for_target(points, target, higher_is_better)
    if lo and hi:
        if lo.score == hi.score:
            return lo.bytes  # a point sits exactly on the target
        f = (target - lo.score) / (hi.score - lo.score)
        return round(lo.bytes + f * (hi.bytes - lo.bytes))
    nearest = min(pts, key=lambda p: abs(p.score - target))
    return f"~{nearest.bytes} (extrapolated @ score {nearest.score:.1f})"


# -- BD-rate (Bjøntegaard delta-rate) ---------------------------------------
def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float] | None:
    """Gaussian elimination with partial pivoting. Returns x or None if singular."""
    n = len(matrix)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-12:
            return None
        a[col], a[piv] = a[piv], a[col]
        for r in range(n):
            if r == col:
                continue
            factor = a[r][col] / a[col][col]
            for c in range(col, n + 1):
                a[r][c] -= factor * a[col][c]
    return [a[i][n] / a[i][i] for i in range(n)]


def _polyfit(xs: list[float], ys: list[float], degree: int) -> list[float] | None:
    """Least-squares polynomial fit; returns coeffs [c0..c_degree] or None."""
    degree = min(degree, len(xs) - 1)
    if degree < 1:
        return None
    # Normal equations: (V^T V) c = V^T y, with Vandermonde V.
    m = degree + 1
    powsum = [0.0] * (2 * degree + 1)
    for x in xs:
        p = 1.0
        for k in range(2 * degree + 1):
            powsum[k] += p
            p *= x
    mat = [[powsum[i + j] for j in range(m)] for i in range(m)]
    rhs = [0.0] * m
    for x, y in zip(xs, ys):
        p = 1.0
        for i in range(m):
            rhs[i] += y * p
            p *= x
    return _solve(mat, rhs)


def _polyint_eval(coeffs: list[float], a: float, b: float) -> float:
    """Definite integral of the polynomial from a to b."""
    def antideriv(x):
        return sum(c / (i + 1) * x ** (i + 1) for i, c in enumerate(coeffs))
    return antideriv(b) - antideriv(a)


def bd_rate(anchor: list[Point], test: list[Point]) -> float | None:
    """Bjøntegaard delta-rate of ``test`` vs ``anchor`` (percent).

    Negative = test needs fewer bytes at equal quality (better). Integrates
    log10(bytes) over the overlapping quality (SSIMULACRA2) range. Returns None
    if the curves don't overlap or have too few points.
    """
    import math

    def curve(points):
        pts = sorted(_usable(points), key=lambda p: p.score)
        xs = [p.score for p in pts]
        ys = [math.log10(p.bytes) for p in pts if p.bytes > 0]
        return xs, ys

    ax, ay = curve(anchor)
    tx, ty = curve(test)
    if len(ax) < 2 or len(tx) < 2:
        return None
    lo = max(min(ax), min(tx))
    hi = min(max(ax), max(tx))
    if hi - lo <= 1e-9:
        return None
    deg = 3 if min(len(ax), len(tx)) >= 4 else 1
    ca = _polyfit(ax, ay, deg)
    ct = _polyfit(tx, ty, deg)
    if not ca or not ct:
        return None
    int_a = _polyint_eval(ca, lo, hi)
    int_t = _polyint_eval(ct, lo, hi)
    avg_diff = (int_t - int_a) / (hi - lo)
    return (10 ** avg_diff - 1.0) * 100.0


# ---------------------------------------------------------------------------
# Orchestration (uses encoders; covered by integration runs, not unit tests)
# ---------------------------------------------------------------------------
@dataclass
class SweepResult:
    tool: str
    image: str
    fmt: str
    mode: str  # "sweep" | "lossless"
    coarse: list[Point] = field(default_factory=list)
    refined: list[Point] = field(default_factory=list)
    targets: dict = field(default_factory=dict)   # target -> {coarse, refined}
    bd_rate_vs: dict = field(default_factory=dict)  # anchor_tool -> percent

    @property
    def all_points(self) -> list[Point]:
        return self.coarse + self.refined


def _encode_only(adapter, cfg, img, fmt, q, scratch_dir, *, best_of, warmup,
                 pin_cpu, timed, dry_run):
    """Encode one quality point and size it. Returns (Point, output_path) with
    score/valid UNSET (filled later by grading), or (None, None) on failure.

    ``timed=True`` runs the best-of-N measurement (serial, uncontended — timing
    fidelity). ``timed=False`` runs a single encode (fast/throughput mode);
    bytes are deterministic so the RD curve is identical, but timing is not
    recorded (``Point.timing is None``)."""
    scratch_dir.mkdir(parents=True, exist_ok=True)
    qtag = "lossless" if q is None else f"q{q}"
    outp = scratch_dir / f"{adapter.name}_{img.stem}_{qtag}.{fmt}"

    def cleanup():
        if outp.exists():
            outp.unlink()
        if adapter.writes_to_dir:
            for f in scratch_dir.glob(f"*.{fmt}"):
                if f != img:
                    f.unlink()

    cmd = adapter.cmd(img, outp, fmt, q, cfg)
    if dry_run:
        measure(cmd, dry_run=True)  # prints the command
        return None, None

    if timed:
        stats = measure(cmd, best_of=best_of, warmup=warmup, pin_cpu=pin_cpu,
                        before_each=cleanup)
        rc, err = stats.returncode, stats.stderr
    else:
        cleanup()
        _wall, _rss, rc, err = run_once(cmd, pin_cpu=pin_cpu)
        stats = None
    if rc != 0:
        print(f"    ! {adapter.name} {qtag} failed rc={rc}: {err.strip()[:120]}")
        return None, None

    produced = _normalise_output(adapter, outp, fmt, scratch_dir, img)
    if produced is None or not produced.exists():
        print(f"    ! {adapter.name} {qtag}: no output produced")
        return None, None
    point = Point(quality=q, bytes=produced.stat().st_size, score=None,
                  timing=stats, valid=None)
    return point, produced


def _grade_and_validate(point: Point, produced: Path, img: Path, grader) -> Point:
    """Fill in a point's score + validity. Pure (no timing side effects), so it
    is safe to run in parallel AFTER all timed encodes for an image complete.

    Validity is checked on the ENCODED output (to catch dropped alpha / resize);
    grading is done on the DECODED pixels (the C grader can't read WebP/AVIF)."""
    point.valid = check_output(img, produced)
    if grader:
        gradable = decode_for_grading(produced, produced.parent)
        point.score = grader.score(img, gradable) if gradable else None
    else:
        point.score = None
    if point.valid and not point.valid.ok:
        qtag = "lossless" if point.quality is None else f"q{point.quality}"
        print(f"    ! {qtag}: invalid output ({'; '.join(point.valid.notes)})")
    return point


def _encode_point(adapter, cfg, img, fmt, q, scratch_dir, grader,
                  best_of, warmup, pin_cpu, dry_run, *, timed=True) -> Point | None:
    """Encode + grade one point, sequentially (used by the bisection refine,
    where each step depends on the previous score)."""
    point, produced = _encode_only(adapter, cfg, img, fmt, q, scratch_dir,
                                   best_of=best_of, warmup=warmup, pin_cpu=pin_cpu,
                                   timed=timed, dry_run=dry_run)
    if point is None:
        return None
    return _grade_and_validate(point, produced, img, grader)


def _normalise_output(adapter, outp: Path, fmt: str, scratch_dir: Path, img: Path):
    """Dir-writing tools name their own output; move the single produced image
    to the canonical ``outp`` so the rest of the pipeline is uniform."""
    if not adapter.writes_to_dir:
        return outp if outp.exists() else None
    if outp.exists():
        return outp
    candidates = [f for f in scratch_dir.glob(f"*.{fmt}")
                  if f != img and f != outp]
    if len(candidates) == 1:
        candidates[0].replace(outp)
        return outp
    return candidates[0] if candidates else None


def sweep_image(adapter, img: Path, fmt: str, grader, cfg, *, targets,
                best_of=5, warmup=1, pin_cpu=None, refine_iters=3,
                dry_run=False, workdir: Path, timed=True, grade_jobs=1,
                quiet=False) -> SweepResult:
    """Coarse sweep + bisection refine for one adapter×image×format.

    Timing fidelity is preserved by ENCODING the whole coarse sweep serially
    (and uncontended) FIRST, then grading those outputs in parallel — grading
    never overlaps a timed encode. ``grade_jobs`` parallelises that grading;
    ``timed=False`` skips timing entirely (fast mode)."""
    mode = "lossless" if adapter.lossless else "sweep"
    res = SweepResult(tool=adapter.name, image=img.name, fmt=fmt, mode=mode)

    point_dir = workdir / adapter.name / fmt / img.stem

    # Phase 1: encode every coarse point serially (timed) — no grading yet.
    encoded: list[tuple[Point, Path]] = []
    for q in adapter.quality_range(fmt):
        pt, produced = _encode_only(
            adapter, cfg, img, fmt, q,
            point_dir / (f"q{q}" if q is not None else "lossless"),
            best_of=best_of, warmup=warmup, pin_cpu=pin_cpu, timed=timed,
            dry_run=dry_run)
        if pt is not None:
            encoded.append((pt, produced))

    if dry_run:
        return res

    # Phase 2: grade + validate the coarse outputs IN PARALLEL. This runs only
    # after all of this image's timed encodes are done, so it cannot perturb
    # any wall-clock measurement.
    if grade_jobs and grade_jobs > 1 and len(encoded) > 1:
        with ThreadPoolExecutor(max_workers=grade_jobs) as ex:
            list(ex.map(lambda ep: _grade_and_validate(ep[0], ep[1], img, grader),
                        encoded))
    else:
        for pt, produced in encoded:
            _grade_and_validate(pt, produced, img, grader)

    res.coarse = [pt for pt, _ in encoded]
    if not quiet:
        for pt in res.coarse:
            _print_point(adapter, fmt, pt)

    if mode == "lossless":
        return res

    # Bisection refine near each target (sequential: each step needs the
    # previous score). Few points, so serial grading here is fine.
    def encode_q(q):
        p = _encode_point(adapter, cfg, img, fmt, round(q),
                          point_dir / f"refine_q{round(q)}", grader,
                          best_of, warmup, pin_cpu, dry_run, timed=timed)
        if p is not None and not quiet:
            _print_point(adapter, fmt, p)
        return p

    seen_q = {p.quality for p in res.coarse}
    for t in targets:
        lo, hi = bracket_for_target(res.coarse, t)
        if not (lo and hi) or lo.quality is None or hi.quality is None:
            res.targets[str(t)] = {
                "coarse": interp_bytes_at_score(res.coarse, t),
                "refined": None,
                "note": "target not bracketed by coarse sweep",
            }
            continue
        q_lo, q_hi = lo.quality, hi.quality
        for _ in range(refine_iters):
            q_mid = (q_lo + q_hi) / 2
            if round(q_mid) in seen_q or abs(q_hi - q_lo) <= 1:
                break
            seen_q.add(round(q_mid))
            pm = encode_q(q_mid)
            if pm is None or pm.score is None:
                break
            pm.refined = True
            res.refined.append(pm)
            # Narrow toward the target on the quality axis.
            if pm.score < t:
                q_lo = q_mid
            else:
                q_hi = q_mid
        combined = res.coarse + res.refined
        res.targets[str(t)] = {
            "coarse": interp_bytes_at_score(res.coarse, t),
            "refined": interp_bytes_at_score(combined, t),
        }
    return res


def _print_point(adapter, fmt, p: Point):
    sc = f"{p.score:.2f}" if p.score is not None else "n/a"
    qtag = "lossless" if p.quality is None else f"q{p.quality}"
    ms = p.timing.median_ms if p.timing and p.timing.median_ms is not None else 0.0
    flag = "" if (p.valid is None or p.valid.ok) else "  [INVALID]"
    tag = "*" if p.refined else " "
    print(f"   {tag}{adapter.name:10s} {fmt:4s} {qtag:<9s} {p.bytes:8d}B  "
          f"ss2={sc:>7s}  {ms:7.1f}ms{flag}")
