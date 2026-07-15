# -*- coding: utf-8 -*-
"""
offer_mapping.py — Convertit une offre réelle de jobs_global.json vers le
`offer_dict` attendu par generate_cv.build_cv(), et déduit le marché cible
(`country` : fr | ca-qc | ca-en | intl).

Déduction du pays :
  1. champ `zone` si présent (persisté par le scraper depuis juillet 2026) ;
  2. sinon analyse de `localisation` (France / provinces canadiennes) ;
  3. sinon `intl`.
Pour le Canada : ca-qc si l'offre est rédigée en français, sinon ca-en.
"""

import re
import unicodedata


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Mots-outils très fréquents, discriminants FR vs EN.
_FR_HINTS = {"le", "la", "les", "des", "une", "vous", "nous", "pour", "dans",
             "avec", "sur", "est", "sont", "votre", "nos", "au", "aux", "et",
             "ou", "chez", "poste", "equipe", "entreprise", "missions"}
_EN_HINTS = {"the", "and", "you", "with", "for", "our", "are", "will", "your",
             "of", "to", "in", "we", "team", "work", "role", "this", "as",
             "on", "is", "be"}

_CANADA_MARKERS = [
    "canada", "quebec", ", qc", "montreal", "chicoutimi", "saguenay", "laval",
    "gatineau", "sherbrooke", "trois-rivieres", "ontario", ", on", "toronto",
    "ottawa", "british columbia", "colombie-britannique", ", bc", "vancouver",
    "alberta", ", ab", "calgary", "edmonton", "manitoba", "winnipeg",
    "saskatchewan", "nova scotia", "nouvelle-ecosse", "new brunswick",
    "nouveau-brunswick", "newfoundland", "terre-neuve",
]


def detect_language(text: str) -> str:
    """'fr' ou 'en' par comptage de mots-outils (heuristique robuste et locale)."""
    words = re.findall(r"[a-z']+", _norm(text))
    fr = sum(1 for w in words if w in _FR_HINTS)
    en = sum(1 for w in words if w in _EN_HINTS)
    return "fr" if fr >= en else "en"


def deduce_country(job: dict) -> str:
    """fr | ca-qc | ca-en | intl à partir de zone/localisation/description."""
    zone = _norm(job.get("zone", ""))
    loc = _norm(job.get("localisation", ""))
    text = (job.get("titre", "") or "") + " " + (job.get("description", "") or "")

    def ca_variant():
        return "ca-qc" if detect_language(text) == "fr" else "ca-en"

    if zone:
        if "france" in zone:
            return "fr"
        if "canada" in zone:
            return ca_variant()
        # Zone "europe"/"intl"/autre : le pays réel dépend de la localisation
        # (une offre Europe basée à Paris doit suivre les règles FR), on laisse
        # donc l'analyse de `localisation` ci-dessous trancher.

    # France : mention explicite ou département entre parenthèses "Paris (75)".
    if "france" in loc or re.search(r"\(\d{2,3}\)", loc):
        return "fr"
    if any(m in loc for m in _CANADA_MARKERS):
        return ca_variant()
    return "intl"


def job_to_offer(job: dict) -> dict:
    """Offre scorée de jobs_global.json -> offer_dict pour build_cv()."""
    tags = job.get("tags")
    return {
        "title": job.get("titre", ""),
        "company": job.get("entreprise", ""),
        "description": job.get("description", "") or "",
        "category": job.get("categorie", "") or "",
        "keywords": tags if isinstance(tags, list) else [],
        "country": deduce_country(job),
    }
