"""Unit tests for the pure numeric core: interpolation, bracketing, bisection
refine, and BD-rate. No external encoders — synthetic points only."""

import unittest

from bench.sweep import (Point, bracket_for_target, interp_bytes_at_score,
                         bd_rate, _polyfit)
from bench.validate import Validity


def pt(score, byts, q=None, valid_ok=True):
    return Point(quality=q, bytes=byts, score=score,
                 valid=Validity(ok=valid_ok))


class TestInterpolation(unittest.TestCase):
    def test_exact_linear_interpolation(self):
        pts = [pt(70, 1000), pt(90, 2000)]
        # target 80 sits halfway in score -> halfway in bytes
        self.assertEqual(interp_bytes_at_score(pts, 80), 1500)

    def test_target_on_a_point(self):
        pts = [pt(70, 1000), pt(80, 1400), pt(90, 2000)]
        self.assertEqual(interp_bytes_at_score(pts, 80), 1400)

    def test_unbracketed_target_is_flagged_string(self):
        pts = [pt(70, 1000), pt(75, 1100)]
        out = interp_bytes_at_score(pts, 90)
        self.assertIsInstance(out, str)
        self.assertIn("extrapolated", out)

    def test_no_usable_points_returns_none(self):
        self.assertIsNone(interp_bytes_at_score([], 80))
        # points without a score are unusable
        self.assertIsNone(interp_bytes_at_score([Point(None, 100, None)], 80))

    def test_invalid_points_excluded(self):
        # the high-score point is invalid (e.g. alpha dropped) -> not bracketed
        pts = [pt(70, 1000), pt(95, 1500, valid_ok=False)]
        out = interp_bytes_at_score(pts, 90)
        self.assertIsInstance(out, str)  # falls back to extrapolation note

    def test_bracket_selection(self):
        pts = [pt(60, 500), pt(75, 900), pt(85, 1300), pt(95, 1800)]
        lo, hi = bracket_for_target(pts, 80)
        self.assertEqual((lo.score, hi.score), (75, 85))


class TestBisectionLogic(unittest.TestCase):
    """Drive the bisection the way sweep_image does, with a synthetic encoder
    whose bytes/score are deterministic functions of quality."""

    def fake_encode(self, q):
        # monotone: score rises with q, bytes rise with q
        score = 50 + q * 0.5          # q=60->80, q=80->90
        byts = int(500 + q * 20)
        return pt(score, byts, q=q)

    def test_bisection_converges_toward_target(self):
        # coarse points bracket target 85 between q=60 (score 80) and q=80 (90)
        coarse = [self.fake_encode(q) for q in (40, 60, 80, 95)]
        lo, hi = bracket_for_target(coarse, 85)
        self.assertIsNotNone(lo)
        self.assertIsNotNone(hi)
        q_lo, q_hi = lo.quality, hi.quality
        # mimic refine loop
        target = 85
        for _ in range(5):
            q_mid = (q_lo + q_hi) / 2
            if abs(q_hi - q_lo) <= 1:
                break
            p = self.fake_encode(q_mid)
            if p.score < target:
                q_lo = q_mid
            else:
                q_hi = q_mid
        # q for score 85 is 70; bracket should close around it
        self.assertLessEqual(q_lo, 70)
        self.assertGreaterEqual(q_hi, 70)


class TestBDRate(unittest.TestCase):
    def test_polyfit_recovers_line(self):
        xs = [1, 2, 3, 4]
        ys = [3, 5, 7, 9]  # y = 2x + 1
        c = _polyfit(xs, ys, 1)
        self.assertAlmostEqual(c[0], 1.0, places=6)
        self.assertAlmostEqual(c[1], 2.0, places=6)

    def test_identical_curves_zero_bdrate(self):
        curve = [pt(70, 1000), pt(80, 1500), pt(90, 2200), pt(95, 3000)]
        other = [pt(70, 1000), pt(80, 1500), pt(90, 2200), pt(95, 3000)]
        self.assertAlmostEqual(bd_rate(curve, other), 0.0, places=3)

    def test_smaller_files_negative_bdrate(self):
        anchor = [pt(70, 1000), pt(80, 1500), pt(90, 2200), pt(95, 3000)]
        # test uses ~30% fewer bytes at every quality -> negative BD-rate
        test = [pt(70, 700), pt(80, 1050), pt(90, 1540), pt(95, 2100)]
        val = bd_rate(anchor, test)
        self.assertLess(val, 0)
        self.assertAlmostEqual(val, -30.0, delta=2.0)

    def test_non_overlapping_returns_none(self):
        anchor = [pt(40, 500), pt(50, 700)]
        test = [pt(80, 1000), pt(90, 1500)]
        self.assertIsNone(bd_rate(anchor, test))


if __name__ == "__main__":
    unittest.main()
