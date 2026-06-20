"""Write per-run artifacts and render the human-readable markdown report.

Artifacts written into the run dir:
  * ``sweep.csv``    — every sweep point (coarse + refined), flat.
  * ``summary.json`` — structured results ``compare`` consumes.
  * ``manifest.json`` — provenance (written by the caller).
  * ``report.md``    — the rendered run report.
"""

from __future__ import annotations

import json
from pathlib import Path

CSV_HEADER = ("tool,format,image,quality,bytes,score,min_ms,median_ms,mad_ms,"
              "peak_rss_kib,refined,valid")


def write_sweep_csv(path: Path, results) -> None:
    lines = [CSV_HEADER]
    for r in results:
        for p in r.all_points:
            row = [r.tool, r.fmt, r.image, *p.as_row()]
            lines.append(",".join("" if x is None else str(x) for x in row))
    path.write_text("\n".join(lines) + "\n")


def build_summary(results, *, targets, primary_grader, config) -> dict:
    out = {
        "targets": targets,
        "primary_grader": primary_grader,
        "config": config,
        "results": [],
    }
    for r in results:
        entry = {
            "tool": r.tool, "image": r.image, "format": r.fmt, "mode": r.mode,
            "targets": r.targets, "bd_rate_vs": r.bd_rate_vs,
        }
        if r.mode == "lossless" and r.coarse:
            p = r.coarse[0]
            entry["lossless"] = {
                "bytes": p.bytes,
                "score": p.score,
                "median_ms": p.timing.median_ms if p.timing else None,
                "min_ms": p.timing.min_ms if p.timing else None,
                "peak_rss_kib": p.timing.peak_rss_kib if p.timing else None,
            }
        # Representative steady-state timing: median across usable points.
        ms = [p.timing.median_ms for p in r.all_points
              if p.timing and p.timing.median_ms is not None]
        entry["median_ms"] = round(sorted(ms)[len(ms) // 2], 3) if ms else None
        out["results"].append(entry)
    return out


def write_summary(path: Path, summary: dict) -> None:
    path.write_text(json.dumps(summary, indent=2) + "\n")


def write_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------
def _fmt_bytes(v):
    if v is None:
        return "—"
    if isinstance(v, str):
        return v  # extrapolation note
    if v >= 1024:
        return f"{v/1024:.1f} KiB"
    return f"{v} B"


def render_markdown(summary: dict, manifest: dict, *, run_id: str) -> str:
    m = manifest.get("machine", {})
    cores = m.get("cores", {})
    lines = [
        f"# Benchmark run `{run_id}`",
        "",
        "> Every size/speed number below is gated on **equal SSIMULACRA2**, "
        "never an equal quality-number. Bytes are read off at a fixed perceptual "
        "score; a smaller file at a different score is not a result.",
        "",
        "## Environment",
        "",
        f"- **CPU:** {m.get('cpu_model')} "
        f"({cores.get('physical')} physical / {cores.get('logical')} logical)",
        f"- **RAM:** {_gib(m.get('ram_bytes'))}",
        f"- **OS:** {m.get('os')}  ·  kernel `{(m.get('kernel') or '')[:60]}`",
        f"- **CPU scaling:** governor={m.get('scaling', {}).get('governor')}, "
        f"turbo={m.get('scaling', {}).get('turbo')}",
        f"- **Primary grader:** `{summary.get('primary_grader')}` "
        f"(independent C reference by default)",
        f"- **Bench:** v{manifest.get('bench_version')} @ "
        f"`{manifest.get('bench_git_sha')}`",
        "",
    ]

    agr = manifest.get("grader_agreement")
    if agr:
        if agr.get("agree") is None:
            lines += [f"_Grader agreement: {agr.get('note', 'not run')}_", ""]
        else:
            verdict = "AGREE" if agr["agree"] else "**DISAGREE**"
            lines += [f"_Grader agreement (C vs Rust SSIMULACRA2): {verdict}, "
                      f"max Δ {agr.get('max_delta')} ≤ tol {agr.get('tolerance')}_",
                      ""]

    cfg = summary.get("config", {})
    lines += [
        "## Fairness controls",
        "",
        f"- threads pinned to **{cfg.get('threads')}**, "
        f"AVIF effort **{cfg.get('avif_effort')}** across all tools",
        f"- metadata stripping: **{cfg.get('strip_metadata')}** "
        f"(byte deltas are not EXIF/ICC)",
        f"- timing: best-of-{cfg.get('best_of')} after {cfg.get('warmup')} "
        f"warmup, median + MAD reported",
        "",
    ]

    mode = cfg.get("mode", "timed")
    if mode == "fast":
        lines += [
            "> ⚠️ **Fast mode** (`--fast`): best-of-1, parallel encodes. "
            "Bytes/quality are exact, but **wall-clock here is NOT trustworthy** "
            "— use this run for size/quality gating only.",
            "",
        ]
    gc = cfg.get("grade_cache") or {}
    if gc.get("enabled") is not False:
        lines += [
            f"- grade cache: {gc.get('hits', 0)} hit / {gc.get('misses', 0)} "
            f"miss (scores memoized by content hash; never bytes or timing)",
            "",
        ]

    targets = summary.get("targets", [])
    lines += _bytes_at_target_tables(summary, targets)
    lines += _lossless_table(summary)
    lines += _bd_rate_table(summary)
    lines += _validity_warnings(summary)

    lines += [
        "## Methodology",
        "",
        "See [`benchmark-methodology.md`](../../benchmark-methodology.md). "
        "Footprint, startup-vs-batch, and the quality-sweep scatter are "
        "additional artifacts in this run dir.",
        "",
    ]
    return "\n".join(lines) + "\n"


def _gib(b):
    return f"{b/1024**3:.1f} GiB" if b else "unknown"


def _group_by_format(summary):
    by_fmt: dict = {}
    for r in summary["results"]:
        by_fmt.setdefault(r["format"], []).append(r)
    return by_fmt


def _bytes_at_target_tables(summary, targets):
    lines = ["## Bytes at equal SSIMULACRA2", ""]
    for fmt, rows in sorted(_group_by_format(summary).items()):
        sweep_rows = [r for r in rows if r["mode"] == "sweep"]
        if not sweep_rows:
            continue
        lines.append(f"### {fmt.upper()}")
        lines.append("")
        hdr = ["image", "tool"] + [f"@ss2≈{int(t)}" for t in targets]
        lines.append("| " + " | ".join(hdr) + " |")
        lines.append("|" + "---|" * len(hdr))
        for r in sorted(sweep_rows, key=lambda x: (x["image"], x["tool"])):
            cells = [r["image"], f"`{r['tool']}`"]
            for t in targets:
                td = r["targets"].get(str(t), {})
                refined = td.get("refined")
                coarse = td.get("coarse")
                cells.append(_fmt_bytes(refined if refined is not None else coarse))
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    return lines


def _lossless_table(summary):
    rows = [r for r in summary["results"] if r["mode"] == "lossless"]
    if not rows:
        return []
    lines = ["## Lossless PNG lane (bytes + speed at score ~100)", "",
             "| image | tool | bytes | score | median ms |",
             "|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: (x["image"], x["tool"])):
        ll = r.get("lossless", {})
        lines.append(f"| {r['image']} | `{r['tool']}` | {_fmt_bytes(ll.get('bytes'))} "
                     f"| {_score(ll.get('score'))} | {_ms(ll.get('median_ms'))} |")
    lines.append("")
    return lines


def _bd_rate_table(summary):
    rows = [r for r in summary["results"] if r.get("bd_rate_vs")]
    if not rows:
        return []
    lines = ["## BD-rate (vs anchor, % bytes at equal quality — negative is better)",
             "", "| image | format | tool | anchor | BD-rate % |",
             "|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: (x["image"], x["format"], x["tool"])):
        for anchor, val in r["bd_rate_vs"].items():
            v = f"{val:+.1f}%" if isinstance(val, (int, float)) else "—"
            lines.append(f"| {r['image']} | {r['format']} | `{r['tool']}` "
                         f"| `{anchor}` | {v} |")
    lines.append("")
    return lines


def _validity_warnings(summary):
    # Validity flags live in the CSV; surface a pointer here.
    return ["## Output validity", "",
            "Per-point dimension/alpha checks are in `sweep.csv` (`valid` "
            "column). Invalid outputs are excluded from the curves above.", ""]


def _score(v):
    return f"{v:.2f}" if isinstance(v, (int, float)) else "—"


def _ms(v):
    return f"{v:.1f}" if isinstance(v, (int, float)) else "—"
