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

    def test_read_png_roundtrip_rgb(self):
        px = imageio.gradient_rgba(9, 7)
        # build an RGB buffer from the gradient
        rgb = bytes(b for i, b in enumerate(px) if i % 4 != 3)
        p = self.tmp / "rt.png"
        imageio.write_png(p, 9, 7, rgb, alpha=False)
        w, h, ch, out = imageio.read_png(p)
        self.assertEqual((w, h, ch), (9, 7, 3))
        self.assertEqual(out, rgb)            # exact pixel round-trip

    def test_read_png_roundtrip_rgba(self):
        px = imageio.gradient_rgba(8, 8)
        p = self.tmp / "rta.png"
        imageio.write_png(p, 8, 8, px, alpha=True)
        w, h, ch, out = imageio.read_png(p)
        self.assertEqual((w, h, ch), (8, 8, 4))
        self.assertEqual(out, px)

    def test_strip_ancillary_png(self):
        import struct, zlib
        p = self.tmp / "c.png"
        imageio.write_png(p, 4, 4, imageio.solid_rgb(4, 4), alpha=False)
        # Inject a bogus ancillary cICP chunk right after IHDR (ends at byte 33).
        body = b"\x09\x10\x00\x00"
        chunk = (struct.pack(">I", len(body)) + b"cICP" + body
                 + struct.pack(">I", zlib.crc32(b"cICP" + body) & 0xFFFFFFFF))
        data = bytearray(p.read_bytes())
        data[33:33] = chunk
        p.write_bytes(bytes(data))
        self.assertIn(b"cICP", p.read_bytes())
        self.assertTrue(imageio.strip_ancillary_png(p))
        self.assertNotIn(b"cICP", p.read_bytes())          # chunk removed
        w, h, ch, _ = imageio.read_png(p)                  # pixels still intact
        self.assertEqual((w, h, ch), (4, 4, 3))

    def test_flatten_opaque_alpha_preserves_rgb(self):
        # fully-opaque RGBA -> dropping alpha must equal the RGB channels
        w = h = 5
        rgba = bytearray()
        for i in range(w * h):
            rgba += bytes((i % 256, (2 * i) % 256, (3 * i) % 256, 255))
        rgb = imageio.flatten_to_rgb(w, h, 4, bytes(rgba))
        expected = bytes(b for i, b in enumerate(rgba) if i % 4 != 3)
        self.assertEqual(rgb, expected)


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
