import re
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / "config.py"
SCRAPER_FILE = BASE_DIR / "scraper.py"
MATCHER_FILE = BASE_DIR / "matcher.py"
CRITERIA_FILE = BASE_DIR / "data" / "criteres.md"
QUOTA_HISTORY_FILE = BASE_DIR / "logs" / "quota_history.json"
DEFAULT_QUOTAS_FILE = BASE_DIR / "logs" / "default_quotas.json"

ACTOR_MAP = {
    "LinkedIn": "APIFY_LINKEDIN_ACTOR",
    "Indeed": "APIFY_INDEED_ACTOR",
    "WTTJ": "APIFY_WTTJ_ACTOR",
}


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_file(path: Path, content: str):
    path.write_text(content, encoding="utf-8")


# ── List variables (KEYWORDS, WTTJ_TITLE_KEYWORDS, EXCLUSION_LIST) ──

def read_list(file_name: str, var_name: str) -> list[str]:
    file_path = BASE_DIR / file_name
    content = _read_file(file_path)
    # Ancre en début de ligne : sans ça, "EXCLUSION_LIST" matcherait aussi à
    # l'intérieur de "TITLE_EXCLUSION_LIST".
    pattern = re.compile(rf'^{re.escape(var_name)}\s*=\s*\[(.*?)\]', re.DOTALL | re.MULTILINE)
    m = pattern.search(content)
    if not m:
        return []
    items_str = m.group(1)
    return re.findall(r'(?:r)?"([^"]*)"', items_str)


def write_list(file_name: str, var_name: str, items: list[str], raw_strings: bool = False):
    file_path = BASE_DIR / file_name
    content = _read_file(file_path)
    indent = "    "
    prefix = "r" if raw_strings else ""
    # En mode raw string (r"..."), les antislashs ne doivent PAS être doublés :
    # r"\bcobol\b" est déjà le pattern voulu. Les doubler produirait \\bcobol\\b
    # (regex cassée). Hors raw string, on échappe normalement.
    items_formatted = ",\n".join(
        f'{indent}{prefix}"{item if raw_strings else item.replace(chr(92), chr(92) * 2)}"'
        for item in items
    )
    new_block = f"{var_name} = [\n{items_formatted},\n]"
    pattern = re.compile(rf'^{re.escape(var_name)}\s*=\s*\[[^\]]*\]', re.DOTALL | re.MULTILINE)
    new_content = pattern.sub(new_block.replace("\\", "\\\\"), content, count=1)
    _write_file(file_path, new_content)


# ── Triple-quoted strings (SYSTEM_PROMPT, SCORE_PROMPT) ──

def read_triple_quoted(file_name: str, var_name: str) -> str:
    file_path = BASE_DIR / file_name
    content = _read_file(file_path)
    patterns = [
        rf'{re.escape(var_name)}\s*=\s*{re.escape(var_name)}\s*=\s*"""(.*?)"""',
        rf'{re.escape(var_name)}\s*=\s*"""(.*?)"""',
        rf'{re.escape(var_name)}\s*=\s*f?"""(.*?)"""',
    ]
    for p in patterns:
        m = re.search(p, content, re.DOTALL)
        if m:
            return m.group(1).strip()
    return ""


def write_triple_quoted(file_name: str, var_name: str, value: str):
    file_path = BASE_DIR / file_name
    content = _read_file(file_path)

    start = content.find(f"{var_name} =")
    if start == -1:
        start = content.find(f"{var_name}=")
    if start == -1:
        return

    after_equals = content.find('"""', start + len(var_name))
    if after_equals == -1:
        return
    triple_close = content.find('"""', after_equals + 3)
    if triple_close == -1:
        return

    new_content = content[:after_equals] + '"""\n' + value + '\n"""' + content[triple_close + 3:]
    _write_file(file_path, new_content)


# ── LLM_QUOTAS dictionary ──

def _find_dict_range(content: str, var_name: str):
    pattern = re.compile(rf'{re.escape(var_name)}\s*=\s*(\{{)', re.DOTALL)
    m = pattern.search(content)
    if not m:
        return None
    start = m.start()
    brace_start = m.start(1)
    depth = 0
    for i in range(brace_start, len(content)):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                return (start, i + 1)
    return None


def read_quotas() -> dict:
    import config
    return {k: dict(v) for k, v in config.LLM_QUOTAS.items()}


def _format_quota_item(key: str, val: dict) -> str:
    lines = [f'    "{key}": {{']
    for field in ["model", "api_key_env", "daily_limit", "tpm_limit",
                   "delay_seconds", "pause_every", "pause_duration"]:
        if field in val:
            v = val[field]
            if isinstance(v, str):
                lines.append(f'        "{field}": "{v}",')
            else:
                lines.append(f'        "{field}": {v},')
    lines.append("    },")
    return "\n".join(lines)


