#!/usr/bin/env python3
"""fetch_cc0.py — pull license-verified CC0 / public-domain images from Wikimedia
Commons for the benchmark photo slots.

For each slot it searches Commons, fetches each candidate's license metadata, and
accepts ONLY images whose license is CC0 or Public Domain — so the committed,
public corpus is unambiguous to redistribute. It downloads a 2048px-wide render
(not the multi-MB original) and records title/author/license/source for
CORPUS.md.

Stdlib only. Usage:  python3 corpus/fetch_cc0.py
Outputs to corpus/images/_dl/ plus _dl/manifest.json (review, then run the
prep step that strips metadata and moves files into the named slots).
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = "imgbench-corpus/0.1 (https://github.com/jysf/imgbench; benchmark test set)"
OUT = Path(__file__).resolve().parent / "images" / "_dl"

# slot -> ordered search terms (first CC0/PD match with a usable size wins)
SLOTS = {
    "photo_foliage":  ["fern fronds close up", "tree foliage leaves detail",
                       "spider web dew macro"],
    "photo_sky":      ["clear blue sky gradient", "sunset sky gradient",
                       "twilight sky gradient"],
    "photo_portrait": ["portrait man face", "portrait woman face",
                       "human portrait studio"],
    "photo_lowlight": ["city night lights skyline", "night street long exposure",
                       "low light night cityscape"],
}

CC0_PD = ("cc0", "pd", "cc-pd")


def _get(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _candidates(term: str, limit: int = 12) -> list[str]:
    d = _get({"action": "query", "list": "search", "srsearch": term,
              "srnamespace": 6, "srlimit": limit})
    return [r["title"] for r in d.get("query", {}).get("search", [])]


def _info(title: str) -> dict | None:
    d = _get({"action": "query", "titles": title, "prop": "imageinfo",
              "iiprop": "url|size|extmetadata|mime", "iiurlwidth": 2048})
    pages = d.get("query", {}).get("pages", {})
    for p in pages.values():
        ii = p.get("imageinfo")
        if ii:
            return ii[0]
    return None


def _is_cc0_pd(meta: dict) -> tuple[bool, str, str]:
    ext = meta.get("extmetadata", {})
    lic = (ext.get("License", {}).get("value") or "").lower()
    short = (ext.get("LicenseShortName", {}).get("value") or "")
    author = (ext.get("Artist", {}).get("value") or "").strip()
    # strip any HTML in the author field crudely
    import re
    author = re.sub(r"<[^>]+>", "", author).strip() or "unknown"
    ok = lic in CC0_PD or "cc0" in short.lower() or "public domain" in short.lower()
    return ok, short or lic or "?", author


def fetch_slot(slot: str, terms: list[str]) -> dict | None:
    for term in terms:
        for title in _candidates(term):
            if not title.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            meta = _info(title)
            if not meta:
                continue
            ok, lic, author = _is_cc0_pd(meta)
            w, h = meta.get("width", 0), meta.get("height", 0)
            if not ok or w < 1800 or w > 8000:
                continue
            thumb = meta.get("thumburl") or meta.get("url")
            ext = ".png" if thumb.lower().split("?")[0].endswith(".png") else ".jpg"
            dest = OUT / f"{slot}{ext}"
            req = urllib.request.Request(thumb, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                dest.write_bytes(r.read())
            rec = {"slot": slot, "title": title, "license": lic, "author": author,
                   "source": meta.get("descriptionurl") or meta.get("url"),
                   "downloaded": str(dest.name), "width": w, "height": h,
                   "term": term}
            print(f"  {slot:16s} <- {title}")
            print(f"    license={lic} · author={author[:50]} · {w}x{h}")
            return rec
    print(f"  {slot:16s} -- no CC0/PD match found")
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for slot, terms in SLOTS.items():
        rec = fetch_slot(slot, terms)
        if rec:
            manifest.append(rec)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nWrote {len(manifest)} image(s) + {OUT/'manifest.json'}")
    print("Next: prep into slots (strip metadata, inject synthetic EXIF) — see "
          "prepare_public_corpus.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
