# -*- coding: utf-8 -*-
"""
llm_rotation.py — Énumération dynamique des (modèle, clé API) disponibles.

Balaye le .env : toutes les clés GROQ_API_KEY_* puis GEMINI_API_KEY_* sont
candidates, dans l'ordre. Utilisé par accroche.py et gap_analysis.py — le
premier appel qui aboutit gagne (les 429/erreurs réseau passent au suivant).
"""

import os

GROQ_MODEL = "groq/llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini/gemini-2.5-flash-lite"


def candidates():
    """Liste ordonnée de (model, api_key) d'après les clés présentes en env."""
    out = []
    for prefix, model in (("GROQ_API_KEY_", GROQ_MODEL),
                          ("GEMINI_API_KEY_", GEMINI_MODEL)):
        for i in range(1, 10):
            key = os.getenv(f"{prefix}{i}")
            if key:
                out.append((model, key))
    return out
