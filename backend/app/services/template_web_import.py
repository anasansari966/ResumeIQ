from __future__ import annotations

import io
import ipaddress
import json
import re
import socket
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import ProxyHandler, Request, build_opener

from fastapi import HTTPException

from app.services import template_registry
from app.services.template_registry import (
    get_template_descriptor,
    slug_folder_template_id,
    templates_dir,
)

_DOC_CLASS_RE = re.compile(r"\\documentclass(?:\[(?P<opts>[^\]]*)\])?\{(?P<cls>[^}]+)\}", re.I)
_BEGIN_DOC_RE = re.compile(r"\\begin\s*\{\s*document\s*\}", re.I)
_HREF_RE = re.compile(r"""href=["'](?P<u>[^"']+)["']""", re.I)
_FILE_HINT_RE = re.compile(r"\.(?:tex|zip)(?:[?#].*)?$", re.I)
_MAX_DOWNLOAD_BYTES = 8_000_000

_STRUCTURE_COMPAT_BLOCK = r"""
\usepackage{xcolor}
\usepackage{enumitem}
\setlist{noitemsep,nolistsep}
\providecommand{\userinformation}[1]{\renewcommand{\userinformation}{#1}}
\providecommand{\cvheading}[1]{{\Huge\bfseries #1}\par\vspace{.6\baselineskip}}
\providecommand{\cvsubheading}[1]{{\Large\bfseries #1}\bigbreak}
\providecommand{\Sep}{\vspace{1em}}
\providecommand{\SmallSep}{\vspace{0.5em}}
\providecommand{\aboutme}[2]{\textbf{#1}~~#2\par\Sep}
\providecommand{\CVSection}[1]{{\Large\textbf{#1}}\par\SmallSep}
\providecommand{\CVItem}[2]{\textbf{#1}\par#2\SmallSep}
\providecommand{\bluebullet}{\textbullet~~}
""".strip()


def _is_blocked_ip(host: str) -> bool:
    try:
        addrs = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    for item in addrs:
        ip_raw = item[4][0]
        try:
            ip = ipaddress.ip_address(ip_raw)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return True
    return False


def _normalize_source_url(raw_url: str) -> str:
    value = (raw_url or "").strip()
    if not value:
        raise HTTPException(400, "Template URL is required")

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(400, "Template URL must start with http:// or https://")
    if not parsed.netloc:
        raise HTTPException(400, "Template URL is invalid")

    host = (parsed.hostname or "").lower()
    if not host:
        raise HTTPException(400, "Template host is invalid")
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(400, "Localhost URLs are not allowed for web template import")
    if _is_blocked_ip(host):
        raise HTTPException(400, "Private/internal network URLs are blocked for security")

    if host == "github.com":
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 5 and parts[2] == "blob":
            user, repo, _blob, branch = parts[:4]
            tail = "/".join(parts[4:])
            return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{tail}"

    return value


def _download_bytes(url: str) -> tuple[bytes, str, str]:
    req = Request(
        url,
        headers={
            "User-Agent": "ResumeIQ-TemplateImporter/1.0",
            "Accept": "text/plain,text/x-tex,text/html,application/zip,*/*;q=0.5",
        },
    )
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(req, timeout=40) as response:
            ctype = (response.headers.get("Content-Type") or "").lower()
            final_url = str(response.geturl() or url)
            data = response.read(_MAX_DOWNLOAD_BYTES + 1)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Failed to download template URL: {exc}") from exc

    if len(data) > _MAX_DOWNLOAD_BYTES:
        raise HTTPException(400, "Template file is too large (max 8 MB)")
    return data, ctype, final_url


def _looks_like_latex(text: str) -> bool:
    lowered = text.lower()
    return "\\documentclass" in lowered or "\\begin{document}" in lowered


def _decode_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace").replace("\ufeff", "").strip()


def _looks_like_zip(url: str, content_type: str, data: bytes) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(".zip") or "zip" in content_type or data.startswith(b"PK\x03\x04")


