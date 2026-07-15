import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from notion_client import Client

import config
import utils

logger = utils.setup_logging("notion_db")

# API Notion 2025-09-03 : les proprietes vivent sur la DATA SOURCE (plus sur
# l'objet database). Une base peut contenir plusieurs data sources ; on ecrit
# dans la premiere. Le parent d'une page devient {"type":"data_source_id", ...}.
NOTION_VERSION = "2025-09-03"
_DATA_SOURCE_CACHE: Dict[str, str] = {}

# Schema de la base Notion. Sert a la fois de reference et de source pour le
# script setup_notion.py qui cree une base propre. Tout est en select/multi_select
# (et non "status") car ces types auto-creent leurs options a l'ecriture.
NOTION_PROPERTIES = {
    "Titre": {"title": {}},
    "Entreprise": {"rich_text": {}},
    "Source": {"select": {}},
    "Type de contrat": {"select": {}},
    "Categorie": {"select": {}},
    "Orientation": {"select": {}},
    "Tags": {"multi_select": {}},
    "Localisation": {"rich_text": {}},
    "Salaire": {"rich_text": {}},
    "Score match": {"number": {"format": "number"}},
    "Score global": {"number": {"format": "number"}},
    "Detail scores": {"rich_text": {}},
    "Statut": {"select": {}},
    "Resume IA": {"rich_text": {}},
    "Lien": {"url": {}},
    "Date ajout": {"date": {}},
    "CV genere": {"checkbox": {}},
    "Postulé": {"checkbox": {}},
    "Date candidature": {"date": {}},
    "CV": {"files": {}},
    "Job ID": {"rich_text": {}},
}


def get_notion_client() -> Client:
    api_key = utils.get_env("NOTION_API_KEY")
    return Client(auth=api_key, notion_version=NOTION_VERSION)


def resolve_data_source_id(client: Client, db_id: str) -> str:
    """id de la data source (API 2025) a partir de l'id de base. Mis en cache.

    Accepte aussi un id qui EST deja une data source (retrieve echoue en base,
    on renvoie l'id tel quel)."""
    if db_id in _DATA_SOURCE_CACHE:
        return _DATA_SOURCE_CACHE[db_id]
    try:
        db = client.databases.retrieve(database_id=db_id)
        sources = db.get("data_sources") or []
        ds_id = sources[0]["id"] if sources else db_id
    except Exception:
        ds_id = db_id  # deja une data source, ou API ancienne
    _DATA_SOURCE_CACHE[db_id] = ds_id
    return ds_id


def upload_file(client: Client, path: Path) -> Optional[str]:
    """Televerse un fichier local vers Notion (single-part) -> file_upload_id.

    Notion File Upload API (2025) : create -> send. Le fichier est ensuite
    referencable dans une propriete 'files' ou un bloc via son id. None si echec."""
    try:
        content_type = "application/pdf" if path.suffix.lower() == ".pdf" else "application/octet-stream"
        fu = client.file_uploads.create(
            mode="single_part", filename=path.name, content_type=content_type,
        )
        client.file_uploads.send(
            file_upload_id=fu["id"],
            file=(path.name, path.read_bytes(), content_type),
        )
        return fu["id"]
    except Exception as e:
        logger.error(f"Upload Notion echoue ({path.name}): {e}")
        return None


def _contract_label(job: Dict[str, Any]) -> str:
    """Type de contrat : valeur deja calculee si presente, sinon classifieur."""
    return job.get("type_contrat") or utils.contract_label(job)


def _score_breakdown(job: Dict[str, Any]) -> str:
    """Ligne lisible du detail multi-criteres pour Notion."""
    return (
        f"Fit {job.get('score', 0)} | "
        f"Remu {job.get('note_remuneration', 0)} | "
        f"Flex {job.get('note_flexibilite', 0)} | "
        f"Boite {job.get('note_entreprise', 0)} | "
        f"Evol {job.get('note_evolution', 0)}"
    )


def _tags_for_notion(job: Dict[str, Any]) -> List[Dict[str, str]]:
    tags = job.get("tags") or []
    if not isinstance(tags, list):
        return []
    # Notion : option name <= 100 chars, pas de virgule. On nettoie et dedoublonne.
    clean, seen = [], set()
    for t in tags:
        name = str(t).replace(",", " ").strip()[:100]
        if name and name.lower() not in seen:
            seen.add(name.lower())
            clean.append({"name": name})
    return clean[:10]


