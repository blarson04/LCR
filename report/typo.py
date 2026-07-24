"""
typo.py: shared typographic hygiene for the PDF deliverables
(practical-typography rules: curly quotes, real dashes, ellipses; applied
outside XML markup so reportlab inline tags survive).
"""

from __future__ import annotations

import re

_TAG = re.compile(r"(<[^>]+>)")


def _fix(seg: str) -> str:
    # ellipses
    seg = seg.replace("...", "…")
    # digit-digit ranges get an en dash (2016-2022, 0.90-0.96); leading minus
    # signs and hyphenated words are untouched
    seg = re.sub(r"(?<=\d)-(?=\d)", "–", seg)
    # a spaced hyphen used as a dash becomes a spaced en dash
    seg = seg.replace(" - ", " – ")
    # apostrophes inside words (contractions, possessives)
    seg = re.sub(r"(?<=\w)'(?=\w)", "’", seg)
    # trailing possessive (markets')
    seg = re.sub(r"(?<=s)'(?=[\s,.;:)\]]|$)", "’", seg)
    # double quotes: opening before non-space, closing after non-space
    seg = re.sub(r'"(?=\S)', "“", seg)
    seg = re.sub(r'(?<=\S)"', "”", seg)
    return seg


def smart(text: str) -> str:
    """Typographic cleanup applied only to text between tags."""
    parts = _TAG.split(text)
    return "".join(p if p.startswith("<") else _fix(p) for p in parts)
