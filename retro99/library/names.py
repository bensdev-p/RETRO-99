"""Title normalization for No-Intro/Redump style file names, and id slugs."""

from __future__ import annotations

import re
from dataclasses import dataclass

REGIONS = {
    "usa", "europe", "japan", "world", "asia", "australia", "brazil", "canada", "china",
    "france", "germany", "hong kong", "italy", "korea", "netherlands", "spain", "sweden",
    "taiwan", "uk", "en", "us", "eu", "jp",
}  # fmt: skip

_TAG = re.compile(r"\s*(\([^)]*\)|\[[^\]]*\])")
_DISC = re.compile(r"\((?:disc|disk|cd)\s*(\d+)(?:\s*of\s*\d+)?\)", re.IGNORECASE)
_TRAILING_ARTICLE = re.compile(r"^(.*), (The|A|An)(\s*-.*|:.*)?$")
_SLUG = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class ParsedName:
    title: str
    region: str = ""
    disc: int | None = None


def parse_name(stem: str) -> ParsedName:
    """``"Legend of Foo, The (USA) (Disc 2) [!]"`` -> title/region/disc."""
    disc_match = _DISC.search(stem)
    disc = int(disc_match.group(1)) if disc_match else None
    regions: list[str] = []
    for tag in _TAG.findall(stem):
        inner = tag.strip()[1:-1]
        if tag.strip().startswith("("):
            parts = [p.strip() for p in inner.split(",")]
            if parts and all(p.lower() in REGIONS for p in parts):
                regions.extend(parts)
    title = _TAG.sub("", stem).replace("_", " ").strip()
    title = re.sub(r"\s{2,}", " ", title)
    m = _TRAILING_ARTICLE.match(title)
    if m:
        title = f"{m.group(2)} {m.group(1)}{m.group(3) or ''}"
    return ParsedName(title or stem, ", ".join(regions), disc)


def normalize_title(stem: str) -> str:
    return parse_name(stem).title


def sort_key(title: str) -> str:
    """Case-insensitive, ignoring a leading article: "The Lion King" sorts under L."""
    t = title.lower().strip()
    for article in ("the ", "a ", "an "):
        if t.startswith(article):
            return t[len(article) :]
    return t


def slugify(text: str) -> str:
    return _SLUG.sub("-", text.lower()).strip("-") or "game"
