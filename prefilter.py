# -*- coding: utf-8 -*-
"""
prefilter.py — Pré-filtre déterministe appliqué AVANT le scoring LLM.

Objectif : écarter à 0 les offres structurellement hors-cible sans dépenser
d'appel LLM (donc de quota). Complète TITLE_EXCLUSION_LIST (titres senior) avec :
  - contrat non CDI/CDD (mission/gig/horaire) ;
  - expérience minimale > config.PREFILTER_MAX_EXP_YEARS ;
  - poste étranger (zone != France) sans remote mondial explicite.

Tout est piloté par config (éditable via le dashboard) : PREFILTER_ENABLED,
PREFILTER_CONTRACT_TERMS, PREFILTER_MAX_EXP_YEARS,
PREFILTER_FOREIGN_REQUIRE_GLOBAL_REMOTE, PREFILTER_GLOBAL_REMOTE_TERMS.
Rien n'est codé en dur ici : les règles vivent dans config.
"""

import re

import config


def _match_any(terms, text: str):
    """Premier terme (regex, sinon sous-chaîne) trouvé dans text, ou None."""
    for term in terms or []:
        try:
            if re.search(term, text, re.IGNORECASE):
                return term
        except re.error:
            if term.lower() in text.lower():
                return term
    return None


# Motifs d'expérience : on ne déclenche QUE si le nombre d'années est rattaché à
# un contexte d'expérience (évite les faux positifs type « depuis plus de 20 ans,
# notre société... » = ancienneté de l'entreprise, pas exigence candidat).
_EXP_PATTERNS = [
    r"(\d{1,2})\s*\+\s*years",
    r"(\d{1,2})\s*(?:to|-|–|à)\s*\d{1,2}\s*(?:years|ans)",
    r"(?:minimum|at least|au moins|min\.?)\s*(?:of\s*)?(\d{1,2})\s*(?:years|ans)",
    r"(\d{1,2})\s*(?:years|ans)\s*(?:of\s+experience|d['’]exp)",
    r"(\d{1,2})\s*(?:years|ans)\s+minimum",
]


def _exp_exceeds(text: str, max_years: int):
    """Renvoie l'exigence (str) si une expérience mini > max_years est trouvée."""
    for pat in _EXP_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            try:
                low = int(m.group(1))
            except (TypeError, ValueError):
                continue
            if low > max_years:
                return f"{low}+ ans"
    return None


def check_prefilter(job: dict):
    """Renvoie une raison d'élimination (str) si l'offre doit être écartée à 0
    sans passer par le LLM, sinon None. Respecte config (dynamique)."""
    if not getattr(config, "PREFILTER_ENABLED", False):
        return None

    titre = job.get("titre", "") or ""
    desc = job.get("description", "") or ""
    text = f"{titre} {desc}"

    # 1) Contrat non CDI/CDD
    term = _match_any(getattr(config, "PREFILTER_CONTRACT_TERMS", []), text)
    if term:
        return f"contrat non CDI/CDD ({term})"

    # 2) Expérience minimale > seuil
    max_years = getattr(config, "PREFILTER_MAX_EXP_YEARS", 3)
    exp = _exp_exceeds(desc, max_years)
    if exp:
        return f"expérience > {max_years} ans exigée ({exp})"

    # 3) Étranger HORS zones locales, sans remote mondial explicite
    if getattr(config, "PREFILTER_FOREIGN_REQUIRE_GLOBAL_REMOTE", False):
        zone = (job.get("zone") or "").strip().lower()
        local = [z.lower() for z in getattr(config, "PREFILTER_LOCAL_ZONES", ["france"])]
        if zone and not any(zone.startswith(z) for z in local):
            if not _match_any(getattr(config, "PREFILTER_GLOBAL_REMOTE_TERMS", []), text):
                return (f"poste étranger ({job.get('zone')}) sans remote mondial "
                        f"réalisable depuis la France")

    return None