def write_quotas(quotas: dict):
    content = _read_file(CONFIG_FILE)
    range_ = _find_dict_range(content, "LLM_QUOTAS")
    if not range_:
        return

    # Providers dynamiques : on écrit toutes les entrées présentes (Groq, toutes
    # les clés Gemini, OpenRouter...) dans l'ordre reçu, sans liste figée.
    parts = [f"LLM_QUOTAS = {{"]
    for key in quotas:
        parts.append(_format_quota_item(key, quotas[key]))
    parts.append("}")
    new_block = "\n".join(parts)

    new_content = content[:range_[0]] + new_block + content[range_[1]:]
    _write_file(CONFIG_FILE, new_content)


def reset_quotas_to_default():
    content = _read_file(CONFIG_FILE)
    range_ = _find_dict_range(content, "DEFAULT_LLM_QUOTAS")
    if not range_:
        return
    default_block = content[range_[0]:range_[1]]
    quotaname = default_block.replace("DEFAULT_LLM_QUOTAS", "LLM_QUOTAS", 1)
    quotas_range = _find_dict_range(content, "LLM_QUOTAS")
    if not quotas_range:
        return
    new_content = content[:quotas_range[0]] + quotaname + content[quotas_range[1]:]
    _write_file(CONFIG_FILE, new_content)


# ── Scalaires simples (bool / int) dans config.py ──

def read_scalar(var_name: str):
    """Lit `VAR = <bool|int>` dans config.py. Renvoie bool, int, ou None."""
    content = _read_file(CONFIG_FILE)
    m = re.search(rf'^{re.escape(var_name)}\s*=\s*(True|False|\d+)\b', content, re.MULTILINE)
    if not m:
        return None
    v = m.group(1)
    if v == "True":
        return True
    if v == "False":
        return False
    return int(v)


def write_scalar(var_name: str, value) -> None:
    """Écrit `VAR = <bool|int>` dans config.py (remplace la 1re occurrence)."""
    if isinstance(value, bool):
        lit = "True" if value else "False"
    else:
        lit = str(int(value))
    content = _read_file(CONFIG_FILE)
    new = re.sub(rf'^({re.escape(var_name)}\s*=\s*)(?:True|False|\d+)\b',
                 rf'\g<1>{lit}', content, count=1, flags=re.MULTILINE)
    _write_file(CONFIG_FILE, new)


# ── Pré-filtre déterministe (config éditable) ──

def read_prefilter() -> dict:
    return {
        "enabled": bool(read_scalar("PREFILTER_ENABLED")),
        "max_exp_years": read_scalar("PREFILTER_MAX_EXP_YEARS") or 3,
        "foreign_require_global_remote": bool(read_scalar("PREFILTER_FOREIGN_REQUIRE_GLOBAL_REMOTE")),
        "contract_terms": read_list("config.py", "PREFILTER_CONTRACT_TERMS"),
        "global_remote_terms": read_list("config.py", "PREFILTER_GLOBAL_REMOTE_TERMS"),
    }


def write_prefilter(data: dict) -> None:
    if "enabled" in data:
        write_scalar("PREFILTER_ENABLED", bool(data["enabled"]))
    if "foreign_require_global_remote" in data:
        write_scalar("PREFILTER_FOREIGN_REQUIRE_GLOBAL_REMOTE", bool(data["foreign_require_global_remote"]))
    if "max_exp_years" in data and data["max_exp_years"] is not None:
        write_scalar("PREFILTER_MAX_EXP_YEARS", int(data["max_exp_years"]))
    if "contract_terms" in data:
        write_list("config.py", "PREFILTER_CONTRACT_TERMS", data["contract_terms"], raw_strings=True)
    if "global_remote_terms" in data:
        write_list("config.py", "PREFILTER_GLOBAL_REMOTE_TERMS", data["global_remote_terms"], raw_strings=True)


# ── Zones de scrape (SCRAPE_ZONES_ENABLED) ──

def read_zones() -> list[dict]:
    """État des zones de scrape : label, activée, méta d'affichage.

    Fusionne SEARCH_LOCATIONS (méta : remote-only, Indeed dispo) avec
    SCRAPE_ZONES_ENABLED (état on/off). Une zone absente du dict est active
    par défaut (rétrocompat)."""
    import importlib
    import config
    importlib.reload(config)  # relit le fichier après un save précédent
    enabled = getattr(config, "SCRAPE_ZONES_ENABLED", {})
    zones = []
    for loc in config.SEARCH_LOCATIONS:
        label = loc["label"]
        zones.append({
            "label": label,
            "enabled": bool(enabled.get(label, True)),
            "remote_only": bool(loc.get("linkedin_remote_only")),
            "indeed": bool(loc.get("indeed_country")),
        })
    return zones


