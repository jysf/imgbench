"""Stdlib PNG writer + probe round-trip, and output-validity checks. These let
the rest of the suite synthesise corpus images with no external tools."""

import tempfile
import unittest
from pathlib import Path

from bench import imageio
from bench.validate import check_output


class TestPngRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_rgb_dimensions(self):
        p = self.tmp / "rgb.png"
        imageio.write_png(p, 7, 5, imageio.solid_rgb(7, 5), alpha=False)
        info = imageio.probe(p)
        self.assertEqual((info.width, info.height), (7, 5))
        self.assertFalse(info.has_alpha)
        self.assertEqual(info.format, "png")

    def test_rgba_alpha_detected(self):
        p = self.tmp / "rgba.png"
        imageio.write_png(p, 8, 8, imageio.gradient_rgba(8, 8), alpha=True)
        info = imageio.probe(p)
        self.assertEqual((info.width, info.height), (8, 8))
        self.assertTrue(info.has_alpha)

    def test_bad_buffer_size_rejected(self):
        with self.assertRaises(ValueError):
            imageio.write_png(self.tmp / "x.png", 4, 4, b"\x00\x01", alpha=False)


class TestValidity(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_preserved_dims_and_alpha_ok(self):
        src = self.tmp / "src.png"
        out = self.tmp / "out.png"
        imageio.write_png(src, 6, 6, imageio.gradient_rgba(6, 6), alpha=True)
        imageio.write_png(out, 6, 6, imageio.gradient_rgba(6, 6), alpha=True)
        v = check_output(src, out)
        self.assertTrue(v.ok)
        self.assertTrue(v.dims_preserved)
        self.assertTrue(v.alpha_preserved)

    def test_dropped_alpha_fails(self):
        src = self.tmp / "src.png"
        out = self.tmp / "out.png"
        imageio.write_png(src, 6, 6, imageio.gradient_rgba(6, 6), alpha=True)
        imageio.write_png(out, 6, 6, imageio.solid_rgb(6, 6), alpha=False)
        v = check_output(src, out)
        self.assertFalse(v.ok)
        self.assertFalse(v.alpha_preserved)

    def test_resized_output_fails(self):
        src = self.tmp / "src.png"
        out = self.tmp / "out.png"
        imageio.write_png(src, 10, 10, imageio.solid_rgb(10, 10), alpha=False)
        imageio.write_png(out, 5, 5, imageio.solid_rgb(5, 5), alpha=False)
        v = check_output(src, out)
        self.assertFalse(v.ok)
        self.assertFalse(v.dims_preserved)


if __name__ == "__main__":
    unittest.main()
