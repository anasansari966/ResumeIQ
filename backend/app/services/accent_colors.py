"""Normalize resume accent colors for preview + LaTeX/PDF export."""
from __future__ import annotations

import re
from typing import Any


_DEFAULT_ACCENT = "0f766e"


def normalize_accent_hex(value: Any, fallback: str = _DEFAULT_ACCENT) -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback.lstrip("#").lower()
    if raw.startswith("#"):
        raw = raw[1:]
    if re.fullmatch(r"[0-9a-fA-F]{6}", raw):
        return raw.lower()
    return fallback.lstrip("#").lower()


def accent_from_resume(resume_json: dict[str, Any] | None, fallback: str = _DEFAULT_ACCENT) -> str:
    data = resume_json or {}
    return normalize_accent_hex(data.get("accent_color") or data.get("theme_accent"), fallback)


def accent_rgb_tuple(hex6: str) -> tuple[int, int, int]:
    h = normalize_accent_hex(hex6)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def apply_accent_to_latex_preamble(preamble: str, resume_json: dict[str, Any] | None) -> str:
    """Rewrite common LaTeX accent color definitions to the user-selected hex."""
    hex6 = accent_from_resume(resume_json)
    r, g, b = accent_rgb_tuple(hex6)
    text = preamble or ""
    rgb_value = f"{{{r},{g},{b}}}"
    html_value = f"{{{hex6}}}"

    # Named RGB/HTML colors used by packaged zip templates.
    # Build patterns without f-strings — literal `}` inside rf"..." is invalid.
    for name in ("sectioncolor", "headercolor", "headingcolor", "accent", "titleblue", "subtitleblue", "coral"):
        escaped = re.escape(name)
        text = re.sub(
            r"(\\definecolor\{" + escaped + r"\}\{RGB\})\{[^}]*\}",
            r"\g<1>" + rgb_value,
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"(\\definecolor\{" + escaped + r"\}\{HTML\})\{[^}]*\}",
            r"\g<1>" + html_value,
            text,
            flags=re.IGNORECASE,
        )

    # Ensure an accent color exists for templates that only use HTML accent.
    if r"\definecolor{accent}" not in text.lower():
        text += f"\n\\definecolor{{accent}}{{HTML}}{{{hex6}}}\n"

    # RoyalBlue-style accents in structure.tex based templates.
    text = text.replace("{RoyalBlue}", "{accent}")
    text = re.sub(r"\\color\{RoyalBlue\}", r"\\color{accent}", text)
    text = re.sub(r"\\textcolor\{RoyalBlue\}", r"\\textcolor{accent}", text)

    return text
