"""Serve template card preview images (disk asset, bundled SVG, or placeholder)."""
from __future__ import annotations

import html
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, Response

from app.services.template_registry import get_template_descriptor, is_supported_template_id, template_preview_asset_path

_STATIC_PREVIEWS_DIR = Path(__file__).resolve().parent.parent / "static" / "template_previews"


def _placeholder_svg_label(label: str) -> bytes:
    safe = html.escape((label or "Template").strip())[:80]
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="360" height="220" viewBox="0 0 360 220">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#e0e7ff"/><stop offset="1" stop-color="#f1f5f9"/>
  </linearGradient></defs>
  <rect width="360" height="220" fill="url(#g)"/>
  <rect x="20" y="18" width="200" height="14" rx="3" fill="#6366f1" opacity="0.35"/>
  <rect x="20" y="42" width="320" height="8" rx="2" fill="#94a3b8" opacity="0.45"/>
  <rect x="20" y="56" width="280" height="8" rx="2" fill="#94a3b8" opacity="0.35"/>
  <rect x="20" y="88" width="100" height="10" rx="2" fill="#64748b" opacity="0.5"/>
  <rect x="20" y="108" width="320" height="6" rx="2" fill="#cbd5e1"/>
  <rect x="20" y="120" width="300" height="6" rx="2" fill="#cbd5e1"/>
  <rect x="20" y="132" width="260" height="6" rx="2" fill="#cbd5e1"/>
  <text x="180" y="195" text-anchor="middle" font-family="Segoe UI,system-ui,sans-serif" font-size="13" fill="#475569">{safe}</text>
</svg>
"""
    return svg.encode("utf-8")


def build_template_preview_response(template_id: str) -> FileResponse | Response:
    if not is_supported_template_id(template_id):
        raise HTTPException(404, "Template not found")

    asset = template_preview_asset_path(template_id)
    if asset:
        media = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(asset.suffix.lower())
        if media:
            return FileResponse(asset, media_type=media, headers={"Cache-Control": "public, max-age=86400"})

    slug = template_id.removeprefix("zip_") if template_id.startswith("zip_") else ""
    if slug:
        svg_path = _STATIC_PREVIEWS_DIR / f"{slug}.svg"
        if svg_path.is_file():
            return FileResponse(svg_path, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})

    desc = get_template_descriptor(template_id)
    label = desc.name if desc else template_id
    return Response(
        content=_placeholder_svg_label(label),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=300"},
    )


def template_preview_url_path(template_id: str) -> str:
    return f"/api/v1/templates/{template_id}/preview"