def create_page_properties(
    job: Dict[str, Any],
    statut: str = "À étudier",
    type_contrat: Optional[str] = None,
    postule: bool = False,
    date_postule: Optional[str] = None,
    cv_file_upload_id: Optional[str] = None,
) -> Dict[str, Any]:
    if type_contrat is None:
        type_contrat = _contract_label(job)

    props: Dict[str, Any] = {
        "Titre": {"title": [{"text": {"content": (job.get("titre") or "Sans titre")[:2000]}}]},
        "Entreprise": {"rich_text": [{"text": {"content": (job.get("entreprise") or "")[:2000]}}]},
        "Source": {"select": {"name": job.get("source", "LinkedIn")}},
        "Type de contrat": {"select": {"name": type_contrat}},
        "Categorie": {"select": {"name": job.get("categorie", "Autre")}},
        "Orientation": {"select": {"name": job.get("orientation", "SWE/Web")}},
        "Tags": {"multi_select": _tags_for_notion(job)},
        "Localisation": {"rich_text": [{"text": {"content": (job.get("localisation") or "")[:2000]}}]},
        "Salaire": {"rich_text": [{"text": {"content": (job.get("salaire") or "Non précisé")[:200]}}]},
        "Score match": {"number": job.get("score", 0)},
        "Score global": {"number": job.get("score_global", job.get("score", 0))},
        "Detail scores": {"rich_text": [{"text": {"content": _score_breakdown(job)}}]},
        "Statut": {"select": {"name": statut}},
        "Resume IA": {"rich_text": [{"text": {"content": (job.get("resume_ia") or "")[:2000]}}]},
        "Lien": {"url": job.get("lien") or None},
        "Date ajout": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
        "CV genere": {"checkbox": bool(job.get("cv_genere", False))},
        "Postulé": {"checkbox": bool(postule)},
        "Job ID": {"rich_text": [{"text": {"content": (job.get("job_id") or "")[:2000]}}]},
    }
    if date_postule:
        props["Date candidature"] = {"date": {"start": date_postule}}
    if cv_file_upload_id:
        props["CV"] = {"files": [{
            "type": "file_upload",
            "file_upload": {"id": cv_file_upload_id},
            "name": "CV.pdf",
        }]}
    return props


def create_page_blocks(
    job: Dict[str, Any]
) -> List[Dict[str, Any]]:
    blocks = []

    resume = job.get("resume_ia", "")
    if resume:
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"text": {"content": "Résumé IA"}}]
            }
        })
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"text": {"content": resume[:1950]}}]
            }
        })

    description = job.get("description", "")
    if description:
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"text": {"content": "Description de l'offre"}}]
            }
        })

        text = description[:10000]
        while text:
            chunk = text[:1950]
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": chunk}}]
                }
            })
            text = text[1950:]

    return blocks


async def create_page(
    job: Dict[str, Any],
    db_id: str,
    statut: str = "À étudier",
) -> Optional[str]:
    client = get_notion_client()

    properties = create_page_properties(job, statut)
    children = create_page_blocks(job)

    try:
        ds_id = resolve_data_source_id(client, db_id)
        response = client.pages.create(
            parent={"type": "data_source_id", "data_source_id": ds_id},
            properties=properties,
            children=children,
        )

        page_id = response.get("id")
        logger.info(f"Created Notion page: {job.get('titre', '')[:40]} ({page_id})")
        return page_id

    except Exception as e:
        logger.error(f"Failed to create Notion page: {e}")
        return None


async def update_page(
    page_id: str,
    job: Dict[str, Any]
) -> bool:
    client = get_notion_client()

    properties = {
        "Score match": {"number": job.get("score", 0)},
        "Statut": {"select": {"name": job.get("statut", "À étudier")}},
    }

    try:
        client.pages.update(page_id=page_id, properties=properties)
        logger.info(f"Updated Notion page: {page_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to update Notion page: {e}")
        return False


async def set_cv_genere(page_id: str, value: bool = True) -> bool:
    """Coche la case 'CV genere' d'une page Notion existante."""
    client = get_notion_client()
    try:
        client.pages.update(
            page_id=page_id,
            properties={"CV genere": {"checkbox": value}},
        )
        return True
    except Exception as e:
        logger.error(f"Failed to set CV genere on {page_id}: {e}")
        return False


async def add_job_to_notion(
    job: Dict[str, Any],
    db_id: Optional[str] = None,
) -> Optional[str]:
    if not db_id:
        db_id = utils.get_env("NOTION_DB_ID")

    if not db_id:
        logger.error("No Notion DB ID provided")
        return None

    score = job.get("score", 0) or 0
    if score >= config.SCORE_PRIORITAIRE:
        statut = "Prioritaire"
    elif score >= config.SCORE_SEUIL:
        statut = "À étudier"
    else:
        logger.info(f"Job ignored (score {score})")
        return None

    return await create_page(job, db_id, statut)