def _choose_main_tex_in_zip(zf: zipfile.ZipFile, tex_members: list[str]) -> str:
    preferred_names = {"main.tex", "resume.tex", "cv.tex", "template.tex"}
    best_name = tex_members[0]
    best_score = -10_000

    for member in tex_members:
        base = Path(member).name.lower()
        score = 0
        if base in preferred_names:
            score += 30
        if base == "structure.tex":
            score -= 25
        score -= member.count("/")
        try:
            snippet = _decode_text(zf.read(member)[:120_000])
        except Exception:  # noqa: BLE001
            snippet = ""
        if "\\documentclass" in snippet:
            score += 20
        if "\\begin{document}" in snippet:
            score += 20
        if "resume" in base or "cv" in base:
            score += 6
        if score > best_score:
            best_score = score
            best_name = member
    return best_name


def _extract_zip_latex(data: bytes) -> tuple[str, str | None]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            members = [
                item.filename
                for item in zf.infolist()
                if not item.is_dir() and not item.filename.startswith("__MACOSX/")
            ]
            tex_members = [name for name in members if name.lower().endswith(".tex")]
            if not tex_members:
                raise HTTPException(400, "ZIP file does not contain any .tex files")

            main_member = _choose_main_tex_in_zip(zf, tex_members)
            main_tex = _decode_text(zf.read(main_member))

            structure_member = next(
                (name for name in tex_members if Path(name).name.lower() == "structure.tex" and name != main_member),
                None,
            )
            structure_tex = _decode_text(zf.read(structure_member)) if structure_member else None
            return main_tex, structure_tex
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Could not parse template ZIP: {exc}") from exc


def _find_template_link_in_html(base_url: str, html: str) -> str | None:
    candidates: list[str] = []
    for match in _HREF_RE.finditer(html):
        raw_href = (match.group("u") or "").strip()
        if not raw_href:
            continue
        abs_url = urljoin(base_url, raw_href)
        if _FILE_HINT_RE.search(abs_url):
            candidates.append(abs_url)
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            0 if "latex" in item.lower() else 1,
            0 if item.lower().endswith(".zip") else 1,
            len(item),
        )
    )
    return candidates[0]


def _download_template_sources(url: str, depth: int = 0) -> tuple[str, str | None, str]:
    if depth > 2:
        raise HTTPException(400, "Could not locate a downloadable LaTeX file from the provided URL")

    normalized = _normalize_source_url(url)
    data, content_type, final_url = _download_bytes(normalized)

    if _looks_like_zip(final_url, content_type, data):
        main_tex, structure_tex = _extract_zip_latex(data)
        if not _looks_like_latex(main_tex):
            raise HTTPException(400, "ZIP template .tex file does not contain a LaTeX document")
        return main_tex, structure_tex, final_url

    text = _decode_text(data)
    if _looks_like_latex(text):
        return text, None, final_url

    if "html" in content_type or "<html" in text[:3000].lower():
        linked = _find_template_link_in_html(final_url, text)
        if not linked:
            raise HTTPException(400, "Provided page does not expose a downloadable .tex or .zip template link")
        return _download_template_sources(linked, depth + 1)

    raise HTTPException(400, "Downloaded content is neither LaTeX nor an HTML page with template links")


def _extract_preamble_and_docclass(tex_source: str) -> tuple[str, str, str]:
    raw = (tex_source or "").replace("\r\n", "\n").replace("\ufeff", "")
    begin_match = _BEGIN_DOC_RE.search(raw)
    preamble = raw[: begin_match.start()] if begin_match else raw

    doc_class = "memoir"
    doc_opts = "a4paper,12pt"
    class_match = _DOC_CLASS_RE.search(preamble)
    if class_match:
        doc_class = (class_match.group("cls") or "memoir").strip() or "memoir"
        opts = (class_match.group("opts") or "").strip()
        if opts:
            doc_opts = opts
        preamble = _DOC_CLASS_RE.sub("", preamble, count=1)

    return preamble.strip(), doc_class, doc_opts


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return text[:64] or "template"


