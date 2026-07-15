import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

import config

THIS_DIR = Path(__file__).resolve().parent
BASE_DIR = THIS_DIR
DATA_DIR = BASE_DIR / "data"
GLOBAL_FILE = DATA_DIR / "jobs_global.json"

load_dotenv(BASE_DIR / ".env")

import utils
logger = utils.setup_logging("data_loader")


def generate_job_id(job: Dict[str, Any]) -> str:
    """Generate unique job ID from titre + entreprise + localisation."""
    titre = job.get("titre", "").lower().strip()
    entreprise = job.get("entreprise", "").lower().strip()
    localisation = job.get("localisation", "").lower().strip()
    return f"{titre}|{entreprise}|{localisation}"


def load_jobs_global() -> Dict[str, Any]:
    """Load the global jobs file."""
    if GLOBAL_FILE.exists():
        try:
            with open(GLOBAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"Loaded {len(data.get('jobs', {}))} jobs from global file")
                return data
        except json.JSONDecodeError as e:
            logger.warning(f"Corrupted global file, creating new: {e}")
            return create_empty_global()
    return create_empty_global()


def create_empty_global() -> Dict[str, Any]:
    """Create empty global data structure."""
    return {
        "jobs": {},
        "metadata": {
            "created": datetime.now().strftime("%Y-%m-%d"),
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "total_jobs": 0,
            "processed": 0,
            "notion_added": 0,
        }
    }


