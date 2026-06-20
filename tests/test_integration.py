"""End-to-end orchestration without external encoders.

A self-contained fake encoder (a python one-liner that writes a real PNG whose
size grows with quality) and a fake grader (score grows with quality) exercise
the full path: sweep_image -> _encode_point -> measure -> validate -> report ->
compare. This proves run-dir artifacts are produced and the regression gate
fires, on any machine, with zero tools installed.
"""

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from bench import imageio, report
from bench.adapters.base import Adapter, EncodeConfig
from bench.compare import compare_runs
from bench.sweep import sweep_image

# A tiny program that writes a valid PNG matching the source's dimensions, then
# appends (a) a recoverable quality marker the grader reads to derive the score,
# and (b) padding whose size scales with q * the encoder's efficiency factor.
# This mimics reality: two encoders at the same quality earn the SAME perceptual
# score but emit DIFFERENT bytes. Trailing bytes after IEND are ignored by probe.
ENCODER = textwrap.dedent("""
    import sys
    from pathlib import Path
    sys.path.insert(0, %r)
    from bench import imageio
    inp, outp, q, scale = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
    info = imageio.probe(Path(inp))
    px = imageio.solid_rgb(info.width, info.height, (q %% 256, q %% 256, q %% 256))
    imageio.write_png(Path(outp), info.width, info.height, px, alpha=info.has_alpha)
    pad = int(q * scale)
    with open(outp, "ab") as f:
        f.write(b"Q%%d;" %% q + b"\\0" * pad)
""")


class FakeAdapter(Adapter):
    def __init__(self, name, scale):
        self.name = name
        self.binary = sys.executable
        self.formats = ("png",)
        self.scale = scale

    def available(self):
        return True

    def quality_range(self, fmt):
        return [40, 55, 70, 85, 95]

    def cmd(self, inp, outp, fmt, q, cfg: EncodeConfig):
        repo = str(Path(__file__).resolve().parent.parent)
        return [sys.executable, "-c", ENCODER % repo,
                str(inp), str(outp), str(q), str(self.scale)]


class FakeGrader:
    name = "fake"
    higher_is_better = True
    identical_score = 100.0

    def score(self, orig, dist):
        # Recover the encoded quality marker; score depends on q alone (NOT on
        # bytes), so two encoders at the same q score identically — the fair
        # footing the whole benchmark is built on. Tuned to bracket 80 and 90.
        import re
        m = re.search(rb"Q(\d+);", Path(dist).read_bytes())
        q = int(m.group(1)) if m else 40
        return min(99.0, 59.0 + q * 0.5)


def do_run(root: Path, scale: float, img: Path) -> Path:
    run_dir = root
    run_dir.mkdir(parents=True, exist_ok=True)
    adapter = FakeAdapter("rimage", scale)
    cfg = EncodeConfig(threads=1)
    res = sweep_image(adapter, img, "png", FakeGrader(), cfg,
                      targets=[80.0, 90.0], best_of=1, warmup=0,
                      refine_iters=2, workdir=run_dir / "_enc")
    summary = report.build_summary([res], targets=[80.0, 90.0],
                                   primary_grader="fake", config={"threads": 1})
    report.write_summary(run_dir / "summary.json", summary)
    report.write_sweep_csv(run_dir / "sweep.csv", [res])
    report.write_manifest(run_dir / "manifest.json",
                          {"schema": 2, "tools": {"rimage": {"version": "fake-1"}},
                           "graders": {}, "primary_grader": "fake"})
    return run_dir


class TestPerformancePaths(unittest.TestCase):
    """Parallel grading must not change results; fast mode trades timing only."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.img = self.tmp / "src.png"
        imageio.write_png(self.img, 24, 24, imageio.solid_rgb(24, 24), alpha=False)

    def _sweep(self, **kw):
        return sweep_image(FakeAdapter("rimage", 10.0), self.img, "png",
                           FakeGrader(), EncodeConfig(threads=1),
                           targets=[80.0, 90.0], best_of=1, warmup=0,
                           refine_iters=2, workdir=self.tmp / kw.pop("wd"), **kw)

    def test_parallel_grading_matches_serial(self):
        serial = self._sweep(wd="serial", grade_jobs=1)
        par = self._sweep(wd="par", grade_jobs=4)
        s = {(p.quality, p.bytes, round(p.score, 4)) for p in serial.coarse}
        p = {(p.quality, p.bytes, round(p.score, 4)) for p in par.coarse}
        self.assertEqual(s, p)               # identical curve regardless of jobs

    def test_fast_mode_records_no_timing_but_real_curve(self):
        res = self._sweep(wd="fast", timed=False, grade_jobs=1)
        self.assertTrue(res.coarse)
        for pt in res.coarse:
            self.assertIsNone(pt.timing)      # fast mode: timing not recorded
            self.assertIsNotNone(pt.score)    # but bytes+score are real
            self.assertGreater(pt.bytes, 0)
        # bytes-at-target still interpolates to an integer
        self.assertIsInstance(res.targets["80.0"]["coarse"], int)


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.img = self.tmp / "src.png"
        imageio.write_png(self.img, 24, 24, imageio.solid_rgb(24, 24), alpha=False)

    def test_run_produces_artifacts_and_curve(self):
        run = do_run(self.tmp / "A", scale=10.0, img=self.img)
        for f in ("summary.json", "sweep.csv", "manifest.json"):
            self.assertTrue((run / f).exists(), f"missing {f}")
        summary = json.loads((run / "summary.json").read_text())
        result = summary["results"][0]
        # bytes-at-target should be interpolated to a real integer
        b80 = result["targets"]["80.0"]
        self.assertIsNotNone(b80["coarse"])
        # sweep.csv has a header + one row per point
        rows = (run / "sweep.csv").read_text().strip().splitlines()
        self.assertGreater(len(rows), 5)
        self.assertTrue(rows[0].startswith("tool,format,image,quality,bytes"))

    def test_compare_detects_seeded_regression(self):
        a = do_run(self.tmp / "A", scale=10.0, img=self.img)
        # scale 13 -> every file ~30% larger -> a clear size regression
        b = do_run(self.tmp / "B", scale=13.0, img=self.img)
        cmp = compare_runs(a, b, size_tol=0.02)
        self.assertTrue(cmp.gated(), "expected the seeded size regression to gate")
        self.assertTrue(any(d.metric.startswith("bytes@") for d in cmp.size_regressions))

    def test_compare_clean_when_identical(self):
        a = do_run(self.tmp / "A", scale=10.0, img=self.img)
        b = do_run(self.tmp / "B", scale=10.0, img=self.img)
        cmp = compare_runs(a, b, size_tol=0.02)
        self.assertFalse(cmp.gated())


if __name__ == "__main__":
    unittest.main()
