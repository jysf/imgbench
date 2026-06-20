"""bench — an equal-SSIMULACRA2 image-optimization benchmark harness.

The non-negotiable principle: every size/speed claim is gated on EQUAL
perceptual quality (SSIMULACRA2), never on an equal quality-number. See
``benchmark-methodology.md`` for the full fairness protocol.

The core is Python standard library only so it runs in CI without a venv.
Optional extras (plotting) live behind ``requirements-optional.txt``.
"""

__version__ = "0.1.0"

# A short, stable schema version stamped into every run manifest so that
# ``compare`` can refuse to diff runs written by incompatible harnesses.
MANIFEST_SCHEMA = 2
