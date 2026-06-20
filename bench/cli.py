"""bench — argparse entrypoint: check / run / compare / corpus / footprint.

Run versioning is the highest-priority feature: every ``run`` writes to an
immutable ``runs/<UTC>-<bench-sha>/`` and updates the ``runs/latest`` symlink;
nothing is ever overwritten.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, grade, provenance, report
from .adapters import all_adapters, by_name as adapter_by_name
from .compare import compare_runs, write_reports
from .footprint import capture as capture_footprint, cold_install_seconds
from .measure import warn_if_loaded
from .sweep import bd_rate, sweep_image
from .adapters.base import EncodeConfig

SRC_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def find_images(inputs: Path) -> list[Path]:
    if inputs.is_file():
        return [inputs]
    return sorted(p for p in inputs.iterdir()
                  if p.suffix.lower() in SRC_SUFFIXES)


def make_run_dir(runs_root: Path, bench_sha: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = runs_root / f"{stamp}-{bench_sha}"
    run_dir.mkdir(parents=True, exist_ok=False)
    # Update runs/latest -> this dir (relative symlink), atomically.
    latest = runs_root / "latest"
    tmp = runs_root / ".latest.tmp"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(run_dir.name, tmp)
    os.replace(tmp, latest)
    return run_dir


def select_adapters(names: list[str] | None):
    adapters = all_adapters()
    if names:
        chosen = [adapter_by_name(n) for n in names]
        missing = [n for n, a in zip(names, chosen) if a is None]
        if missing:
            sys.exit(f"unknown tool(s): {missing}")
        return chosen
    return adapters


def run_agreement_check(images, cfg, scratch: Path) -> dict:
    """Encode a few images once and confirm the two SSIMULACRA2 builds agree."""
    c, rs = grade.GRADERS["ssimulacra2"], grade.GRADERS["ssimulacra2_rs"]
    if not (c.available() and rs.available()):
        return grade.agreement_check([])  # records the "skipped" note
    # Use the first available lossy adapter to produce comparison images.
    enc = next((a for a in all_adapters()
                if a.available() and not a.lossless and "webp" in a.formats), None)
    if enc is None:
        return grade.agreement_check([])
    scratch.mkdir(parents=True, exist_ok=True)
    pairs = []
    for img in images[:3]:
        outp = scratch / f"agree_{img.stem}.webp"
        from .measure import run_once
        run_once(enc.cmd(img, outp, "webp", 80, cfg))
        # dir-writing tools land the file elsewhere; find it
        if not outp.exists() and getattr(enc, "writes_to_dir", False):
            cands = [f for f in scratch.glob("*.webp") if f != outp]
            if cands:
                cands[0].replace(outp)
        if outp.exists():
            pairs.append((img, outp))
    return grade.agreement_check(pairs)


def compute_bd_rates(results, anchor_pref=("rimage", "cwebp", "sharp")):
    """For each (fmt, image), pick an anchor tool and compute BD-rate of each
    other sweep tool against it. Mutates ``result.bd_rate_vs``."""
    by_key: dict = {}
    for r in results:
        if r.mode == "sweep":
            by_key.setdefault((r.fmt, r.image), []).append(r)
    for (_fmt, _img), group in by_key.items():
        names = {r.tool for r in group}
        anchor_name = next((a for a in anchor_pref if a in names), None)
        if anchor_name is None:
            continue
        anchor = next(r for r in group if r.tool == anchor_name)
        for r in group:
            if r.tool == anchor_name:
                continue
            val = bd_rate(anchor.all_points, r.all_points)
            if val is not None:
                r.bd_rate_vs[anchor_name] = round(val, 2)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------
def cmd_check(args) -> int:
    primary = grade.default_grader()
    print(f"bench v{__version__}")
    print("\ngraders:")
    for g in grade.all_graders():
        star = " (primary)" if primary and g.name == primary.name else ""
        ver = g.version() if g.available() else "MISSING"
        print(f"  {g.name:16s}: {'ok' if g.available() else 'missing':8s} {ver or ''}{star}")
    if not primary:
        print("  ! no SSIMULACRA2 grader on PATH — install cloudinary/ssimulacra2")
    print("\ntools:")
    for a in all_adapters():
        ver = a.version() if a.available() else f"missing ({a.binary})"
        print(f"  {a.name:16s}: {'ok' if a.available() else 'missing':8s} {ver or ''}")
    return 0


def cmd_run(args) -> int:
    images = find_images(args.inputs)
    if not images:
        sys.exit(f"no source images in {args.inputs}")

    grader = grade.by_name(args.grader) if args.grader else grade.default_grader()
    if grader is None and not args.dry_run:
        sys.exit("ERROR: no SSIMULACRA2 grader on PATH (see `bench check`).")
    if grader and not grader.available() and not args.dry_run:
        sys.exit(f"ERROR: grader '{args.grader}' not available.")

    adapters = [a for a in select_adapters(args.tools) if a.available() or args.dry_run]
    if not adapters:
        sys.exit("no requested tools are installed (see `bench check`).")

    cfg = EncodeConfig(threads=args.threads, avif_effort=args.avif_effort,
                       strip_metadata=not args.no_strip)

    # crustyimg build-feature gate: a lossy comparison needs webp-lossy,avif.
    lossy_requested = any(f in ("webp", "avif") for f in args.formats)
    crusty = adapter_by_name("crustyimg")
    if crusty and crusty.available() and lossy_requested:
        ok, reason = crusty.feature_check(lossy=True)
        if not ok:
            sys.exit(f"ERROR: {reason}")

    warn_if_loaded()

    bench_sha = provenance.bench_git_sha(Path(__file__).resolve().parent.parent.parent)
    if args.dry_run:
        run_dir = Path(tempfile.mkdtemp(prefix="bench-dryrun-"))
        print(f"# dry-run; scratch dir {run_dir}")
    else:
        run_dir = make_run_dir(args.runs_root, bench_sha)
        print(f"# run dir: {run_dir}")
    workdir = run_dir / "_enc"

    # Persistent grade cache (content-addressed; see grade/cache.py). Memoizes
    # the deterministic grader across runs — never bytes or timing. The
    # agreement check below deliberately uses the RAW graders, bypassing it.
    cache = None
    base_grader = grader
    if grader and not args.dry_run and not args.no_grade_cache:
        cache = grade.GradeCache(args.grade_cache).load()
        grader = grade.CachingGrader(base_grader, cache)

    timed = not args.fast
    ncpu = os.cpu_count() or 4
    jobs = args.jobs or ncpu
    # In fast mode the OUTER pool parallelises whole units, so keep per-unit
    # grading serial to avoid oversubscription. In timed mode units run serially
    # (timing fidelity), so grading is where intra-unit parallelism helps.
    grade_jobs = 1 if args.fast else (args.grade_jobs or ncpu)

    # Grader agreement sanity-check (independent of the sweep).
    agreement = None
    if not args.dry_run and grader:
        agreement = run_agreement_check(images, cfg, workdir / "_agree")
        if agreement.get("agree") is False:
            print(f"  ! WARNING: SSIMULACRA2 implementations disagree "
                  f"(max Δ {agreement.get('max_delta')} > tol {agreement.get('tolerance')})")

    # Build the (adapter, format, image) work units.
    units = [(a, fmt, img) for a in adapters for fmt in args.formats
             if fmt in a.formats for img in images]

    def run_unit(a, fmt, img):
        return sweep_image(a, img, fmt, grader, cfg, targets=args.targets,
                           best_of=args.best_of, warmup=args.warmup,
                           pin_cpu=args.pin_cpu, refine_iters=args.refine_iters,
                           dry_run=args.dry_run, workdir=workdir,
                           timed=timed, grade_jobs=grade_jobs, quiet=args.fast)

    results = []
    if args.fast and not args.dry_run:
        # Fast mode: timing is NOT trusted, so encodes may run concurrently
        # across units for maximum throughput (bytes are deterministic).
        print(f"# fast mode: best-of-1, {jobs}-way parallel, timing NOT recorded")
        lock = threading.Lock()
        done = 0
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            futs = {ex.submit(run_unit, a, fmt, img): (a, fmt, img)
                    for a, fmt, img in units}
            for fut in as_completed(futs):
                a, fmt, img = futs[fut]
                results.append(fut.result())
                with lock:
                    done += 1
                    print(f"  [{done}/{len(units)}] {a.name}/{fmt}/{img.name}")
    else:
        # Timed (default) mode: units run SERIALLY and uncontended so wall-clock
        # is trustworthy; grading within each unit is parallelised post-encode.
        for a, fmt, img in units:
            if not args.dry_run:
                print(f"== {a.name} / {fmt} / {img.name} ==")
            results.append(run_unit(a, fmt, img))

    if args.dry_run:
        print("\n# dry-run complete (no artifacts written).")
        return 0

    if cache:
        cache.save()

    compute_bd_rates(results)

    config_record = {
        "formats": args.formats, "targets": args.targets,
        "best_of": args.best_of, "warmup": args.warmup, "threads": args.threads,
        "avif_effort": args.avif_effort, "strip_metadata": not args.no_strip,
        "pin_cpu": args.pin_cpu, "refine_iters": args.refine_iters,
        "mode": "fast" if args.fast else "timed",
        "timing_trustworthy": timed,
        "parallel_jobs": jobs if args.fast else 1,
        "grade_jobs": grade_jobs,
        "grade_cache": (cache.stats() if cache else {"enabled": False}),
    }
    manifest = provenance.build_manifest(
        bench_sha=bench_sha, images=images, adapters=all_adapters(),
        graders=grade.all_graders(), primary_grader=base_grader,
        config=config_record, agreement=agreement,
        extra={"footprint": capture_footprint(all_adapters())})

    report.write_manifest(run_dir / "manifest.json", manifest)
    report.write_sweep_csv(run_dir / "sweep.csv", results)
    summary = report.build_summary(results, targets=args.targets,
                                    primary_grader=grader.name if grader else None,
                                    config=config_record)
    report.write_summary(run_dir / "summary.json", summary)
    md = report.render_markdown(summary, manifest, run_id=run_dir.name)
    (run_dir / "report.md").write_text(md)

    # Also drop the rendered report into reports/ for easy browsing.
    args.reports_root.mkdir(parents=True, exist_ok=True)
    (args.reports_root / f"{run_dir.name}.md").write_text(md)

    print(f"\nWrote {run_dir}/ (manifest.json, sweep.csv, summary.json, report.md)")
    print(f"Rendered report: {args.reports_root / (run_dir.name + '.md')}")
    if cache:
        s = cache.stats()
        print(f"grade cache: {s['hits']} hit / {s['misses']} miss "
              f"(hit rate {s['hit_rate']}), {s['entries']} entries @ {s['path']}")
    if args.fast:
        print("NOTE: fast mode — wall-clock in this run is NOT trustworthy "
              "(best-of-1, parallel). Use it for size/quality gating only.")
    return 0


def cmd_cache(args) -> int:
    cache = grade.GradeCache(args.grade_cache).load()
    if args.clear:
        cache.clear()
        print(f"cleared grade cache at {args.grade_cache}")
        return 0
    s = cache.stats()
    print(f"grade cache @ {s['path']}")
    print(f"  entries: {s['entries']}")
    print(f"  (hits/misses are per-process; 0/0 here since nothing graded yet)")
    print("  clear with: bench cache --clear   |   bypass a run with: run --no-grade-cache")
    return 0


def cmd_compare(args) -> int:
    cmp = compare_runs(args.run_a, args.run_b, size_tol=args.size_tol,
                       speed_tol=args.speed_tol, gate_speed=args.gate_speed,
                       targets=args.targets)
    if cmp.version_drift and not args.allow_version_drift:
        print("ERROR: tool/grader versions drifted between runs:")
        for d in cmp.version_drift:
            print(f"  - {d}")
        print("Re-run with --allow-version-drift to compare anyway.")
        return 3
    paths = write_reports(cmp, args.run_a, args.run_b, args.reports_root)
    print(f"Wrote {paths['markdown']}")
    print(f"Wrote {paths['csv']}")
    print(f"size/quality regressions: {len(cmp.size_regressions)}; "
          f"speed regressions: {len(cmp.speed_regressions)}")
    if cmp.gated():
        print("VERDICT: FAIL (regression beyond tolerance)")
        return 1
    print("VERDICT: PASS")
    return 0


def cmd_corpus(args) -> int:
    from .imageio import probe
    corpus_md = args.corpus / "CORPUS.md"
    images = find_images(args.corpus / "images")
    expected = _parse_corpus_hashes(corpus_md) if corpus_md.exists() else {}
    rc = 0
    print(f"corpus: {len(images)} image(s) under {args.corpus/'images'}")
    for img in images:
        digest = provenance.sha256_file(img)
        try:
            info = probe(img)
            dims = f"{info.width}x{info.height}{' +alpha' if info.has_alpha else ''}"
        except (ValueError, OSError):
            dims = "unprobeable"
        exp = expected.get(img.name)
        if exp is None:
            status = "no recorded sha256 in CORPUS.md"
        elif exp == digest:
            status = "OK"
        else:
            status = f"SHA MISMATCH (expected {exp[:12]}…)"
            rc = 2
        print(f"  {img.name:30s} {dims:18s} {digest[:12]}…  {status}")
    if rc:
        print("\nCorpus verification FAILED — recorded hashes do not match.")
    return rc


def cmd_footprint(args) -> int:
    fp = capture_footprint(all_adapters())
    if args.cold_install:
        fp["cold_install"] = cold_install_seconds(args.dockerfile)
    print(json.dumps(fp, indent=2))
    return 0


def _parse_corpus_hashes(corpus_md: Path) -> dict:
    """Pull (filename, sha256) pairs out of CORPUS.md. Lenient: matches any
    line that mentions a known image filename and a 64-hex digest."""
    import re
    text = corpus_md.read_text()
    out = {}
    hexre = re.compile(r"\b([0-9a-fA-F]{64})\b")
    for line in text.splitlines():
        m = hexre.search(line)
        if not m:
            continue
        for tok in re.findall(r"[\w\-.]+\.(?:png|jpe?g|webp|tiff?)", line, re.I):
            out[tok] = m.group(1).lower()
    return out


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    here = Path(__file__).resolve().parent.parent  # imgbench/
    ap = argparse.ArgumentParser(prog="bench",
                                 description="equal-SSIMULACRA2 image benchmark")
    ap.add_argument("--version", action="version", version=f"bench {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="report tool/grader availability")

    r = sub.add_parser("run", help="run the sweep")
    r.add_argument("--inputs", type=Path, default=here / "corpus" / "images")
    r.add_argument("--runs-root", type=Path, default=here / "runs")
    r.add_argument("--reports-root", type=Path, default=here / "reports")
    r.add_argument("--formats", nargs="+", default=["webp", "avif", "jpeg", "png"])
    r.add_argument("--targets", nargs="+", type=float, default=[80.0, 90.0])
    r.add_argument("--best-of", type=int, default=5)
    r.add_argument("--warmup", type=int, default=1)
    r.add_argument("--threads", type=int, default=1)
    r.add_argument("--avif-effort", type=int, default=6)
    r.add_argument("--refine-iters", type=int, default=3)
    r.add_argument("--pin-cpu", type=int, default=None,
                   help="pin encodes to this CPU via taskset (Linux)")
    r.add_argument("--no-strip", action="store_true",
                   help="do NOT strip metadata (default strips for fairness)")
    r.add_argument("--grader", default=None,
                   help="grader name (default: ssimulacra2 C reference)")
    r.add_argument("--tools", nargs="+", default=None,
                   help="subset of tools to run (default: all available)")
    r.add_argument("--dry-run", action="store_true",
                   help="print encode commands; write nothing")
    # -- performance ----------------------------------------------------
    r.add_argument("--fast", action="store_true",
                   help="throughput mode: best-of-1 + parallel encodes for "
                        "size/quality gating. Timing is NOT recorded.")
    r.add_argument("--jobs", type=int, default=None,
                   help="parallel work units in --fast mode (default: CPU count)")
    r.add_argument("--grade-jobs", type=int, default=None,
                   help="parallel grading threads in timed mode "
                        "(default: CPU count; runs only after timed encodes)")
    r.add_argument("--grade-cache", type=Path,
                   default=here / ".cache" / "grade-cache.json",
                   help="persistent score cache path (content-addressed)")
    r.add_argument("--no-grade-cache", action="store_true",
                   help="bypass the grade cache (recompute every score)")

    c = sub.add_parser("compare", help="diff two runs; exit nonzero on regression")
    c.add_argument("run_a", type=Path, help="baseline run dir")
    c.add_argument("run_b", type=Path, help="candidate run dir")
    c.add_argument("--reports-root", type=Path, default=here / "reports")
    c.add_argument("--size-tol", type=float, default=0.02)
    c.add_argument("--speed-tol", type=float, default=0.10)
    c.add_argument("--targets", nargs="+", type=float, default=None)
    c.add_argument("--gate-speed", action="store_true",
                   help="also fail on speed regressions (off by default — noisy)")
    c.add_argument("--allow-version-drift", action="store_true")

    cp = sub.add_parser("corpus", help="verify corpus hashes + probe images")
    cp.add_argument("--corpus", type=Path, default=here / "corpus")

    fp = sub.add_parser("footprint", help="capture per-tool footprint")
    fp.add_argument("--cold-install", action="store_true",
                    help="also build the tools Docker image to time cold install")
    fp.add_argument("--dockerfile", type=Path,
                    default=here / "tools" / "Dockerfile")

    ca = sub.add_parser("cache", help="inspect or clear the grade cache")
    ca.add_argument("--grade-cache", type=Path,
                    default=here / ".cache" / "grade-cache.json")
    ca.add_argument("--clear", action="store_true", help="delete the cache")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return {
        "check": cmd_check, "run": cmd_run, "compare": cmd_compare,
        "corpus": cmd_corpus, "footprint": cmd_footprint, "cache": cmd_cache,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
