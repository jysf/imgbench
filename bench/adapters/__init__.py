"""Adapter registry. ``writes_to_dir`` defaults to False on the base class; the
sweep runner consults it to normalise dir-writing tools' output to one path."""

from __future__ import annotations

from .base import Adapter, EncodeConfig
from .avifenc import Avifenc
from .crustyimg import CrustyImg
from .cwebp import Cwebp
from .oxipng import Oxipng, Pngquant
from .rimage import Rimage
from .sharp import SharpCli, SharpPng

ADAPTERS: list[Adapter] = [
    Rimage(), SharpCli(), Cwebp(), Avifenc(),
    Oxipng(), SharpPng(), Pngquant(), CrustyImg(),
]


def all_adapters() -> list[Adapter]:
    return list(ADAPTERS)


def by_name(name: str) -> Adapter | None:
    for a in ADAPTERS:
        if a.name == name:
            return a
    return None


__all__ = [
    "Adapter", "EncodeConfig", "ADAPTERS", "all_adapters", "by_name",
    "Rimage", "SharpCli", "SharpPng", "Cwebp", "Avifenc", "Oxipng",
    "Pngquant", "CrustyImg",
]
