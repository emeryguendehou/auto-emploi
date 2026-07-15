"""Cree une base Notion propre et adaptee au pipeline (a lancer UNE fois).

Pourquoi : l'ancienne base avait des proprietes incompletes/incoherentes
(Statut en type "status" qui exige des options pre-creees, pas de Tags, pas de
Categorie, pas de Type de contrat fiable). Ce script genere une base neuve dont
le schema correspond EXACTEMENT a ce qu'ecrit notion_db.create_page_properties,
avec toutes les options de select deja remplies depuis config.py.

Prerequis :
  1. Une integration Notion : https://www.notion.so/my-integrations
     -> recopier le token dans .env : NOTION_API_KEY=ntn_xxx
  2. Une page Notion qui servira de parent a la base.
     -> la PARTAGER avec l'integration (··· en haut a droite > Connexions)
     -> recopier son ID dans .env : NOTION_PARENT_PAGE_ID=xxxxx
        (l'ID = les 32 caracteres dans l'URL de la page)

Usage :
    poetry run python setup_notion.py
    # ou en passant la page parent en argument :
    poetry run python setup_notion.py <PARENT_PAGE_ID>

A la fin, le script affiche le NOTION_DB_ID a coller dans .env.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from notion_client import Client

import config

load_dotenv(Path(__file__).parent / ".env")

# Palette de couleurs Notion valides, parcourue en boucle pour les options.
_COLORS = ["blue", "green", "orange", "red", "purple", "pink",
           "yellow", "brown", "gray", "default"]


def _select(options: list[str]) -> dict:
    return {"select": {"options": [
        {"name": name, "color": _COLORS[i % len(_COLORS)]}
        for i, name in enumerate(options)
    ]}}


def build_schema() -> dict:
    """Schema de la base, options pre-remplies depuis config."""
    sources = [s.capitalize() if s != "wttj" else "WTTJ"
               for s in getattr(config, "SCRAPER_SOURCES", {}).keys()] or ["LinkedIn", "Indeed", "WTTJ"]
    contrats = ["CDI", "CDD", "Alternance", "Stage", "Inconnu"]
    categories = list(getattr(config, "JOB_CATEGORIES", ["Autre"]))
    orientations = ["Cyber", "IA", "Cyber+IA"]
    statuts = ["Prioritaire", "À étudier", "Ignoré"]

    return {
        "Titre": {"title": {}},
        "Entreprise": {"rich_text": {}},
        "Source": _select(sources),
        "Type de contrat": _select(contrats),
        "Categorie": _select(categories),
        "Orientation": _select(orientations),
        "Tags": {"multi_select": {"options": []}},  # auto-rempli a l'ecriture
        "Localisation": {"rich_text": {}},
        "Salaire": {"rich_text": {}},
        "Score match": {"number": {"format": "number"}},
        "Score global": {"number": {"format": "number"}},
        "Detail scores": {"rich_text": {}},
        "Statut": _select(statuts),
        "Resume IA": {"rich_text": {}},
        "Lien": {"url": {}},
        "Date ajout": {"date": {}},
        "CV genere": {"checkbox": {}},
        "Postulé": {"checkbox": {}},
        "Date candidature": {"date": {}},
        "CV": {"files": {}},
        "Job ID": {"rich_text": {}},
    }


def main() -> int:
    api_key = os.getenv("NOTION_API_KEY")
    if not api_key:
        print("[ERREUR] NOTION_API_KEY absent du .env")
        return 1

    parent_id = sys.argv[1] if len(sys.argv) > 1 else os.getenv("NOTION_PARENT_PAGE_ID")
    if not parent_id:
        print("[ERREUR] Page parent manquante.")
        print("  -> ajoute NOTION_PARENT_PAGE_ID=<id> dans .env")
        print("  -> ou lance : python setup_notion.py <PARENT_PAGE_ID>")
        print("  (et n'oublie pas de PARTAGER la page avec ton integration)")
        return 1

    # API 2025-09-03 : les proprietes vivent sur la DATA SOURCE. On cree donc la
    # base (data source par defaut = juste "Name" titre), puis on POUSSE le schema
    # complet sur la data source (renommage "Name"->"Titre" + ajout du reste).
    client = Client(auth=api_key, notion_version="2025-09-03")

    print(f"Creation de la base sous la page parent {parent_id}...")
    try:
        db = client.databases.create(
            parent={"type": "page_id", "page_id": parent_id},
            title=[{"type": "text", "text": {"content": "Suivi Alternance (auto)"}}],
        )
    except Exception as e:
        print(f"[ERREUR] Creation echouee : {e}")
        print("  Verifie que la page parent est bien PARTAGEE avec l'integration.")
        return 1

    db_id = db["id"]
    sources = db.get("data_sources") or []
    if not sources:
        print("[ERREUR] Base creee sans data source (API inattendue).")
        return 1
    ds_id = sources[0]["id"]

    print("Pose du schema sur la data source...")
    schema = build_schema()
    payload = {"Name": {"name": "Titre"}}  # renomme le titre (pas de 2e title)
    for k, v in schema.items():
        if k != "Titre":
            payload[k] = v
    try:
        client.data_sources.update(data_source_id=ds_id, properties=payload)
    except Exception as e:
        print(f"[ERREUR] Pose du schema echouee : {e}")
        return 1

    print("\n[OK] Base creee et schema pose !")
    print(f"  NOTION_DB_ID={db_id}")
    print("\nColle cette ligne dans ton .env (remplace l'ancien NOTION_DB_ID),")
    print("puis relance le pipeline : poetry run python main.py --phase notion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