def add_candidature_to_notion(job: Dict[str, Any]) -> Dict[str, Any]:
    """Pousse une CANDIDATURE (offre postulée) dans Notion, avec son CV attaché.

    Renvoie {page_id, cv_upload_id, cv_path} : cv_path n'est renseigné QUE si le CV
    a bien été téléversé et attaché (l'appelant peut alors supprimer le fichier local).
    """
    client = get_notion_client()
    db_id = utils.get_env("NOTION_DB_ID")
    ds_id = resolve_data_source_id(client, db_id)

    score = job.get("score", 0) or 0
    if score >= config.SCORE_PRIORITAIRE:
        statut = "Prioritaire"
    elif score >= config.SCORE_SEUIL:
        statut = "À étudier"
    else:
        statut = "Ignoré"

    # Téléverse le CV s'il existe sur disque.
    cv_upload_id, cv_path = None, None
    gf = job.get("generated_files") or {}
    raw = gf.get("cv") or ""
    if raw:
        p = Path(raw)
        if p.exists():
            cv_upload_id = upload_file(client, p)
            if cv_upload_id:
                cv_path = p

    props = create_page_properties(
        job, statut,
        postule=True,
        date_postule=job.get("date_postule"),
        cv_file_upload_id=cv_upload_id,
    )
    resp = client.pages.create(
        parent={"type": "data_source_id", "data_source_id": ds_id},
        properties=props,
        children=create_page_blocks(job),
    )
    page_id = resp.get("id")
    logger.info(f"Candidature Notion: {job.get('entreprise','?')[:30]} ({page_id}) CV={'oui' if cv_path else 'non'}")
    return {"page_id": page_id, "cv_upload_id": cv_upload_id, "cv_path": str(cv_path) if cv_path else ""}


def _pending_cv_path(job: Dict[str, Any]) -> Optional[Path]:
    """Chemin du CV PDF local de l'offre s'il existe encore sur disque."""
    gf = job.get("generated_files") or {}
    raw = gf.get("cv") or ""
    if raw:
        p = Path(raw)
        if p.exists():
            return p
    return None


def _delete_local_cv(path_str: str) -> bool:
    """Supprime un CV local UNIQUEMENT si c'est un PDF sous data/generated.

    Règle Emery : un CV joint à Notion est retiré du disque. Garde-fou strict pour
    ne jamais toucher un fichier ailleurs (ex. racine Downloads = docs perso)."""
    if not path_str:
        return False
    try:
        p = Path(path_str).resolve()
        gen = (config.DATA_DIR / "generated").resolve()
        if p.suffix.lower() == ".pdf" and p.exists() and gen in p.parents:
            p.unlink()
            return True
    except Exception:
        pass
    return False


def sync_candidature(job_id: str, postule: bool) -> None:
    """Reflète l'état 'postulé' d'une offre dans Notion (best-effort, non bloquant).

    - postule=True  : crée la page Notion si absente, sinon coche « Postulé » (+ date)
      et attache le CV s'il n'y est pas déjà. Un CV attaché est supprimé du disque.
    - postule=False : décoche « Postulé » sur la page existante (page conservée).

    Toute erreur (Notion injoignable, clés absentes…) est absorbée : la source de
    vérité reste le JSON local déjà écrit par set_job_postule.
    """
    try:
        from data_loader import load_jobs_global, update_job_notion
        data = load_jobs_global()
        job = data.get("jobs", {}).get(job_id)
        if not job:
            return
        client = get_notion_client()
        page_id = job.get("notion_page_id")

        # Décochage : on désactive juste le flag sur la page (réversible).
        if not postule:
            if page_id:
                client.pages.update(page_id=page_id, properties={"Postulé": {"checkbox": False}})
            return

        # Pas encore dans Notion -> création complète (upload CV + suppression locale).
        if not page_id:
            res = add_candidature_to_notion(job)
            if res.get("page_id"):
                update_job_notion(job_id, res["page_id"])
                _delete_local_cv(res.get("cv_path", ""))
            return

        # Page existante -> coche Postulé (+ date) et attache le CV s'il manque.
        props: Dict[str, Any] = {"Postulé": {"checkbox": True}}
        if job.get("date_postule"):
            props["Date candidature"] = {"date": {"start": job["date_postule"]}}

        cv_path = _pending_cv_path(job)
        cv_attached = False
        if cv_path:
            page = client.pages.retrieve(page_id=page_id)
            already = bool(page.get("properties", {}).get("CV", {}).get("files"))
            if not already:
                up = upload_file(client, cv_path)
                if up:
                    props["CV"] = {"files": [{
                        "type": "file_upload", "file_upload": {"id": up}, "name": "CV.pdf",
                    }]}
                    cv_attached = True

        client.pages.update(page_id=page_id, properties=props)
        if cv_attached:
            _delete_local_cv(str(cv_path))
    except Exception as e:
        logger.error(f"Sync Notion candidature échoué ({str(job_id)[:40]}): {e}")


async def add_jobs_batch(
    jobs: List[Dict[str, Any]],
    db_id: Optional[str] = None
) -> List[str]:
    if not db_id:
        db_id = utils.get_env("NOTION_DB_ID")

    page_ids = []
    for job in jobs:
        page_id = await add_job_to_notion(job, db_id)
        if page_id:
            page_ids.append(page_id)

        await asyncio.sleep(0.5)

    return page_ids