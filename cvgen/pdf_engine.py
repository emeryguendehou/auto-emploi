# -*- coding: utf-8 -*-
"""
pdf_engine.py — Rendu HTML -> PDF avec deux moteurs, par ordre de préférence :

  1. WeasyPrint (si installé avec ses DLL GTK/Pango — rare sous Windows) ;
  2. Microsoft Edge headless (présent d'office sous Windows, rendu Chromium).

Expose :
  write_pdf(html, pdf_path)  -> écrit le PDF
  count_pages(html)          -> nombre de pages du rendu (pour la boucle
                                d'auto-ajustement à 1 page de generate_cv)
"""

import os
import subprocess
import tempfile
import time
from pathlib import Path

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def _weasyprint():
    try:
        from weasyprint import HTML
        return HTML
    except Exception:
        return None


def _browser_path() -> str:
    for p in EDGE_CANDIDATES:
        if Path(p).exists():
            return p
    raise RuntimeError(
        "Aucun moteur PDF : ni WeasyPrint, ni Edge/Chrome trouvés. "
        "Installer le runtime GTK3 + weasyprint, ou Microsoft Edge."
    )


def _browser_render(html: str, pdf_path: Path) -> None:
    """Rend le HTML en PDF via Edge/Chrome headless (fichiers temporaires)."""
    browser = _browser_path()
    pdf_path = Path(pdf_path).resolve()  # Edge résout les chemins relatifs ailleurs
    # Indispensable : sans ça, si un PDF du même nom existe déjà (régénération),
    # la boucle d'attente ci-dessous le voit « stable » et rend la main AVANT
    # qu'Edge ait rendu. Le HTML temporaire est alors supprimé trop tôt et Edge
    # imprime sa page d'erreur « ERR_FILE_NOT_FOUND » par-dessus.
    pdf_path.unlink(missing_ok=True)
    fd, tmp_html = tempfile.mkstemp(suffix=".html")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        url = Path(tmp_html).as_uri()
        # --enable-logging=stderr est indispensable sous Windows : sans lui,
        # le lanceur msedge.exe se détache de la console et rend la main
        # AVANT d'avoir écrit le PDF (échec silencieux, code 0).
        cmd = [
            browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
            "--enable-logging=stderr", f"--print-to-pdf={pdf_path}", url,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=90)
        # Sous Windows, le lanceur msedge.exe peut rendre la main AVANT que le
        # PDF soit écrit sur disque : on attend le fichier (taille stable).
        deadline = time.monotonic() + 30
        last_size = -1
        while time.monotonic() < deadline:
            if Path(pdf_path).exists():
                size = Path(pdf_path).stat().st_size
                if size > 0 and size == last_size:
                    return
                last_size = size
            time.sleep(0.2)
        raise RuntimeError(
            f"Rendu Edge échoué (code {result.returncode}): "
            f"{result.stderr.decode(errors='replace')[:300]}"
        )
    finally:
        Path(tmp_html).unlink(missing_ok=True)


def write_pdf(html: str, pdf_path) -> None:
    """Écrit le PDF avec le premier moteur disponible."""
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    HTML = _weasyprint()
    if HTML is not None:
        HTML(string=html).write_pdf(str(pdf_path))
        return
    _browser_render(html, pdf_path)


def count_pages(html: str) -> int:
    """Nombre de pages du rendu. Sans moteur PDF, renvoie 1 (pas d'ajustement)."""
    HTML = _weasyprint()
    if HTML is not None:
        return len(HTML(string=html).render().pages)
    try:
        fd, tmp_pdf = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        # Edge refuse d'écraser silencieusement un fichier vide dans certains
        # cas : on le supprime avant le rendu.
        Path(tmp_pdf).unlink(missing_ok=True)
        _browser_render(html, Path(tmp_pdf))
        import pdfplumber
        with pdfplumber.open(tmp_pdf) as pdf:
            return len(pdf.pages)
    except Exception:
        return 1
    finally:
        Path(tmp_pdf).unlink(missing_ok=True)
