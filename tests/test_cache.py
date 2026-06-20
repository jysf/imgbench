"""Grade-cache integrity: it memoizes a deterministic grader keyed on CONTENT +
grader version, never returns a score for different bytes, and persists across
processes. These tests are the proof that "caching results" is safe here."""

import tempfile
import unittest
from pathlib import Path

from bench import imageio
from bench.grade.cache import CachingGrader, GradeCache


class CountingGrader:
    """Stand-in grader: score = output file size; counts real computations."""
    name = "count"
    higher_is_better = True
    identical_score = 100.0

    def __init__(self, version="v1"):
        self._v = version
        self.calls = 0

    def version(self):
        return self._v

    def available(self):
        return True

    def resolved_binary(self):
        return "count"

    def score(self, orig, dist):
        self.calls += 1
        return float(Path(dist).stat().st_size)


class TestGradeCache(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / "src.png"
        imageio.write_png(self.src, 8, 8, imageio.solid_rgb(8, 8), alpha=False)
        self.dist = self.tmp / "out.bin"
        self.dist.write_bytes(b"A" * 100)
        self.cache_path = self.tmp / "cache.json"

    def test_hit_after_miss(self):
        cache = GradeCache(self.cache_path)
        g = CountingGrader()
        s1 = cache.get_or_compute(g, self.src, self.dist)
        s2 = cache.get_or_compute(g, self.src, self.dist)
        self.assertEqual(s1, s2)
        self.assertEqual(g.calls, 1)          # second call served from cache
        self.assertEqual(cache.hits, 1)
        self.assertEqual(cache.misses, 1)

    def test_content_change_invalidates(self):
        cache = GradeCache(self.cache_path)
        g = CountingGrader()
        cache.get_or_compute(g, self.src, self.dist)
        # different output bytes -> different sha -> miss -> recompute
        self.dist.write_bytes(b"B" * 250)
        s2 = cache.get_or_compute(g, self.src, self.dist)
        self.assertEqual(g.calls, 2)
        self.assertEqual(s2, 250.0)           # the NEW bytes' score, not stale

    def test_grader_version_invalidates(self):
        cache = GradeCache(self.cache_path)
        g1 = CountingGrader(version="2.0")
        g2 = CountingGrader(version="2.1")   # weights retuned -> must recompute
        cache.get_or_compute(g1, self.src, self.dist)
        cache.get_or_compute(g2, self.src, self.dist)
        self.assertEqual(g1.calls, 1)
        self.assertEqual(g2.calls, 1)        # not served from g1's entry

    def test_persistence_across_processes(self):
        c1 = GradeCache(self.cache_path)
        g = CountingGrader()
        c1.get_or_compute(g, self.src, self.dist)
        c1.save()
        # fresh cache object (simulates a new process) + fresh grader
        c2 = GradeCache(self.cache_path).load()
        g2 = CountingGrader()
        s = c2.get_or_compute(g2, self.src, self.dist)
        self.assertEqual(g2.calls, 0)        # served from disk, no recompute
        self.assertEqual(s, 100.0)

    def test_none_not_cached(self):
        class NoneGrader(CountingGrader):
            def score(self, orig, dist):
                self.calls += 1
                return None
        cache = GradeCache(self.cache_path)
        g = NoneGrader()
        cache.get_or_compute(g, self.src, self.dist)
        cache.get_or_compute(g, self.src, self.dist)
        self.assertEqual(g.calls, 2)         # None is never cached -> retried
        self.assertFalse(cache.dirty)

    def test_schema_bump_ignores_old_file(self):
        self.cache_path.write_text('{"schema": -999, "entries": {"k": 1.0}}')
        cache = GradeCache(self.cache_path).load()
        self.assertEqual(cache.stats()["entries"], 0)

    def test_clear(self):
        cache = GradeCache(self.cache_path)
        cache.get_or_compute(CountingGrader(), self.src, self.dist)
        cache.save()
        self.assertTrue(self.cache_path.exists())
        cache.clear()
        self.assertFalse(self.cache_path.exists())
        self.assertEqual(cache.stats()["entries"], 0)

    def test_caching_grader_delegates_identity(self):
        cache = GradeCache(self.cache_path)
        inner = CountingGrader(version="9.9")
        wrapped = CachingGrader(inner, cache)
        self.assertEqual(wrapped.name, "count")
        self.assertEqual(wrapped.version(), "9.9")
        self.assertTrue(wrapped.available())
        # score routes through the cache
        wrapped.score(self.src, self.dist)
        wrapped.score(self.src, self.dist)
        self.assertEqual(inner.calls, 1)


if __name__ == "__main__":
    unittest.main()
