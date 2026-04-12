"""Discover runtime resume templates from built-ins and the project Templates/ folder."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import settings
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


@lru_cache
def list_folder_templates() -> tuple[TemplateDescriptor, ...]:
    root = templates_dir()
    if not root.is_dir():
        return ()

    found: list[TemplateDescriptor] = []
    for idx, folder in enumerate(sorted(p for p in root.iterdir() if p.is_dir()), start=1):
        tex_files = sorted(p for p in folder.glob("*.tex") if p.name.lower() != "structure.tex")
        if not tex_files:
            continue
        entry = tex_files[0]
        folder_name = _humanize_template_name(folder.name)
        variant = "sidebar-classic" if (folder / "structure.tex").is_file() else "clean"
        found.append(
            TemplateDescriptor(
                id=slug_folder_template_id(folder.name),
                name=folder_name,
                style="Imported template",
                best_for="Template-first resume flow with polished PDF export",
                ats_score=94,
                kind="folder",
                source="folder",
                description=f"{folder_name} imported from your local template library.",
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
    return tuple(sorted((*list_folder_templates(), *list_builtin_templates()), key=lambda item: item.sort_order))


def get_template_descriptor(template_id: str) -> TemplateDescriptor | None:
    for item in list_resume_templates():
        if item.id == template_id:
            return item
    return None


def folder_template_entry_path(template_id: str) -> Path | None:
    desc = get_template_descriptor(template_id)
    if not desc or desc.source != "folder":
        return None
    return desc.entry_path


def folder_template_structure_path(template_id: str) -> Path | None:
    desc = get_template_descriptor(template_id)
    if not desc or desc.source != "folder" or not desc.folder_path:
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
    return bool(desc and desc.source == "folder")


def first_resume_template_id() -> str:
    folder_items = list_folder_templates()
    if folder_items:
        return folder_items[0].id
    return first_latex_template_id()


def is_supported_template_id(template_id: str) -> bool:
    return get_template_descriptor(template_id) is not None or is_latex_template_id(template_id)
