"""Exporte les offres scorées dans un CSV ouvrable dans Excel.

Trié par score global décroissant (meilleures d'abord). Ouvrable directement
dans Excel (encodage utf-8-sig + séparateur ';' -> accents et colonnes OK).

Usage :
    poetry run python export_csv.py            # offres scorées (score != None)
    poetry run python export_csv.py --all      # toutes les offres (même à traiter)
    poetry run python export_csv.py --min 60   # seulement score >= 60
"""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
GLOBAL_FILE = BASE / "data" / "jobs_global.json"


def statut(score) -> str:
    s = score or 0
    if score is None:
        return "À traiter"
    if s == 0:
        return "Éliminée"
    if s >= 80:
        return "Prioritaire"
    if s >= 60:
        return "À étudier"
    return "Ignorée"


COLUMNS = [
    ("Score global", "score_global"),
    ("Fit", "score"),
    ("Statut", None),
    ("Catégorie", "categorie"),
    ("Orientation", "orientation"),
    ("Contrat", "type_contrat"),
    ("Entreprise", "entreprise"),
    ("Poste", "titre"),
    ("Localisation", "localisation"),
    ("Salaire", "salaire"),
    ("Rémunération", "note_remuneration"),
    ("Flexibilité", "note_flexibilite"),
    ("Note entreprise", "note_entreprise"),
    ("Évolution", "note_evolution"),
    ("Source", "source"),
    ("Lien", "lien"),
    ("Résumé IA", "resume_ia"),
    ("Raisons", "raisons_score"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Export CSV des offres")
    ap.add_argument("--all", action="store_true", help="inclure les offres non scorées")
    ap.add_argument("--min", type=int, default=None, help="score minimum à inclure")
    args = ap.parse_args()

    data = json.load(open(GLOBAL_FILE, encoding="utf-8"))
    jobs = list(data.get("jobs", {}).values())

    if not args.all:
        jobs = [j for j in jobs if j.get("score") is not None]
    if args.min is not None:
        jobs = [j for j in jobs if (j.get("score") or 0) >= args.min]

    jobs.sort(key=lambda j: (j.get("score_global") or 0, j.get("score") or 0), reverse=True)

    out = BASE / "data" / f"offres_{datetime.now():%Y%m%d_%H%M}.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([label for label, _ in COLUMNS])
        for j in jobs:
            row = []
            for label, key in COLUMNS:
                row.append(statut(j.get("score")) if key is None else j.get(key, ""))
            w.writerow(row)

    print(f"Export OK : {out}  ({len(jobs)} offres)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
