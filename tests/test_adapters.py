"""Adapter wiring — command construction is pure, so it's testable with no
external encoders. Focus: the JPEG lane is wired correctly and adapters honour
the EncodeConfig fairness knobs."""

import unittest
from pathlib import Path

from bench.adapters import ADAPTERS, by_name, EncodeConfig
from bench.adapters.mozjpeg import Cjpeg


class TestJpegLane(unittest.TestCase):
    def setUp(self):
        self.cfg = EncodeConfig(threads=1, avif_effort=6, strip_metadata=True)
        self.inp = Path("/tmp/src.png")
        self.outp = Path("/tmp/work/out.jpeg")

    def test_jpeg_capable_tools(self):
        jpeg_tools = {a.name for a in ADAPTERS if "jpeg" in a.formats}
        # the JPEG lane: rimage (MozJPEG), sharp, and the dedicated cjpeg
        self.assertEqual(jpeg_tools, {"rimage", "sharp", "cjpeg"})

    def test_cjpeg_command_shape(self):
        cmd = Cjpeg().cmd(self.inp, self.outp, "jpeg", 80, self.cfg)
        self.assertEqual(cmd[0], "cjpeg")
        self.assertIn("-quality", cmd)
        self.assertIn("80", cmd)
        self.assertIn(str(self.outp), cmd)
        self.assertIn(str(self.inp), cmd)

    def test_rimage_maps_jpeg_to_mozjpeg_codec(self):
        cmd = by_name("rimage").cmd(self.inp, self.outp, "jpeg", 75, self.cfg)
        self.assertEqual(cmd[0], "rimage")
        self.assertEqual(cmd[1], "mozjpeg")          # JPEG codec subcommand
        self.assertIn("--quality", cmd)
        self.assertIn("-d", cmd)                     # rimage writes to a directory

    def test_sharp_emits_jpeg_format_flag(self):
        cmd = by_name("sharp").cmd(self.inp, self.outp, "jpeg", 75, self.cfg)
        self.assertIn("-f", cmd)
        self.assertEqual(cmd[cmd.index("-f") + 1], "jpeg")

    def test_jpeg_is_a_sweep_not_lossless(self):
        for name in ("rimage", "sharp", "cjpeg"):
            self.assertFalse(by_name(name).lossless,
                             f"{name} JPEG must sweep quality, not be lossless")


class TestFairnessKnobs(unittest.TestCase):
    def test_avif_effort_propagates(self):
        cfg = EncodeConfig(avif_effort=4)
        cmd = by_name("avifenc").cmd(Path("i"), Path("o.avif"), "avif", 80, cfg)
        # avifenc speed = 10 - effort
        self.assertIn("--speed", cmd)
        self.assertEqual(cmd[cmd.index("--speed") + 1], "6")

    def test_metadata_strip_toggle(self):
        on = by_name("cwebp").cmd(Path("i"), Path("o.webp"), "webp", 80,
                                  EncodeConfig(strip_metadata=True))
        off = by_name("cwebp").cmd(Path("i"), Path("o.webp"), "webp", 80,
                                   EncodeConfig(strip_metadata=False))
        self.assertIn("none", on)                    # -metadata none
        self.assertNotIn("none", off)


if __name__ == "__main__":
    unittest.main()
