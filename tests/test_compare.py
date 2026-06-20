"""Compare/regression logic: seeded size regression gates (nonzero exit),
speed regression stays informational, version drift is detected."""

import json
import tempfile
import unittest
from pathlib import Path

from bench.compare import compare_runs, detect_version_drift, index_metrics


def write_run(root: Path, name: str, *, bytes80, median_ms, bytes90=2000,
              versions=None):
    d = root / name
    d.mkdir(parents=True)
    summary = {
        "targets": [80.0, 90.0],
        "primary_grader": "ssimulacra2",
        "config": {},
        "results": [{
            "tool": "rimage", "image": "a.png", "format": "webp", "mode": "sweep",
            "targets": {"80.0": {"coarse": bytes80, "refined": bytes80},
                        "90.0": {"coarse": bytes90, "refined": bytes90}},
            "bd_rate_vs": {}, "median_ms": median_ms,
        }],
    }
    (d / "summary.json").write_text(json.dumps(summary))
    manifest = {
        "schema": 2,
        "tools": {"rimage": {"version": (versions or {}).get("rimage", "rimage 0.11.0")}},
        "graders": {"ssimulacra2": {"version": "ssimulacra2 2.1"}},
        "primary_grader": "ssimulacra2",
    }
    (d / "manifest.json").write_text(json.dumps(manifest))
    return d


class TestCompare(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_no_change_passes(self):
        a = write_run(self.root, "A", bytes80=1000, median_ms=10.0)
        b = write_run(self.root, "B", bytes80=1000, median_ms=10.0)
        cmp = compare_runs(a, b)
        self.assertFalse(cmp.gated())
        self.assertEqual(len(cmp.size_regressions), 0)

    def test_size_regression_gates(self):
        a = write_run(self.root, "A", bytes80=1000, median_ms=10.0)
        # candidate is 10% larger at the target -> gate-worthy (>2% tol)
        b = write_run(self.root, "B", bytes80=1100, median_ms=10.0)
        cmp = compare_runs(a, b, size_tol=0.02)
        self.assertTrue(cmp.gated())
        self.assertEqual(len(cmp.size_regressions), 1)
        self.assertEqual(cmp.size_regressions[0].metric, "bytes@80")

    def test_improvement_does_not_gate(self):
        a = write_run(self.root, "A", bytes80=1000, median_ms=10.0)
        b = write_run(self.root, "B", bytes80=900, median_ms=10.0)  # smaller = good
        cmp = compare_runs(a, b)
        self.assertFalse(cmp.gated())

    def test_speed_regression_informational_by_default(self):
        a = write_run(self.root, "A", bytes80=1000, median_ms=10.0)
        b = write_run(self.root, "B", bytes80=1000, median_ms=20.0)  # 2x slower
        cmp = compare_runs(a, b)
        self.assertEqual(len(cmp.speed_regressions), 1)
        self.assertFalse(cmp.gated())  # speed not gated by default

    def test_speed_regression_gates_when_requested(self):
        a = write_run(self.root, "A", bytes80=1000, median_ms=10.0)
        b = write_run(self.root, "B", bytes80=1000, median_ms=20.0)
        cmp = compare_runs(a, b, gate_speed=True)
        self.assertTrue(cmp.gated())

    def test_version_drift_detected(self):
        a = write_run(self.root, "A", bytes80=1000, median_ms=10.0)
        b = write_run(self.root, "B", bytes80=1000, median_ms=10.0,
                      versions={"rimage": "rimage 0.12.0"})
        cmp = compare_runs(a, b)
        self.assertTrue(cmp.version_drift)
        self.assertIn("rimage", cmp.version_drift[0])

    def test_index_metrics_shapes(self):
        a = write_run(self.root, "A", bytes80=1000, median_ms=10.0)
        summary = json.loads((a / "summary.json").read_text())
        idx = index_metrics(summary, [80.0, 90.0])
        self.assertEqual(idx[("rimage", "webp", "a.png", "bytes@80")], (1000, "size"))
        self.assertEqual(idx[("rimage", "webp", "a.png", "median_ms")], (10.0, "speed"))


if __name__ == "__main__":
    unittest.main()
