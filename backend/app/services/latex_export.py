from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from app.config import settings


def _has_pdflatex(bin_dir: Path) -> bool:
    exe = bin_dir / ("pdflatex.exe" if platform.system() == "Windows" else "pdflatex")
    return exe.is_file()


def _discovered_tex_bin_dirs() -> list[str]:
    """If LaTeX is installed but not on PATH (common on Windows), pick known install locations."""
    out: list[str] = []
    if platform.system() != "Windows":
        return out

    candidates: list[Path] = []
    local = os.environ.get("LOCALAPPDATA", "")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pfx86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    for root in filter(None, (local, pf, pfx86)):
        r = Path(root)
        candidates.extend(
            (
                r / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64",
                r / "MiKTeX" / "miktex" / "bin" / "x64",
            )
        )
    home = Path.home()
    candidates.append(home / "scoop" / "apps" / "miktex" / "current" / "miktex" / "bin" / "x64")

    seen: set[str] = set()
    for d in candidates:
        try:
            if d.is_dir() and _has_pdflatex(d):
                s = str(d.resolve())
                if s not in seen:
                    seen.add(s)
                    out.append(s)
        except OSError:
            continue

    tl = Path(r"C:\texlive")
    if tl.is_dir():
        years = sorted(
            (p for p in tl.iterdir() if p.is_dir() and p.name.isdigit()),
            key=lambda p: int(p.name),
            reverse=True,
        )
        for y in years[:2]:
            w = y / "bin" / "win32"
            try:
                if w.is_dir() and _has_pdflatex(w):
                    s = str(w.resolve())
                    if s not in seen:
                        seen.add(s)
                        out.append(s)
            except OSError:
                continue
    return out


def _extra_path_prefix() -> str:
    raw = (settings.latex_path_extra or "").strip()
    user_parts = [p.strip() for p in raw.replace(",", os.pathsep).split(os.pathsep) if p.strip()]
    parts: list[str] = []
    for p in user_parts:
        if p and p not in parts:
            parts.append(p)
    for p in _discovered_tex_bin_dirs():
        if p not in parts:
            parts.append(p)
    return os.pathsep.join(parts)


def _which_path_string() -> str | None:
    prefix = _extra_path_prefix()
    base = os.environ.get("PATH", "")
    if not prefix:
        return base if base else None
    return f"{prefix}{os.pathsep}{base}"


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    prefix = _extra_path_prefix()
    override = _resolved_pdflatex_override()
    if override:
        bin_dir = str(Path(override).parent.resolve())
        if bin_dir:
            prefix = f"{bin_dir}{os.pathsep}{prefix}" if prefix else bin_dir
    if prefix:
        env["PATH"] = f"{prefix}{os.pathsep}{env.get('PATH', '')}"
    # Never open MiKTeX's package installer during a download request.
    env["MIKTEX_AUTO_INSTALL"] = "0"
    env["MIKTEX_AUTOINSTALL"] = "0"
    env["MIKTEX_DISABLEINSTALLERGUI"] = "1"
    return env


def _resolved_pdflatex_override() -> str | None:
    raw = os.path.expandvars(os.path.expanduser((settings.latex_pdflatex_path or "").strip()))
    if not raw:
        return None
    p = Path(raw)
    if p.is_file():
        return str(p.resolve())
    return None


def _latex_compiler_candidates() -> list[tuple[str, str]]:
    """Prefer explicit pdflatex, then PATH discovery (pdflatex, xelatex, lualatex, tectonic)."""
    which_path = _which_path_string()
    compilers: list[tuple[str, str]] = []
    seen_norm: set[str] = set()

    override = _resolved_pdflatex_override()
    if override:
        kind = "miktex" if "miktex" in os.path.normcase(override) else "latex"
        compilers.append((override, kind))
        seen_norm.add(os.path.normcase(override))

    for name in ("pdflatex", "xelatex", "lualatex"):
        found = shutil.which(name, path=which_path) if which_path else shutil.which(name)
        if found and os.path.normcase(found) not in seen_norm:
            kind = "miktex" if "miktex" in os.path.normcase(found) else "latex"
            compilers.append((found, kind))
            seen_norm.add(os.path.normcase(found))
    tectonic = shutil.which("tectonic", path=which_path) if which_path else shutil.which("tectonic")
    if tectonic and os.path.normcase(tectonic) not in seen_norm:
        compilers.append((tectonic, "tectonic"))
    return compilers


def _cleanup_build_artifacts(build_dir: Path, stem: str) -> None:
    for p in list(build_dir.glob(f"{stem}*")):
        try:
            p.unlink()
        except OSError:
            pass


def _run_compiler(compiler: str, kind: str, tex_name: str, work_dir: Path) -> bool:
    if kind == "tectonic":
        cmd = [compiler, tex_name, "--outdir", "."]
        rounds = 1
    else:
        no_installer = ["--disable-installer"] if kind == "miktex" else []
        cmd = [compiler, *no_installer, "-interaction=nonstopmode", "-halt-on-error", tex_name]
        rounds = 2

    run_env = _subprocess_env()
    try:
        for _ in range(rounds):
            proc = subprocess.run(  # noqa: S603
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=45,
                env=run_env,
            )
            if proc.returncode != 0:
                return False
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def latex_to_pdf_bytes(tex_source: str, *, build_dir: Path | None = None) -> bytes | None:
    """
    Compile LaTeX to PDF. When ``build_dir`` is set (packaged templates under .extracted/),
    compilation runs with cwd = that folder so layout matches how those .tex files are built locally.
    """
    compilers = _latex_compiler_candidates()
    if not compilers:
        return None

    if build_dir is not None:
        build_dir = build_dir.resolve()
        if not build_dir.is_dir():
            return None
        parts = {x.lower() for x in build_dir.parts}
        if ".extracted" not in parts:
            return None

    for compiler, kind in compilers:
        stem = f"resumeiq_b_{uuid.uuid4().hex[:12]}"
        tex_name = f"{stem}.tex"
        pdf_name = f"{stem}.pdf"

        if build_dir is not None:
            wd = build_dir
            tex_path = wd / tex_name
            pdf_path = wd / pdf_name
            built: bytes | None = None
            try:
                tex_path.write_text(tex_source, encoding="utf-8")
                ok = _run_compiler(compiler, kind, tex_path.name, wd)
                if ok and pdf_path.is_file():
                    built = pdf_path.read_bytes()
            finally:
                _cleanup_build_artifacts(wd, stem)
            if built:
                return built
            continue

        with tempfile.TemporaryDirectory() as td:
            wd = Path(td)
            tex_path = wd / tex_name
            pdf_path = wd / pdf_name
            tex_path.write_text(tex_source, encoding="utf-8")
            ok = _run_compiler(compiler, kind, tex_path.name, wd)
            if ok and pdf_path.is_file():
                return pdf_path.read_bytes()

    return None
