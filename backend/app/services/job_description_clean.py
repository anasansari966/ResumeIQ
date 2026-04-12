"""Normalize scraped job descriptions: strip pseudo-markdown, unescape LinkedIn-style escapes, improve line breaks."""
from __future__ import annotations

import re


def clean_job_description(text: str, *, max_len: int = 50_000) -> str:
    """
    Turn blobs like ``**Role:** ... **Location:** ...`` and ``4\\+ Yrs`` into readable plain text
    with paragraph breaks.
    """
    if not text or not str(text).strip():
        return ""

    s = str(text).replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\u200b", "").replace("\ufeff", "")

    # LinkedIn / JobSpy often emit backslash escapes
    s = re.sub(r"\\([\\*+\-.&|()[\]{}#])", r"\1", s)

    # Bold / strong markers (repeat: nested or adjacent ** blocks)
    for _ in range(24):
        nxt = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
        if nxt == s:
            break
        s = nxt
    s = re.sub(r"__(.+?)__", r"\1", s)

    # Header immediately followed by prose or bullet list (no blank line after scrape)
    s = re.sub(
        r"(About The Role|About the role)\s+(We |You |This |Our |The )",
        r"\1\n\n\2",
        s,
        flags=re.I,
    )
    s = re.sub(
        r"(Key Responsibilities|Required Qualifications|Preferred Skills|Key Competencies)\s+\*\s+",
        r"\1\n\n• ",
        s,
        flags=re.I,
    )

    # Inline bullets: "Responsibilities * Build ..." -> newline + bullet
    s = re.sub(r"(?<=[.:!\w\)\]])\s+\*\s+(?=[A-Za-z0-9(])", "\n\n• ", s)

    # Section headers: require colon for Role/Location/… so we do not split "About The Role" or "Senior Data Scientist Role"
    _SECTION = (
        r"(?<!\w)(?="
        r"(?:About The Role|About the role|Key Responsibilities|Required Qualifications|"
        r"Qualifications|Preferred Skills|Nice to have|Key Competencies|What you need|What you'll do|"
        r"Benefits|Salary|Compensation|Join us to)\s*:?"
        r"|(?:Role|Location|Experience|Employment Type)\s*:"
        r")"
    )
    s = re.sub(_SECTION, "\n\n", s, flags=re.I)

    # Lines that are only a short title (ALL CAPS or Title Case header)
    s = re.sub(r"([.!?])\s+([A-Z][A-Z\s,&]{3,80}:)\s*", r"\1\n\n\2 ", s)

    # Bullets: "* item" or "- item" at line start -> bullet + space
    out_lines: list[str] = []
    for line in s.split("\n"):
        t = line.strip()
        if re.match(r"^[\*•\-]\s+", t):
            t = "• " + re.sub(r"^[\*•\-]\s+", "", t)
        elif re.match(r"^[\*•\-]$", t):
            t = ""
        out_lines.append(t)
    s = "\n".join(out_lines)

    # Inline meta labels stuck together (not "…The Role:" — Role omitted here on purpose)
    s = re.sub(
        r"([a-z0-9)])(\s+)((?:Location|Experience|Employment Type)\s*:)",
        r"\1\n\n\3",
        s,
        flags=re.I,
    )

    # Normalize spaces on each line (keep single newlines for lists)
    merged: list[str] = []
    for line in s.split("\n"):
        merged.append(re.sub(r"[ \t]+", " ", line).strip())
    s = "\n".join(x for x in merged if x is not None)

    # Collapse excessive blank lines
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"\)\s+,", "),", s)
    s = s.strip()

    if len(s) > max_len:
        s = s[:max_len].rstrip() + "…"
    return s
