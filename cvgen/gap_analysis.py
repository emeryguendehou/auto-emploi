# -*- coding: utf-8 -*-
"""
gap_analysis.py — Note d'analyse d'écarts offre ↔ CV, générée par LLM.

Le LLM ne touche JAMAIS au CV : il le lit (comme un recruteur) et produit un
`notes_offre.md` à côté du PDF — points forts à appuyer, mots-clés absents,
préparation d'entretien, drapeaux. L'honnêteté est imposée par le prompt :
interdiction de recommander d'ajouter au CV une compétence non possédée.
"""

import os
import re
from pathlib import Path

from .llm_rotation import candidates

SYSTEM_PROMPT = """Tu es un coach candidature senior, honnête et direct.
On te donne une OFFRE d'emploi et le CV (déjà finalisé) d'un candidat.
Ta mission : une note d'analyse en français, format Markdown, 4 sections :

## Points forts à appuyer
Les 3-5 éléments du CV qui matchent le mieux l'offre (et pourquoi).

## Écarts et mots-clés absents
Les exigences de l'offre que le CV ne couvre pas ou peu. Pour chacune :
est-elle comblable avec le vécu réel du candidat (reformulation), ou à
assumer en entretien ? INTERDICTION ABSOLUE de recommander d'ajouter au CV
une compétence, un outil ou une expérience que le CV ne démontre pas déjà.

## Préparation d'entretien
2-4 questions probables du recruteur sur les écarts, avec une piste de
réponse honnête s'appuyant sur les équivalents présents dans le CV.

## Drapeaux
Points de vigilance sur l'offre elle-même (localisation ambiguë, séniorité
exigée vs profil, langue, salaire absent…). Si rien : « RAS ».

Sois concret et bref (max ~350 mots). Pas de flatterie."""


def _cv_text_from_html(html_path) -> str:
    html = Path(html_path).read_text(encoding="utf-8")
    text = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def write_gap_notes(job: dict, html_path, outdir) -> "Path | None":
    """Écrit notes_offre.md dans outdir. Best-effort : None si aucun LLM."""
    try:
        from litellm import completion
    except ImportError:
        return None

    user = (
        f"OFFRE\n"
        f"Titre : {job.get('titre', '')}\n"
        f"Entreprise : {job.get('entreprise', '')}\n"
        f"Localisation : {job.get('localisation', '')}\n"
        f"Description :\n{(job.get('description') or '')[:6000]}\n\n"
        f"CV DU CANDIDAT (texte extrait)\n{_cv_text_from_html(html_path)[:6000]}"
    )

    for model, api_key in candidates():
        try:
            resp = completion(
                model=model, api_key=api_key,
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": user}],
                max_tokens=900, temperature=0.3,
            )
            text = (resp.choices[0].message.content or "").strip()
            if len(text) < 100:
                continue
            path = Path(outdir) / "notes_offre.md"
            header = (f"# Analyse d'écarts — {job.get('titre', '')} @ "
                      f"{job.get('entreprise', '')}\n\n"
                      f"> Générée par LLM ({model}) : à lire avant de postuler, "
                      f"le CV n'est jamais modifié par cette analyse.\n\n")
            path.write_text(header + text + "\n", encoding="utf-8")
            return path
        except Exception:
            continue
    return None
