"""Manifest capture: machine probe shape, corpus hashing determinism, and the
crustyimg build-feature gate."""

import tempfile
import unittest
from pathlib import Path

from bench import grade, provenance
from bench.adapters import all_adapters
from bench.adapters.crustyimg import CrustyImg
from bench import imageio


class TestProvenance(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.imgs = []
        for i in range(3):
            p = self.tmp / f"img{i}.png"
            imageio.write_png(p, 4, 4, imageio.solid_rgb(4, 4, (i, i, i)), alpha=False)
            self.imgs.append(p)

    def test_machine_has_required_keys(self):
        m = provenance.machine()
        for key in ("cpu_model", "cores", "ram_bytes", "os", "kernel", "scaling"):
            self.assertIn(key, m)
        self.assertIn("logical", m["cores"])

    def test_corpus_hash_is_deterministic_and_order_independent(self):
        h1 = provenance.corpus_hashes(self.imgs)
        h2 = provenance.corpus_hashes(list(reversed(self.imgs)))
        self.assertEqual(h1["aggregate_sha256"], h2["aggregate_sha256"])
        self.assertEqual(h1["count"], 3)
        for img in self.imgs:
            self.assertIn(img.name, h1["per_image"])

    def test_hash_changes_when_pixels_change(self):
        h1 = provenance.corpus_hashes(self.imgs)
        imageio.write_png(self.imgs[0], 4, 4,
                          imageio.solid_rgb(4, 4, (200, 0, 0)), alpha=False)
        h2 = provenance.corpus_hashes(self.imgs)
        self.assertNotEqual(h1["aggregate_sha256"], h2["aggregate_sha256"])

    def test_build_manifest_shape(self):
        man = provenance.build_manifest(
            bench_sha="abc1234", images=self.imgs, adapters=all_adapters(),
            graders=grade.all_graders(), primary_grader=grade.default_grader(),
            config={"targets": [80, 90]})
        self.assertEqual(man["bench_git_sha"], "abc1234")
        self.assertIn("rimage", man["tools"])
        self.assertIn("ssimulacra2", man["graders"])
        self.assertEqual(man["corpus"]["count"], 3)
        self.assertIn("schema", man)


class TestCrustyFeatureGate(unittest.TestCase):
    def test_lossy_requires_features(self):
        c = CrustyImg()
        # simulate a lossless-only build by stubbing the reported features
        c.build_features = lambda: []
        ok, reason = c.feature_check(lossy=True)
        self.assertFalse(ok)
        self.assertIn("webp-lossy", reason)

    def test_features_present_passes(self):
        c = CrustyImg()
        c.build_features = lambda: ["webp-lossy", "avif"]
        ok, _ = c.feature_check(lossy=True)
        self.assertTrue(ok)

    def test_lossless_comparison_not_gated(self):
        c = CrustyImg()
        c.build_features = lambda: []
        ok, _ = c.feature_check(lossy=False)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