def save_jobs_global(data: Dict[str, Any]) -> None:
    """Save the global jobs file."""
    data["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    data["metadata"]["total_jobs"] = len(data.get("jobs", {}))
    
    with open(GLOBAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(data['jobs'])} jobs to global file")


def add_jobs_to_global(new_jobs: List[Dict[str, Any]]) -> Dict[str, int]:
    """Add new jobs to global file with deduplication by job_id (titre+entreprise+localisation).
    
    Returns:
        Dict with counts: {"added": N, "updated": M, "duplicates": K}
    """
    data = load_jobs_global()
    jobs_dict = data.get("jobs", {})
    
    stats = {"added": 0, "updated": 0, "duplicates": 0}
    today = datetime.now().strftime("%Y-%m-%d")
    
    for job in new_jobs:
        job_id = generate_job_id(job)
        if not job_id:
            continue

        # Classification robuste du type de contrat (source unique de verite).
        keep, type_contrat = utils.is_desired_contract(job)
        job["type_contrat"] = utils.CONTRACT_LABELS.get(type_contrat, "Inconnu")
        if not keep:
            # Type connu mais hors JOB_TYPES (cdi/cdd/stage) -> exclu definitif.
            logger.info(f"[CONTRAT FILTER] '{type_contrat}' -> {job.get('titre', '')[:60]}")
            job["score"] = 0
            job["raisons_score"] = f"Exclu post-scrape: contrat '{type_contrat}' hors cible"
            job["resume_ia"] = f"Exclu: contrat {job['type_contrat']} (non desire)"

        if job_id in jobs_dict:
            existing = jobs_dict[job_id]
            if existing.get("date_updated") != today:
                existing["date_updated"] = today
                jobs_dict[job_id] = {**existing, **job, "date_updated": today, "job_id": job_id}
                stats["updated"] += 1
            else:
                stats["duplicates"] += 1
        else:
            jobs_dict[job_id] = {
                **job,
                "job_id": job_id,
                "date_scraped": job.get("date_scraped", today),
                "date_updated": today,
                "score": job.get("score", None),
                "notion_page_id": job.get("notion_page_id", None),
                "statut": job.get("statut", "À étudier"),
            }
            stats["added"] += 1
    
    data["jobs"] = jobs_dict
    save_jobs_global(data)
    
    logger.info(f"Jobs: +{stats['added']} added, ~{stats['updated']} updated, {stats['duplicates']} duplicates")
    return stats


def get_unprocessed_jobs() -> List[Dict[str, Any]]:
    """Get jobs that haven't been processed by LLM yet."""
    data = load_jobs_global()
    unprocessed = []
    
    for url, job in data.get("jobs", {}).items():
        if job.get("score") is None:
            unprocessed.append(job)
    
    logger.info(f"Found {len(unprocessed)} unprocessed jobs")
    return unprocessed


def get_jobs_for_notion() -> List[Dict[str, Any]]:
    """Get jobs with score >= SCORE_NOTION that haven't been added to Notion."""
    data = load_jobs_global()
    to_add = []
    
    for url, job in data.get("jobs", {}).items():
        score = job.get("score") or 0
        notion_id = job.get("notion_page_id")
        
        if score >= config.SCORE_NOTION and not notion_id:
            to_add.append(job)
    
    logger.info(f"Found {len(to_add)} jobs ready for Notion (score >= {config.SCORE_NOTION}, no page)")
    return to_add


def update_job_score(job_id: str, score: int, resume_ia: str, raisons: str, tags: List[str], orientation: str = "SWE/Web", categorie: str = "Autre", salaire: str = "Non précisé", extra: Optional[Dict[str, Any]] = None) -> None:
    """Update a job with LLM score. `extra` : champs additionnels (score_global, notes...)."""
    data = load_jobs_global()
    jobs = data.get("jobs", {})

    if job_id in jobs:
        jobs[job_id]["score"] = score
        jobs[job_id]["resume_ia"] = resume_ia
        jobs[job_id]["raisons_score"] = raisons
        jobs[job_id]["tags"] = tags
        jobs[job_id]["orientation"] = orientation
        jobs[job_id]["categorie"] = categorie
        jobs[job_id]["salaire"] = salaire
        if extra:
            for k, v in extra.items():
                jobs[job_id][k] = v
        data["metadata"]["processed"] = data["metadata"].get("processed", 0) + 1
        save_jobs_global(data)


def get_jobs_for_generation(threshold: int = None) -> List[Dict[str, Any]]:
    """Offres a fort score (>= threshold) dont le CV/LM n'est pas encore genere."""
    if threshold is None:
        threshold = getattr(config, "SCORE_GENERATE", config.SCORE_PRIORITAIRE)
    data = load_jobs_global()
    todo = []
    for job in data.get("jobs", {}).values():
        score = job.get("score") or 0
        if score >= threshold and not job.get("cv_genere"):
            todo.append(job)
    logger.info(f"Found {len(todo)} jobs for CV/LM generation (score >= {threshold})")
    return todo


def mark_job_generated(job_id: str, cv_path: str = "", lm_path: str = "", out_dir: str = "") -> None:
    """Marque une offre comme generee (CV/LM) et stocke les chemins."""
    data = load_jobs_global()
    jobs = data.get("jobs", {})
    if job_id in jobs:
        jobs[job_id]["cv_genere"] = True
        jobs[job_id]["generated_files"] = {
            "cv": str(cv_path),
            "lm": str(lm_path),
            "dir": str(out_dir),
        }
        save_jobs_global(data)


def set_job_postule(job_id: str, value: bool = True) -> bool:
    """Marque/démarque une offre comme postulée (avec date de candidature)."""
    data = load_jobs_global()
    jobs = data.get("jobs", {})
    if job_id not in jobs:
        return False
    jobs[job_id]["postule"] = bool(value)
    if value:
        jobs[job_id]["date_postule"] = datetime.now().strftime("%Y-%m-%d")
    else:
        jobs[job_id].pop("date_postule", None)
    save_jobs_global(data)
    return True


def set_job_closed(job_id: str, value: bool = True) -> bool:
    """Marque/démarque une offre comme fermée (poste pourvu / ne prend plus de candidatures)."""
    data = load_jobs_global()
    jobs = data.get("jobs", {})
    if job_id not in jobs:
        return False
    jobs[job_id]["closed"] = bool(value)
    if value:
        jobs[job_id]["date_closed"] = datetime.now().strftime("%Y-%m-%d")
    else:
        jobs[job_id].pop("date_closed", None)
    save_jobs_global(data)
    return True


def update_job_notion(job_id: str, notion_page_id: str) -> None:
    """Update a job with Notion page ID."""
    data = load_jobs_global()
    jobs = data.get("jobs", {})
    
    if job_id in jobs:
        jobs[job_id]["notion_page_id"] = notion_page_id
        data["metadata"]["notion_added"] = data["metadata"].get("notion_added", 0) + 1
        save_jobs_global(data)


def get_job_count() -> int:
    """Get total job count."""
    data = load_jobs_global()
    return len(data.get("jobs", {}))