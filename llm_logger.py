"""LLM Prompt Logger - Sauvegarde les prompts et responses pour debug."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import config
import utils

logger = utils.setup_logging("llm_logger")

_run_counter = 0
_current_log_file: Optional[Path] = None


def get_run_id() -> str:
    """Genere un ID unique pour le run."""
    global _run_counter
    _run_counter += 1
    return f"run_{_run_counter:03d}"


def get_log_file_path() -> Path:
    """Retourne le chemin du fichier de log pour le run actuel."""
    global _current_log_file
    
    if _current_log_file is None:
        config.LLM_LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"llm_{timestamp}_{get_run_id()}.json"
        _current_log_file = config.LLM_LOG_DIR / filename
        
        # Initialiser le fichier
        data = {
            "run_id": f"run_{_run_counter:03d}",
            "started_at": datetime.now().isoformat(),
            "entries": [],
        }
        with open(_current_log_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    return _current_log_file


def should_log() -> bool:
    """Check si le logging est active."""
    return getattr(config, 'LLM_LOG_ENABLED', False)


def log_prompt(
    job: Dict[str, Any],
    user_prompt: str,
    provider: str,
    system_prompt: str,
) -> None:
    """Sauvegarde le prompt envoye au LLM."""
    if not should_log():
        return
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "type": "prompt",
        "provider": provider,
        "job_id": job.get("job_id", ""),
        "job_info": {
            "titre": job.get("titre", ""),
            "entreprise": job.get("entreprise", ""),
            "localisation": job.get("localisation", ""),
            "description_length": len(job.get("description", "")),
        },
        "prompts": {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        },
    }
    
    _append_to_log(log_entry)


def log_response(
    job_id: str,
    response: Dict[str, Any],
    provider: str,
) -> None:
    """Sauvegarde la reponse du LLM."""
    if not should_log():
        return
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "type": "response",
        "provider": provider,
        "job_id": job_id,
        "response": response,
    }
    
    _append_to_log(log_entry)


def _append_to_log(entry: Dict[str, Any]) -> None:
    """Ajoute une entree au fichier de log."""
    log_file = get_log_file_path()
    
    with open(log_file, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {"entries": []}
    
    data["entries"].append(entry)
    
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def finalize_log() -> None:
    """Finalise le log - ajoute les infos de fin."""
    if not should_log():
        return
    
    global _current_log_file
    
    if _current_log_file is None or not _current_log_file.exists():
        return
    
    with open(_current_log_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    data["finished_at"] = datetime.now().isoformat()
    data["total_entries"] = len(data.get("entries", []))
    
    with open(_current_log_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Reset for next run
    _current_log_file = None


def reset_log() -> None:
    """Reset le counter pour un nouveau run manuel."""
    global _run_counter, _current_log_file
    _run_counter = 0
    _current_log_file = None