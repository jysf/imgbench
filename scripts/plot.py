#!/usr/bin/env python3
"""Render the quality-sweep scatter from a run's sweep.csv.

OPTIONAL extra — needs matplotlib (see requirements-optional.txt). The core
benchmark never imports this; plotting is strictly opt-in so CI stays
stdlib-only.

    pip install -r requirements-optional.txt
    python scripts/plot.py runs/latest

Produces, per image, one PNG with x = SSIMULACRA2, y = bytes (log), one line
per tool — "the single most honest visual" from the methodology.
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    sys.exit("matplotlib not installed — `pip install -r requirements-optional.txt`")


def main(run_dir: Path) -> int:
    csv_path = run_dir / "sweep.csv"
    if not csv_path.exists():
        sys.exit(f"no sweep.csv in {run_dir}")
    out_dir = run_dir / "plots"
    out_dir.mkdir(exist_ok=True)

    # (image, fmt) -> tool -> [(score, bytes)]
    series = defaultdict(lambda: defaultdict(list))
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            if not row["score"] or row["valid"] == "0":
                continue
            try:
                score = float(row["score"])
                byts = int(row["bytes"])
            except ValueError:
                continue
            series[(row["image"], row["format"])][row["tool"]].append((score, byts))

    written = []
    for (image, fmt), tools in sorted(series.items()):
        fig, ax = plt.subplots(figsize=(7, 5))
        for tool, pts in sorted(tools.items()):
            pts.sort()
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            ax.plot(xs, ys, marker="o", label=tool)
        ax.set_xlabel("SSIMULACRA2 (higher = better)")
        ax.set_ylabel("bytes")
        ax.set_yscale("log")
        ax.set_title(f"{image} — {fmt}")
        ax.axvline(80, ls="--", c="grey", lw=0.8)
        ax.axvline(90, ls="--", c="grey", lw=0.8)
        ax.legend()
        ax.grid(True, which="both", ls=":", alpha=0.4)
        out = out_dir / f"sweep_{Path(image).stem}_{fmt}.png"
        fig.tight_layout()
        fig.savefig(out, dpi=110)
        plt.close(fig)
        written.append(out)

    print(f"wrote {len(written)} plot(s) to {out_dir}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: plot.py runs/<run-dir>")
    raise SystemExit(main(Path(sys.argv[1])))
