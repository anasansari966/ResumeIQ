"""Discover runtime resume templates from built-ins and the project Templates/ folder."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.services import packaged_templates
from app.services.latex_templates import first_latex_template_id, is_latex_template_id, list_latex_templates


@dataclass(frozen=True)
class TemplateDescriptor:
    id: str
    name: str
    style: str = "LaTeX"
    best_for: str = ""
    ats_score: int = 90
    kind: str = "latex"
    source: str = "builtin"
    description: str = ""
    preview_variant: str = "clean"
    file_name: str | None = None
    entry_path: Path | None = None
    folder_path: Path | None = None
    preview_asset: Path | None = None
    sort_order: int = 0


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def templates_dir() -> Path:
    if settings.templates_dir:
        return Path(settings.templates_dir)
    return project_root() / "Templates"


def slug_docx_id(filename: str) -> str:
    stem = Path(filename).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    return f"doc_{stem or 'template'}"


def slug_folder_template_id(name: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"folder_{stem or 'template'}"


_docx_like_suffix = re.compile(r"(?i)\.(docx|dotx|doc)$")


def _humanize_template_name(raw: str) -> str:
    text = raw.replace("_", " ").replace("-", " ").strip()
    text = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.title() or raw


def docx_display_name(stem: str) -> str:
    """File title for UI: strip repeated Word-like extensions from stem."""
    s = stem.strip()
    while True:
        m = _docx_like_suffix.search(s)
        if not m:
            break
        s = s[: m.start()].strip()
    return s or stem.strip()


def primary_docx_path() -> Path | None:
    """The one Word template used for previews and export."""
    root = templates_dir()
    name = (settings.resume_template_docx or "").strip() or "Document 3.docx"
    p = root / name
    if not p.is_file() or p.name.startswith("~$"):
        return None
    return p


@lru_cache
def list_docx_templates() -> tuple[tuple[str, str, Path], ...]:
    """Return at most one entry: (id, display_name, path) for the configured template file."""
    p = primary_docx_path()
    if not p:
        return ()
    return ((slug_docx_id(p.name), docx_display_name(p.stem), p),)


def docx_path_for_id(template_id: str) -> Path | None:
    for tid, _name, path in list_docx_templates():
        if tid == template_id:
            return path
    return None


def is_docx_template_id(template_id: str) -> bool:
    return docx_path_for_id(template_id) is not None


def first_docx_template_id() -> str | None:
    items = list_docx_templates()
    return items[0][0] if items else None


def _folder_preview_asset(folder: Path) -> Path | None:
    patterns = ("preview", "thumb", "thumbnail", "screenshot", "cover")
    image_suffixes = {".png", ".jpg", ".jpeg", ".webp"}
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in image_suffixes)
    for p in files:
        low = p.stem.lower()
        if any(token in low for token in patterns):
            return p
    return None


def _read_folder_meta(folder: Path) -> dict:
    meta_path = folder / "resumeiq.meta.json"
    if not meta_path.is_file():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


@lru_cache
def list_folder_templates() -> tuple[TemplateDescriptor, ...]:
    root = templates_dir()
    if not root.is_dir():
        return ()

    found: list[TemplateDescriptor] = []
    seen_keys: set[tuple[str, str]] = set()
    for idx, folder in enumerate(sorted(p for p in root.iterdir() if p.is_dir()), start=1):
        meta = _read_folder_meta(folder)
        entry_file = str(meta.get("entry_file") or "").strip()
        preferred_entry = folder / entry_file if entry_file else None
        tex_files = sorted(p for p in folder.glob("*.tex") if p.name.lower() != "structure.tex")
        if preferred_entry and preferred_entry.is_file():
            tex_files = [preferred_entry, *[p for p in tex_files if p != preferred_entry]]
        if not tex_files:
            continue
        entry = tex_files[0]
        folder_name = str(meta.get("name") or _humanize_template_name(folder.name))
        source = str(meta.get("source") or "folder")
        variant = str(
            meta.get("preview_variant")
            or ("sidebar-classic" if (folder / "structure.tex").is_file() else "clean")
        )
        description = str(
            meta.get("description")
            or (
                f"{folder_name} imported from web."
                if source == "web"
                else f"{folder_name} imported from your local template library."
            )
        )
        best_for = str(
            meta.get("best_for")
            or (
                "Web-imported LaTeX layout for template-first PDF exports"
                if source == "web"
                else "Template-first resume flow with polished PDF export"
            )
        )
        try:
            ats_score = int(meta.get("ats_score") or 94)
        except Exception:  # noqa: BLE001
            ats_score = 94
        found.append(
            TemplateDescriptor(
                id=slug_folder_template_id(folder.name),
                name=folder_name,
                style="Web LaTeX import" if source == "web" else "Imported template",
                best_for=best_for,
                ats_score=ats_score,
                kind="folder",
                source=source,
                description=description,
                preview_variant=variant,
                file_name=entry.name,
                entry_path=entry,
                folder_path=folder,
                preview_asset=_folder_preview_asset(folder),
                sort_order=idx,
            )
        )
        dedupe_key = (source, folder_name.strip().lower())
        if dedupe_key in seen_keys:
            found.pop()
            continue
        seen_keys.add(dedupe_key)
    return tuple(found)


def list_packaged_zip_templates() -> tuple[TemplateDescriptor, ...]:
    """LaTeX templates shipped as .zip under backend/templates/ (extracted to .extracted/)."""
    zips = packaged_templates.iter_packaged_template_paths()
    if not zips:
        return ()
    found: list[TemplateDescriptor] = []
    for idx, zp in enumerate(zips, start=1):
        folder = packaged_templates.ensure_zip_extracted(zp)
        entry = packaged_templates.main_tex_in_folder(folder)
        if not entry:
            continue
        slug = packaged_templates.slug_from_zip(zp)
        display = packaged_templates.display_name_from_zip(zp)
        # Word Online–style ATS labels for the picker (export still uses LaTeX zip layouts).
        word_style = {
            "chicago": ("ATS Chronological", "Word-style chronological ATS resume"),
            "milano": ("ATS Modern", "Word-style modern ATS resume"),
            "easy": ("ATS Simple", "Word-style simple ATS resume"),
            "classic": ("ATS Professional", "Word-style professional ATS resume"),
        }
        label_key = next((k for k in word_style if k in slug.lower()), None)
        if label_key:
            display, best = word_style[label_key]
        else:
            best = "ATS-friendly layout — preview updates with your resume before PDF export"
        tid = f"zip_{slug}"
        low = slug.lower()
        if "chicago" in low:
            variant = "sidebar-classic"
        elif "milano" in low:
            variant = "milano"
        elif "classic" in low:
            variant = "minimal"
        elif "easy" in low:
            variant = "clean"
        else:
            variant = "clean"
        found.append(
            TemplateDescriptor(
                id=tid,
                name=display,
                style="ATS (Word-inspired)",
                best_for=best,
                ats_score=min(98, 91 + idx),
                kind="latex",
                source="zip",
                description=f"{display} — ATS-friendly layout inspired by Microsoft Word resume templates; PDF via LaTeX.",
                preview_variant=variant,
                file_name=entry.name,
                entry_path=entry,
                folder_path=folder,
                preview_asset=_folder_preview_asset(folder),
                sort_order=idx,
            )
        )
    return tuple(found)


@lru_cache
def list_builtin_templates() -> tuple[TemplateDescriptor, ...]:
    base_order = len(list_folder_templates()) + 10
    items: list[TemplateDescriptor] = []
    for idx, (tid, name) in enumerate(list_latex_templates(), start=base_order):
        low = tid.lower()
        if "robotics" in low or "research" in low:
            variant = "research"
            best_for = "Research and technical experience with publication-heavy content"
            score = 93
        elif "data" in low:
            variant = "research"
            best_for = "Dense, keyword-heavy resumes for analytics and data roles"
            score = 96
        elif "executive" in low:
            variant = "clean"
            best_for = "Leadership, management, and impact-driven executive profiles"
            score = 95
        elif "modern" in low or "emerald" in low:
            variant = "clean"
            best_for = "Balanced modern look for general professional hiring tracks"
            score = 95
        elif "ats" in low:
            variant = "clean"
            best_for = "ATS-friendly screening with simple, consistent section flow"
            score = 97
        else:
            variant = "minimal"
            best_for = "Minimal visual style with concise readable sections"
            score = 94
        items.append(
            TemplateDescriptor(
                id=tid,
                name=name,
                style="LaTeX",
                best_for=best_for,
                ats_score=score,
                kind="latex",
                source="builtin",
                description=f"Built-in {name} template",
                preview_variant=variant,
                sort_order=idx,
            )
        )
    return tuple(items)


def list_resume_templates() -> tuple[TemplateDescriptor, ...]:
    """Zip ATS packs first, then unique folder imports, then built-in LaTeX layouts."""
    packaged = list_packaged_zip_templates()
    builtins = list_builtin_templates()
    folders = list_folder_templates()

    zip_tokens = set()
    for item in packaged:
        # zip_chicago_latex_resume_template_free_download → chicago
        slug = item.id.removeprefix("zip_")
        for token in ("chicago", "milano", "classic", "easy"):
            if token in slug:
                zip_tokens.add(token)

    unique_folders: list[TemplateDescriptor] = []
    for item in folders:
        low = item.id.lower()
        # Skip local folder extracts that duplicate a packaged zip ATS layout.
        if any(token in low for token in zip_tokens):
            continue
        unique_folders.append(item)

    merged = (*packaged, *unique_folders, *builtins)
    if not merged:
        return ()
    seen: set[str] = set()
    out: list[TemplateDescriptor] = []
    for item in sorted(
        merged,
        key=lambda row: (0 if row.source == "zip" else 1 if row.source in {"folder", "web"} else 2, row.sort_order),
    ):
        if item.id in seen:
            continue
        seen.add(item.id)
        out.append(item)
    return tuple(out)


def get_template_descriptor(template_id: str) -> TemplateDescriptor | None:
    for item in list_resume_templates():
        if item.id == template_id:
            return item
    return None


def folder_template_entry_path(template_id: str) -> Path | None:
    desc = get_template_descriptor(template_id)
    if not desc or desc.source not in {"folder", "web"}:
        return None
    return desc.entry_path


def folder_template_structure_path(template_id: str) -> Path | None:
    desc = get_template_descriptor(template_id)
    if not desc or desc.source not in {"folder", "web"} or not desc.folder_path:
        return None
    p = desc.folder_path / "structure.tex"
    return p if p.is_file() else None


def template_preview_asset_path(template_id: str) -> Path | None:
    desc = get_template_descriptor(template_id)
    if not desc:
        return None
    return desc.preview_asset if desc.preview_asset and desc.preview_asset.is_file() else None


def is_folder_template_id(template_id: str) -> bool:
    desc = get_template_descriptor(template_id)
    return bool(desc and desc.source in {"folder", "web", "zip"})


def zip_packaged_template_build_dir(template_id: str) -> Path | None:
    """Directory under backend/templates/.extracted where packaged .tex lives — used as LaTeX cwd for PDF."""
    desc = get_template_descriptor(template_id)
    if not desc or desc.source != "zip" or not desc.folder_path:
        return None
    p = desc.folder_path.resolve()
    if not p.is_dir():
        return None
    parts = {x.lower() for x in p.parts}
    if ".extracted" not in parts:
        return None
    return p


def first_resume_template_id() -> str:
    packaged = list_packaged_zip_templates()
    if packaged:
        return packaged[0].id
    folder_items = list_folder_templates()
    if folder_items:
        return folder_items[0].id
    return first_latex_template_id()


def is_supported_template_id(template_id: str) -> bool:
    return get_template_descriptor(template_id) is not None or is_latex_template_id(template_id)