def write_zones(enabled_map: dict) -> None:
    """Réécrit le bloc SCRAPE_ZONES_ENABLED. `enabled_map` : {label: bool}.
    Les labels inconnus (hors SEARCH_LOCATIONS) sont ignorés ; les labels
    absents de enabled_map gardent leur valeur courante."""
    import config
    current = {loc["label"]: getattr(config, "SCRAPE_ZONES_ENABLED", {}).get(loc["label"], True)
               for loc in config.SEARCH_LOCATIONS}
    for label, val in enabled_map.items():
        if label in current:
            current[label] = bool(val)

    content = _read_file(CONFIG_FILE)
    range_ = _find_dict_range(content, "SCRAPE_ZONES_ENABLED")
    if not range_:
        return
    lines = ["SCRAPE_ZONES_ENABLED = {"]
    for label, val in current.items():
        lines.append(f'    "{label}": {val},')
    lines.append("}")
    new_block = "\n".join(lines)
    new_content = content[:range_[0]] + new_block + content[range_[1]:]
    _write_file(CONFIG_FILE, new_content)


# ── Criteria markdown file ──

def read_criteria() -> str:
    if not CRITERIA_FILE.exists():
        return ""
    return CRITERIA_FILE.read_text(encoding="utf-8")


def write_criteria(text: str):
    CRITERIA_FILE.write_text(text, encoding="utf-8")


# ── Scraper actors config ──

def read_actor_ids() -> dict:
    content = _read_file(CONFIG_FILE)
    result = {}
    for source, var in ACTOR_MAP.items():
        m = re.search(rf'{re.escape(var)}\s*=\s*"([^"]*)"', content)
        result[source] = m.group(1) if m else ""
    return result


# ── Quota history ──

def read_quota_history() -> dict:
    if not QUOTA_HISTORY_FILE.exists():
        return {}
    return json.loads(QUOTA_HISTORY_FILE.read_text(encoding="utf-8"))


def get_today_usage() -> dict:
    history = read_quota_history()
    today = datetime.now().strftime("%Y-%m-%d")
    return history.get(today, {})


# ── Global job stats ──

def get_job_stats() -> dict:
    """Stats de la base, ALIGNEES sur la page Offres du dashboard.

    Les compteurs par score ne portent que sur le POOL ACTIF (offres ni postulees
    ni fermees) — exactement comme les onglets de la page Offres. Les offres
    postulees (Candidatures) et fermees (Offres fermees) sont comptees a part.
      - unprocessed : score is None (jamais passe au LLM)
      - excluded    : score == 0   (rejete : contrat hors cible / exclusion list)
      - ignores     : 0 < score < 60
      - a_etudier   : 60 <= score < 80
      - prioritaires: score >= 80
    (total = postule + closed + unprocessed + excluded + ignores + a_etudier + prioritaires)
    """
    import config as _cfg
    from data_loader import load_jobs_global
    data = load_jobs_global()
    jobs = data.get("jobs", {})

    seuil = getattr(_cfg, "SCORE_SEUIL", 60)
    prio = getattr(_cfg, "SCORE_PRIORITAIRE", 80)

    total = len(jobs)
    unprocessed = excluded = ignores = a_etudier = prioritaires = 0
    postule = closed = in_notion = 0

    for j in jobs.values():
        if j.get("notion_page_id"):
            in_notion += 1
        # Postule / ferme : buckets prioritaires (comme la page Offres qui les
        # sort de la liste). Postule l'emporte sur ferme (offre a laquelle on a
        # candidate = candidature, meme si l'annonce ferme ensuite).
        if j.get("postule"):
            postule += 1
            continue
        if j.get("closed"):
            closed += 1
            continue
        score = j.get("score")
        if score is None:
            unprocessed += 1
        elif score == 0:
            excluded += 1
        elif score < seuil:
            ignores += 1
        elif score < prio:
            a_etudier += 1
        else:
            prioritaires += 1

    return {
        "total": total,
        "unprocessed": unprocessed,
        "excluded": excluded,
        "ignores": ignores,
        "a_etudier": a_etudier,
        "prioritaires": prioritaires,
        "postule": postule,
        "closed": closed,
        "in_notion": in_notion,
        "processed": total - unprocessed,
    }
