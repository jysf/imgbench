"""Minimal, dependency-free image I/O.

Two jobs, both stdlib-only so the core never needs Pillow/numpy:

1. ``write_png`` — emit a tiny valid PNG (RGB or RGBA). Used by the test suite
   to synthesise corpus images so unit tests need no external encoders.
2. ``probe`` — read width/height and alpha-presence back out of an encoded
   file by parsing container headers. Used by the output-validity checks
   (a tool that silently drops alpha or resizes must not score a bytes "win").

Supported probe formats: PNG, JPEG, WebP, AVIF/HEIF (ISO-BMFF ``ispe``), GIF.
Dimensions are exact for all of them. Alpha is exact for PNG/WebP/GIF, parsed
best-effort for AVIF (auxiliary alpha track), and always False for JPEG.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class ImageInfo:
    width: int
    height: int
    has_alpha: bool
    format: str


# ---------------------------------------------------------------------------
# Writing (test-fixture support)
# ---------------------------------------------------------------------------
def write_png(path: Path, width: int, height: int, pixels: bytes, *, alpha: bool) -> None:
    """Write an 8-bit PNG. ``pixels`` is raw RGB (3 B/px) or RGBA (4 B/px),
    row-major, top-to-bottom, with no per-row filter byte (we add them)."""
    channels = 4 if alpha else 3
    color_type = 6 if alpha else 2  # 6 = RGBA, 2 = RGB
    stride = width * channels
    if len(pixels) != stride * height:
        raise ValueError(f"pixel buffer {len(pixels)} != {stride*height} expected")

    # Prepend the mandatory per-scanline filter byte (0 = None).
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(pixels[y * stride:(y + 1) * stride])

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    out = bytearray(PNG_SIG)
    out += chunk(b"IHDR", ihdr)
    out += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    out += chunk(b"IEND", b"")
    path.write_bytes(bytes(out))


def solid_rgb(width: int, height: int, rgb=(127, 127, 127)) -> bytes:
    return bytes(rgb) * (width * height)


# Color-type -> channel count for 8-bit PNG (the cases we read/write).
_CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}


def read_png(path: Path) -> tuple[int, int, int, bytes]:
    """Decode an 8-bit, non-interlaced PNG. Returns (width, height, channels,
    pixels) where pixels is raw row-major samples (no per-row filter byte).
    Supports color types 0/2/4/6 at bit depth 8 — enough for our corpus prep
    and tests; raises ValueError otherwise (palette/16-bit/interlaced)."""
    data = Path(path).read_bytes()
    if data[:8] != PNG_SIG:
        raise ValueError("not a PNG")
    w, h, depth, color_type, _comp, _filt, interlace = struct.unpack(
        ">IIBBBBB", data[16:29])
    if depth != 8 or interlace != 0 or color_type not in _CHANNELS:
        raise ValueError(f"unsupported PNG (depth={depth}, type={color_type}, "
                         f"interlace={interlace}); only 8-bit non-interlaced "
                         f"gray/RGB/+alpha")
    ch = _CHANNELS[color_type]

    # Concatenate IDAT chunk bodies, then inflate.
    idat = bytearray()
    i = 8
    while i + 8 <= len(data):
        length = struct.unpack(">I", data[i:i + 4])[0]
        tag = data[i + 4:i + 8]
        body = data[i + 8:i + 8 + length]
        if tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break
        i += 12 + length
    raw = zlib.decompress(bytes(idat))

    stride = w * ch
    out = bytearray(stride * h)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        _unfilter(line, prev, ftype, ch)
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return w, h, ch, bytes(out)


def _unfilter(line: bytearray, prev: bytearray, ftype: int, bpp: int) -> None:
    """Reverse a PNG scanline filter in place (0=None,1=Sub,2=Up,3=Avg,4=Paeth)."""
    if ftype == 0:
        return
    for x in range(len(line)):
        a = line[x - bpp] if x >= bpp else 0
        b = prev[x]
        c = prev[x - bpp] if x >= bpp else 0
        if ftype == 1:
            v = a
        elif ftype == 2:
            v = b
        elif ftype == 3:
            v = (a + b) >> 1
        elif ftype == 4:
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            v = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
        else:
            raise ValueError(f"bad PNG filter {ftype}")
        line[x] = (line[x] + v) & 0xFF


def flatten_to_rgb(width: int, height: int, channels: int, pixels: bytes,
                   bg=(255, 255, 255)) -> bytes:
    """Composite any alpha over ``bg`` and return RGB (3 B/px). Gray is expanded
    to RGB. Opaque pixels are unchanged."""
    out = bytearray(width * height * 3)
    o = 0
    if channels == 3:
        return pixels
    for px in range(width * height):
        base = px * channels
        if channels == 4:
            r, g, b, a = pixels[base], pixels[base+1], pixels[base+2], pixels[base+3]
        elif channels == 2:  # gray + alpha
            r = g = b = pixels[base]; a = pixels[base+1]
        else:  # gray
            r = g = b = pixels[base]; a = 255
        if a != 255:
            r = (r * a + bg[0] * (255 - a)) // 255
            g = (g * a + bg[1] * (255 - a)) // 255
            b = (b * a + bg[2] * (255 - a)) // 255
        out[o] = r; out[o+1] = g; out[o+2] = b; o += 3
    return bytes(out)


def gradient_rgba(width: int, height: int) -> bytes:
    """A smooth gradient with a varying alpha ramp — useful for alpha tests."""
    buf = bytearray()
    for y in range(height):
        for x in range(width):
            buf += bytes((
                (x * 255) // max(width - 1, 1),
                (y * 255) // max(height - 1, 1),
                128,
                (x * 255) // max(width - 1, 1),
            ))
    return bytes(buf)


# ---------------------------------------------------------------------------
# Probing (output-validity support)
# ---------------------------------------------------------------------------
def probe(path: Path) -> ImageInfo:
    """Return ImageInfo for an encoded file. Raises ValueError if unrecognised."""
    data = Path(path).read_bytes()
    if data[:8] == PNG_SIG:
        return _probe_png(data)
    if data[:3] == b"\xff\xd8\xff":
        return _probe_jpeg(data)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return _probe_webp(data)
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return _probe_gif(data)
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return _probe_isobmff(data)
    raise ValueError(f"unrecognised image format: {path}")


def _probe_png(data: bytes) -> ImageInfo:
    # IHDR is always the first chunk, at a fixed offset.
    w, h, _depth, color_type = struct.unpack(">IIBB", data[16:26])
    # color types with alpha: 4 (gray+alpha), 6 (RGBA). tRNS adds keyed
    # transparency to types 0/2/3 — count that as alpha too.
    has_alpha = color_type in (4, 6) or (b"tRNS" in data)
    return ImageInfo(w, h, has_alpha, "png")


def _probe_jpeg(data: bytes) -> ImageInfo:
    i = 2
    n = len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        # SOF0..SOF15 except DHT(C4)/JPG(C8)/DAC(CC) carry frame dimensions.
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return ImageInfo(w, h, False, "jpeg")
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + seg_len
    raise ValueError("no SOF marker in JPEG")


def _probe_webp(data: bytes) -> ImageInfo:
    fourcc = data[12:16]
    if fourcc == b"VP8X":
        flags = data[20]
        has_alpha = bool(flags & 0x10)
        w = 1 + int.from_bytes(data[24:27], "little")
        h = 1 + int.from_bytes(data[27:30], "little")
        return ImageInfo(w, h, has_alpha, "webp")
    if fourcc == b"VP8 ":  # simple lossy: no alpha
        w = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        h = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return ImageInfo(w, h, False, "webp")
    if fourcc == b"VP8L":  # simple lossless: alpha in a header bit
        b = data[21:26]
        bits = int.from_bytes(b[1:5], "little")
        w = (bits & 0x3FFF) + 1
        h = ((bits >> 14) & 0x3FFF) + 1
        has_alpha = bool((bits >> 28) & 1)
        return ImageInfo(w, h, has_alpha, "webp")
    raise ValueError(f"unknown WebP chunk {fourcc!r}")


def _probe_gif(data: bytes) -> ImageInfo:
    w, h = struct.unpack("<HH", data[6:10])
    # GIF transparency is signalled per Graphic Control Extension; the presence
    # of any GCE with the transparent-colour flag set counts as alpha.
    has_alpha = b"\x21\xf9" in data
    return ImageInfo(w, h, has_alpha, "gif")


def _probe_isobmff(data: bytes) -> ImageInfo:
    """Parse AVIF/HEIF just enough to read ``ispe`` (size) and detect an
    ``auxC`` alpha aux item. Walks the box tree iteratively."""
    width = height = 0
    has_alpha = False

    def walk(buf: bytes, start: int, end: int, depth: int) -> None:
        nonlocal width, height, has_alpha
        i = start
        while i + 8 <= end:
            size = struct.unpack(">I", buf[i:i + 4])[0]
            box_type = buf[i + 4:i + 8]
            header = 8
            if size == 1:  # 64-bit extended size
                size = struct.unpack(">Q", buf[i + 8:i + 16])[0]
                header = 16
            if size == 0:
                size = end - i
            box_end = min(i + size, end)
            body = i + header

            if box_type == b"ispe":
                w, h = struct.unpack(">II", buf[body + 4:body + 12])
                # The primary image is the largest ispe we see.
                if w * h >= width * height:
                    width, height = w, h
            elif box_type == b"auxC":
                # Alpha aux images declare an alpha URN.
                if b"alpha" in buf[body:box_end]:
                    has_alpha = True
            elif box_type in (b"meta", b"iprp", b"ipco", b"moov", b"trak",
                              b"mdia", b"minf", b"stbl"):
                inner = body + (4 if box_type == b"meta" else 0)  # meta is a FullBox
                walk(buf, inner, box_end, depth + 1)
            i = box_end if size else end

    walk(data, 0, len(data), 0)
    if not (width and height):
        raise ValueError("no ispe box found in ISO-BMFF image")
    fmt = "avif" if b"avif" in data[8:24] or b"av01" in data else "heif"
    return ImageInfo(width, height, has_alpha, fmt)
