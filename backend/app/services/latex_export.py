from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def latex_to_pdf_bytes(tex_source: str) -> bytes | None:
    compilers = [c for c in (shutil.which("xelatex"), shutil.which("pdflatex")) if c]
    if not compilers:
        return None
    for compiler in compilers:
        with tempfile.TemporaryDirectory() as td:
            wd = Path(td)
            tex_path = wd / "resume.tex"
            pdf_path = wd / "resume.pdf"
            tex_path.write_text(tex_source, encoding="utf-8")
            cmd = [compiler, "-interaction=nonstopmode", "-halt-on-error", tex_path.name]
            ok = True
            for _ in range(2):
                proc = subprocess.run(cmd, cwd=str(wd), capture_output=True, text=True, timeout=45)  # noqa: S603
                if proc.returncode != 0:
                    ok = False
                    break
            if ok and pdf_path.is_file():
                return pdf_path.read_bytes()
    return None
