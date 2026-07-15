import os
import re
import sys
import json
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
import config

def setup_logging(name: str = "auto_alternance") -> logging.Logger:
    # Windows : la console est souvent en cp1252 et plante (UnicodeEncodeError)
    # des qu'un log contient un caractere non-latin1 (ex: la fleche "→" presente
    # dans de nombreux logs). On force UTF-8 avec repli "replace" pour ne JAMAIS
    # interrompre un run a cause d'un caractere d'affichage.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

def get_env(key: str, required: bool = True) -> Optional[str]:
    value = os.getenv(key)
    if not value and required:
        raise ValueError(f"Missing required env var: {key}")
    return value

def load_json_file(filepath: Path) -> Any:
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json_file(filepath: Path, data: Any) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def hash_url(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.split()).strip()

_THINK_RE = re.compile(r"<think\b[^>]*>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: Optional[str]) -> str:
    """Retire les blocs de raisonnement <think>...</think> laissés par certains
    modèles (DeepSeek R1, QwQ...) pour ne garder que la réponse finale."""
    if not text:
        return ""
    return _THINK_RE.sub("", text).strip()


def get_date_string() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def get_datetime_string() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def safe_filename(name: str) -> str:
    keepcharacters = (" ", ".", "_", "-")
    return "".join(c for c in name if c.isalnum() or c in keepcharacters).rstrip()


# ─────────────────────────────────────────────────────────────────────────────
# Classification du type de contrat (source unique de verite).
# Utilise par scraper.py (filtrage a la source), data_loader.py (exclusion
# post-scrape) et notion_db.py (propriete "Type de contrat").
#
# Priorite d'analyse : alternance > stage > cdd > cdi. On regarde D'ABORD le
# titre (qui prime), puis le texte complet seulement si le titre est muet. Ainsi
# "CDI a la cle apres l'alternance" ou "alternance" dans le titre -> alternance,
# et un CDI dont la description mentionne "nos alternants" reste un CDI.
# ─────────────────────────────────────────────────────────────────────────────

_CONTRACT_PATTERNS = [
    ("alternance", re.compile(
        r"\balternan(?:ce|t|te)\b|\bapprenti(?:ssage|e)?\b"
        r"|contrat\s+de\s+professionnalisation|contrat\s+pro\b|work[\s-]?study",
        re.IGNORECASE)),
    ("stage", re.compile(
        r"\bstages?\b|\bstagiaire\b|\binternship\b|\bintern\b|\btrainee\b",
        re.IGNORECASE)),
    ("cdd", re.compile(
        r"\bcdd\b|fixed[\s-]?term|contrat\s+(?:a|à)\s+dur(?:é|e)e\s+d(?:é|e)termin",
        re.IGNORECASE)),
    ("cdi", re.compile(
        r"\bcdi\b|contrat\s+(?:a|à)\s+dur(?:é|e)e\s+ind(?:é|e)termin"
        r"|\bpermanent\b|temps\s+plein|full[\s-]?time|poste\s+permanent",
        re.IGNORECASE)),
]


def _classify_text(text: str) -> Optional[str]:
    for label, pattern in _CONTRACT_PATTERNS:
        if pattern.search(text):
            return label
    return None


def detect_contract_type(job: Dict[str, Any]) -> str:
    """Retourne 'alternance' | 'stage' | 'cdd' | 'cdi' | 'inconnu'.

    Le titre prime sur la description pour eviter les faux positifs.
    """
    titre = job.get("titre", "") or ""
    description = job.get("description", "") or ""

    from_title = _classify_text(titre)
    if from_title:
        return from_title

    from_full = _classify_text(f"{titre} {description}")
    return from_full or "inconnu"


# Libelles d'affichage (ex: pour la propriete Notion "Type de contrat").
CONTRACT_LABELS = {
    "alternance": "Alternance",
    "stage": "Stage",
    "cdd": "CDD",
    "cdi": "CDI",
    "inconnu": "Inconnu",
}


def contract_label(job: Dict[str, Any]) -> str:
    return CONTRACT_LABELS.get(detect_contract_type(job), "Inconnu")


def is_desired_contract(job: Dict[str, Any]) -> tuple[bool, str]:
    """Decide si l'offre correspond aux types de contrat voulus (config.JOB_TYPES).

    Regles :
      - type detecte dans JOB_TYPES         -> garde (True)
      - type 'inconnu'                       -> garde (True, on ne jette pas un
                                                doute, le LLM tranchera)
      - type connu mais hors JOB_TYPES       -> rejette (False) ex: cdi/cdd/stage
                                                quand on cherche l'alternance

    Returns: (garde, type_detecte)
    """
    detected = detect_contract_type(job)
    desired = {t.lower() for t in getattr(config, "JOB_TYPES", ["alternance"])}
    if detected == "inconnu" or detected in desired:
        return True, detected
    return False, detected