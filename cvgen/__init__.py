# -*- coding: utf-8 -*-
"""
cvgen — Module de génération de CV ciblés (architecture 3 couches).

  CONTENU   : profile_master.yaml  (source de vérité unique, bullets FR/EN taggés)
  SÉLECTION : generate_cv.py       (offre -> poids de tags -> sélection de bullets)
  RENDU     : country_rules.yaml + template_cv.html (Jinja2 -> PDF, 1 page)

Point d'entrée pipeline : generate_cv_for_job(job, outdir) ci-dessous.
"""

from pathlib import Path

import yaml

HERE = Path(__file__).parent


def load_master() -> dict:
    return yaml.safe_load((HERE / "profile_master.yaml").read_text(encoding="utf-8"))


def load_rules() -> dict:
    return yaml.safe_load((HERE / "country_rules.yaml").read_text(encoding="utf-8"))


def generate_cv_for_job(job: dict, outdir, hook=None):
    """Offre scorée de jobs_global.json -> CV ciblé (HTML + PDF) dans outdir.

    Renvoie (html_path, pdf_path, country). pdf_path est None si aucun moteur
    PDF n'est disponible (le HTML reste imprimable via le navigateur).
    `hook(offer, lang)` : accroche optionnelle (voir accroche.llm_accroche).
    """
    from .generate_cv import build_cv
    from .offer_mapping import job_to_offer

    offer = job_to_offer(job)
    country = offer["country"]
    html_path, pdf_path = build_cv(
        offer, country, load_master(), load_rules(), Path(outdir), hook=hook
    )
    return html_path, pdf_path, country
