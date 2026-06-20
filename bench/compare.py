"""Compare two runs → a delta report (markdown + CSV) and a CI gate.

``bench compare runs/<A> runs/<B>`` treats A as the baseline and B as the
candidate. It diffs bytes-at-target (80/90), lossless PNG bytes, and wall-clock
per tool×image×format, flags regressions beyond tolerance, and exits non-zero so
CI can gate.

Two regression classes, deliberately separated:
  * **size/quality** — gate-worthy (deterministic; a real product regression).
  * **speed** — informational by default (noisy on shared/thermal machines);
    only gates when ``--gate-speed`` is passed.

If the two runs' tool versions drifted, the comparison is flagged (and refused
unless ``--allow-version-drift``): a byte delta across encoder versions isn't a
clean result.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import MANIFEST_SCHEMA


@dataclass
class Delta:
    tool: str
    fmt: str
    image: str
    metric: str          # e.g. "bytes@80", "lossless_bytes", "median_ms"
    kind: str            # "size" | "speed"
    a: float | None
    b: float | None
    pct: float | None    # (b-a)/a * 100; positive = B larger/slower
    regression: bool = False

    def as_row(self) -> list:
        return [self.tool, self.fmt, self.image, self.metric, self.kind,
                _num(self.a), _num(self.b), _pct(self.pct),
                "REGRESSION" if self.regression else ""]


@dataclass
class Comparison:
    deltas: list[Delta] = field(default_factory=list)
    version_drift: list[str] = field(default_factory=list)
    schema_mismatch: bool = False
    size_tol: float = 0.02
    speed_tol: float = 0.10
    gate_speed: bool = False

    @property
    def size_regressions(self) -> list[Delta]:
        return [d for d in self.deltas if d.kind == "size" and d.regression]

    @property
    def speed_regressions(self) -> list[Delta]:
        return [d for d in self.deltas if d.kind == "speed" and d.regression]

    def gated(self) -> bool:
        """True when CI should fail."""
        if self.size_regressions:
            return True
        if self.gate_speed and self.speed_regressions:
            return True
        return False


# ---------------------------------------------------------------------------
# Loading + indexing
# ---------------------------------------------------------------------------
def _load(run_dir: Path) -> tuple[dict, dict]:
    summary = json.loads((run_dir / "summary.json").read_text())
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    return summary, manifest


def _coerce_bytes(v):
    """bytes-at-target may be an int or an extrapolation string; only ints
    compare cleanly."""
    return v if isinstance(v, (int, float)) else None


def index_metrics(summary: dict, targets) -> dict:
    """Flatten a summary into {(tool, fmt, image, metric): (value, kind)}."""
    idx: dict = {}
    for r in summary["results"]:
        key = (r["tool"], r["format"], r["image"])
        if r["mode"] == "sweep":
            for t in targets:
                td = r["targets"].get(str(t), {})
                val = td.get("refined")
                if val is None:
                    val = td.get("coarse")
                idx[(*key, f"bytes@{int(t)}")] = (_coerce_bytes(val), "size")
        elif r["mode"] == "lossless":
            ll = r.get("lossless", {})
            idx[(*key, "lossless_bytes")] = (_coerce_bytes(ll.get("bytes")), "size")
        if r.get("median_ms") is not None:
            idx[(*key, "median_ms")] = (r["median_ms"], "speed")
    return idx


# ---------------------------------------------------------------------------
# Version-drift detection
# ---------------------------------------------------------------------------
def detect_version_drift(man_a: dict, man_b: dict) -> list[str]:
    drift = []
    ta, tb = man_a.get("tools", {}), man_b.get("tools", {})
    for name in sorted(set(ta) | set(tb)):
        va = (ta.get(name) or {}).get("version")
        vb = (tb.get(name) or {}).get("version")
        if va != vb:
            drift.append(f"{name}: {va!r} -> {vb!r}")
    ga, gb = man_a.get("graders", {}), man_b.get("graders", {})
    pa, pb = man_a.get("primary_grader"), man_b.get("primary_grader")
    if pa != pb:
        drift.append(f"primary_grader: {pa!r} -> {pb!r}")
    for name in sorted(set(ga) | set(gb)):
        va = (ga.get(name) or {}).get("version")
        vb = (gb.get(name) or {}).get("version")
        if va != vb:
            drift.append(f"grader {name}: {va!r} -> {vb!r}")
    return drift


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------
def compare_runs(dir_a: Path, dir_b: Path, *, size_tol: float = 0.02,
                 speed_tol: float = 0.10, gate_speed: bool = False,
                 targets=None) -> Comparison:
    sum_a, man_a = _load(dir_a)
    sum_b, man_b = _load(dir_b)
    targets = targets or sum_a.get("targets") or sum_b.get("targets") or [80.0, 90.0]

    cmp = Comparison(size_tol=size_tol, speed_tol=speed_tol, gate_speed=gate_speed)
    cmp.schema_mismatch = (man_a.get("schema") != man_b.get("schema")
                           and bool(man_a) and bool(man_b))
    cmp.version_drift = detect_version_drift(man_a, man_b)

    idx_a = index_metrics(sum_a, targets)
    idx_b = index_metrics(sum_b, targets)
    for key in sorted(set(idx_a) | set(idx_b)):
        tool, fmt, image, metric = key
        a_pair, b_pair = idx_a.get(key), idx_b.get(key)
        a_val = a_pair[0] if a_pair else None
        b_val = b_pair[0] if b_pair else None
        kind = (a_pair or b_pair)[1]
        pct = None
        regression = False
        if isinstance(a_val, (int, float)) and isinstance(b_val, (int, float)) and a_val:
            pct = (b_val - a_val) / a_val * 100.0
            tol = size_tol if kind == "size" else speed_tol
            regression = (b_val - a_val) / a_val > tol  # B worse than A
        cmp.deltas.append(Delta(tool, fmt, image, metric, kind,
                                a_val, b_val, pct, regression))
    return cmp


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _num(v):
    if v is None:
        return ""
    return f"{v:.0f}" if isinstance(v, float) and abs(v) >= 100 else str(v)


def _pct(v):
    return "" if v is None else f"{v:+.1f}%"


def render_csv(cmp: Comparison) -> str:
    lines = ["tool,format,image,metric,kind,baseline,candidate,delta_pct,flag"]
    for d in cmp.deltas:
        lines.append(",".join(str(x) for x in d.as_row()))
    return "\n".join(lines) + "\n"


def render_markdown(cmp: Comparison, dir_a: Path, dir_b: Path) -> str:
    lines = [
        "# Run comparison",
        "",
        f"- **baseline (A):** `{dir_a.name}`",
        f"- **candidate (B):** `{dir_b.name}`",
        f"- size tolerance: {cmp.size_tol*100:.1f}%  ·  "
        f"speed tolerance: {cmp.speed_tol*100:.1f}% "
        f"({'gated' if cmp.gate_speed else 'informational'})",
        "",
    ]
    if cmp.schema_mismatch:
        lines += ["> ⚠️ **manifest schema mismatch** between runs — "
                  "results may not be comparable.", ""]
    if cmp.version_drift:
        lines += ["## ⚠️ Tool/grader version drift", "",
                  "A byte delta across encoder versions is not a clean result:",
                  ""]
        lines += [f"- {d}" for d in cmp.version_drift]
        lines.append("")

    size_regs = cmp.size_regressions
    speed_regs = cmp.speed_regressions
    verdict = "FAIL" if cmp.gated() else "PASS"
    lines += [f"## Verdict: **{verdict}**", "",
              f"- size/quality regressions (gate-worthy): **{len(size_regs)}**",
              f"- speed regressions (informational"
              f"{', gated' if cmp.gate_speed else ''}): **{len(speed_regs)}**",
              ""]

    lines += _delta_section("Size / quality deltas", "size", cmp)
    lines += _delta_section("Speed deltas", "speed", cmp)
    return "\n".join(lines) + "\n"


def _delta_section(title, kind, cmp: Comparison):
    rows = [d for d in cmp.deltas if d.kind == kind]
    if not rows:
        return []
    lines = [f"## {title}", "",
             "| tool | format | image | metric | A | B | Δ | |",
             "|---|---|---|---|---|---|---|---|"]
    for d in sorted(rows, key=lambda x: (not x.regression, x.tool, x.image)):
        flag = "🔴" if d.regression else ""
        lines.append(f"| `{d.tool}` | {d.fmt} | {d.image} | {d.metric} "
                     f"| {_num(d.a)} | {_num(d.b)} | {_pct(d.pct)} | {flag} |")
    lines.append("")
    return lines


def write_reports(cmp: Comparison, dir_a: Path, dir_b: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / f"compare_{dir_a.name}__vs__{dir_b.name}.md"
    csv = out_dir / f"compare_{dir_a.name}__vs__{dir_b.name}.csv"
    md.write_text(render_markdown(cmp, dir_a, dir_b))
    csv.write_text(render_csv(cmp))
    return {"markdown": md, "csv": csv}
