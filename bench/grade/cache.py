"""Persistent grade cache — memoize the (deterministic) grader.

WHAT IS CACHED: only the grader's score for a given
``(source content, output content, grader name + version)`` triple. NOT bytes
(stat'd fresh every run), NOT timing (measured fresh every run). A SSIMULACRA2
score is a pure deterministic function of two exact image byte-streams and the
grader binary, so this is plain memoization of a pure function — the cached
number is provably identical to recomputing it.

WHY IT CAN'T GO STALE: the key is sha256(source) + sha256(output) + grader
name/version + a cache-schema tag. Change one byte of either image, or the
grader, and the key changes -> miss -> recompute. You can never get a score that
belongs to different bytes. Keyed on CONTENT, not path.

CLEARING: never by time. Invalidated by key (content/grader change); LRU-pruned
when over ``max_entries``; wiped by ``--no-grade-cache``, ``bench cache --clear``
/ deleting the file, or a ``CACHE_SCHEMA`` bump.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from pathlib import Path

CACHE_SCHEMA = 1  # bump to invalidate every existing cache on load


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class GradeCache:
    """Content-addressed score cache, persisted to one JSON file."""

    def __init__(self, path: Path, *, max_entries: int = 100_000):
        self.path = Path(path)
        self.max_entries = max_entries
        self._entries: "OrderedDict[str, float]" = OrderedDict()
        self._src_sha: dict[str, str] = {}  # per-process source-hash memo
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.dirty = False

    # -- persistence --------------------------------------------------------
    def load(self) -> "GradeCache":
        try:
            blob = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return self
        if blob.get("schema") != CACHE_SCHEMA:
            return self  # incompatible -> start empty (old entries ignored)
        entries = blob.get("entries", {})
        self._entries = OrderedDict(entries.items())
        return self

    def save(self) -> None:
        if not self.dirty:
            return
        with self._lock:
            # LRU prune to the cap before writing.
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
            payload = {"schema": CACHE_SCHEMA, "entries": dict(self._entries)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload))
        tmp.replace(self.path)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self.dirty = True
        if self.path.exists():
            self.path.unlink()

    # -- keying -------------------------------------------------------------
    def _source_sha(self, orig: Path) -> str:
        key = str(Path(orig).resolve())
        sha = self._src_sha.get(key)
        if sha is None:
            sha = _sha256(orig)
            self._src_sha[key] = sha
        return sha

    def make_key(self, grader_name: str, grader_version: str | None,
                 orig: Path, dist: Path) -> str:
        return "|".join((
            str(CACHE_SCHEMA), grader_name, grader_version or "?",
            self._source_sha(orig), _sha256(dist),
        ))

    # -- the memoized call --------------------------------------------------
    def get_or_compute(self, grader, orig: Path, dist: Path):
        key = self.make_key(grader.name, grader.version(), orig, dist)
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
                self.hits += 1
                return self._entries[key]
        score = grader.score(orig, dist)  # the actual subprocess, outside lock
        if score is not None:
            with self._lock:
                self._entries[key] = score
                self._entries.move_to_end(key)
                self.misses += 1
                self.dirty = True
        return score

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "hits": self.hits, "misses": self.misses,
            "entries": len(self._entries),
            "hit_rate": round(self.hits / total, 3) if total else None,
            "path": str(self.path),
        }


class CachingGrader:
    """Wraps a Grader so ``score`` is served from ``cache``. Delegates identity
    (name/version/availability) so the rest of the harness can't tell."""

    def __init__(self, inner, cache: GradeCache):
        self.inner = inner
        self.cache = cache

    name = property(lambda self: self.inner.name)
    higher_is_better = property(lambda self: self.inner.higher_is_better)
    identical_score = property(lambda self: self.inner.identical_score)

    def available(self):
        return self.inner.available()

    def resolved_binary(self):
        return self.inner.resolved_binary()

    def version(self):
        return self.inner.version()

    def score(self, orig: Path, dist: Path):
        return self.cache.get_or_compute(self.inner, orig, dist)