def _display_name(raw_name: str | None, source_url: str) -> str:
    if raw_name and raw_name.strip():
        return raw_name.strip()
    path = urlparse(source_url).path
    stem = Path(path).name or "Web LaTeX Template"
    stem = re.sub(r"\.zip$", "", stem, flags=re.I)
    stem = re.sub(r"\.tex_?$", "", stem, flags=re.I)
    stem = Path(stem).stem
    return stem.replace("-", " ").replace("_", " ").strip().title() or "Web LaTeX Template"


def _folder_name(base_slug: str) -> str:
    return f"web_{base_slug}"


def _merge_structure_tex(base_tex: str, doc_class: str, doc_opts: str) -> str:
    text = (base_tex or "").replace("\r\n", "\n").replace("\ufeff", "")
    begin_match = _BEGIN_DOC_RE.search(text)
    if begin_match:
        text = text[: begin_match.start()]
    text = _DOC_CLASS_RE.sub("", text, count=1).strip()
    # Keep imports compatible with pdflatex; imported web templates often require xelatex-only fontspec.
    text = re.sub(r"^\s*\\usepackage(?:\[[^\]]*\])?\{fontspec\}\s*(?:%.*)?$", "", text, flags=re.I | re.M)
    text = re.sub(r"^\s*\\setmainfont\{[^}]*\}\s*(?:%.*)?$", "", text, flags=re.I | re.M)
    text = re.sub(r"^\s*\\setsansfont\{[^}]*\}\s*(?:%.*)?$", "", text, flags=re.I | re.M)
    text = re.sub(r"^\s*\\setmonofont\{[^}]*\}\s*(?:%.*)?$", "", text, flags=re.I | re.M)
    text = re.sub(
        r"^\s*\\newfontfamily\\[A-Za-z@]+(?:\[[^\]]*\])?\{[^}]*\}\s*(?:%.*)?$",
        "",
        text,
        flags=re.I | re.M,
    )
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return f"% resumeiq:documentclass={doc_class}|{doc_opts}\n\n{text}\n\n{_STRUCTURE_COMPAT_BLOCK}\n"


def _write_imported_template_folder(
    folder: Path,
    source_tex: str,
    structure_seed_tex: str,
    doc_class: str,
    doc_opts: str,
    source_url: str,
    display_name: str,
) -> None:
    folder.mkdir(parents=True, exist_ok=True)

    structure = _merge_structure_tex(structure_seed_tex, doc_class, doc_opts)
    (folder / "template.tex").write_text(source_tex, encoding="utf-8")
    (folder / "structure.tex").write_text(structure, encoding="utf-8")

    meta: dict[str, Any] = {
        "name": display_name,
        "source": "web",
        "url": source_url,
        "description": f"Imported from {source_url}",
        "best_for": "Web-imported LaTeX layout for PDF/TEX exports",
        "preview_variant": "clean",
        "ats_score": 94,
        "entry_file": "template.tex",
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }
    (folder / "resumeiq.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def refresh_template_registry_cache() -> None:
    template_registry.list_docx_templates.cache_clear()
    template_registry.list_folder_templates.cache_clear()
    template_registry.list_builtin_templates.cache_clear()


def import_latex_template_from_web(url: str, name: str | None = None) -> str:
    source_tex, structure_override, resolved_url = _download_template_sources(url)
    preamble, doc_class, doc_opts = _extract_preamble_and_docclass(source_tex)
    structure_seed = structure_override if structure_override else preamble

    display_name = _display_name(name, resolved_url)
    slug = _slugify(display_name)
    folder = templates_dir() / _folder_name(slug)
    _write_imported_template_folder(
        folder=folder,
        source_tex=source_tex,
        structure_seed_tex=structure_seed,
        doc_class=doc_class,
        doc_opts=doc_opts,
        source_url=resolved_url,
        display_name=display_name,
    )

    refresh_template_registry_cache()
    template_id = slug_folder_template_id(folder.name)
    if not get_template_descriptor(template_id):
        raise HTTPException(500, "Template import completed but registration failed")
    return template_id
