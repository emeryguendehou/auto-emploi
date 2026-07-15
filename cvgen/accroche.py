# -*- coding: utf-8 -*-
"""
accroche.py — Hook LLM pour l'accroche du CV (SEUL texte rédigé par un LLM).

Contrat strict (garde-fou anti-hallucination) :
  - interdiction d'inventer une expérience, un outil ou un chiffre ;
  - se limiter au lien entre le profil fourni et l'offre ;
  - 35 mots max, même langue que le CV.

En cas d'échec LLM (quota, réseau, sortie non conforme), fallback statique
honnête — le CV reste valide sans accroche personnalisée.
"""

import os
import re

SYSTEM_PROMPT = {
    "fr": (
        "Tu complètes le profil d'un CV par UNE phrase d'accroche ciblée sur "
        "l'offre. RÈGLES ABSOLUES : n'invente JAMAIS une expérience, un outil, "
        "une technologie ou un chiffre ; contente-toi de relier le profil "
        "fourni à l'offre ; 35 mots MAXIMUM ; en français ; pas de guillemets, "
        "pas de première personne du singulier au début (commence par un nom "
        "ou un adjectif, ex. « Motivé pour... », « Profil aligné sur... »). "
        "Réponds UNIQUEMENT avec la phrase."
    ),
    "en": (
        "You add ONE targeted hook sentence to a resume profile. ABSOLUTE "
        "RULES: NEVER invent an experience, tool, technology or number; only "
        "connect the provided profile to the job offer; 35 words MAXIMUM; in "
        "English; no quotes. Respond ONLY with the sentence."
    ),
}

# Rotation dynamique sur toutes les clés GROQ/GEMINI du .env.
try:
    from .llm_rotation import candidates
except ImportError:
    from llm_rotation import candidates

MAX_WORDS = 45  # marge au-delà des 35 demandés ; sinon on rejette


def _fallback(offer: dict, lang: str) -> str:
    title = offer.get("title", "")
    if lang == "fr":
        return f"Candidature ciblée pour le poste de {title}."
    return f"Applying for the {title} role."


def _clean(text: str) -> str:
    text = (text or "").strip().strip('"').strip("«»").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def llm_accroche(offer: dict, lang: str, profile_base: str = "") -> str:
    """Accroche LLM (35 mots max) ou fallback statique. Signature compatible
    avec le paramètre `hook` de build_cv (offer, lang)."""
    try:
        from litellm import completion
    except ImportError:
        return _fallback(offer, lang)

    user = (
        f"PROFIL DU CANDIDAT (source de vérité, ne rien ajouter au-delà) :\n"
        f"{profile_base or offer.get('_profile_base', '')}\n\n"
        f"OFFRE VISÉE :\n"
        f"- Poste : {offer.get('title', '')}\n"
        f"- Entreprise : {offer.get('company', '')}\n"
        f"- Extrait : {(offer.get('description') or '')[:800]}"
    )

    for model, api_key in candidates():
        try:
            resp = completion(
                model=model,
                api_key=api_key,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT.get(lang, SYSTEM_PROMPT["en"])},
                    {"role": "user", "content": user},
                ],
                max_tokens=120,
                temperature=0.3,
            )
            text = _clean(resp.choices[0].message.content)
            if text and len(text.split()) <= MAX_WORDS and "\n" not in text:
                return text
        except Exception:
            continue
    return _fallback(offer, lang)
