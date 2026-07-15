import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from apify_client import ApifyClient
import config
import utils

logger = utils.setup_logging("scraper")


def normalize_linkedin_job(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "titre": job.get("title", ""),
        "entreprise": job.get("companyName", ""),
        "localisation": job.get("location", ""),
        "description": job.get("descriptionText", job.get("descriptionHtml", "")),
        "lien": job.get("link", ""),
        "source": "LinkedIn",
        "date_publication": job.get("postedAt", ""),
    }


def normalize_indeed_job(job: Dict[str, Any]) -> Dict[str, Any]:
    title_data = job.get("title", {})
    title_text = title_data.get("text", "") if isinstance(title_data, dict) else title_data

    location_data = job.get("location", {})
    if isinstance(location_data, dict):
        location_text = location_data.get("formattedShort", location_data.get("formatted", ""))
    else:
        location_text = location_data or ""

    urls = job.get("urls", {})
    link = urls.get("indeed", "") if isinstance(urls, dict) else ""

    description = job.get("description", {})
    desc_text = description.get("text", "") if isinstance(description, dict) else description

    company_data = job.get("company", {})
    company_name = company_data.get("name", "") if isinstance(company_data, dict) else ""

    dates_data = job.get("dates", {})
    posted_date = dates_data.get("posted", "") if isinstance(dates_data, dict) else ""

    return {
        "titre": title_text,
        "entreprise": company_name,
        "localisation": location_text,
        "description": desc_text,
        "lien": link,
        "source": "Indeed",
        "date_publication": posted_date,
    }


def normalize_wttj_job(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "titre": job.get("title", ""),
        "entreprise": job.get("company", ""),
        "localisation": job.get("location", ""),
        "description": job.get("description_text", job.get("description_html", "")),
        "lien": job.get("url", ""),
        "source": "WTTJ",
        "date_publication": job.get("date_posted", ""),
    }


def _linkedin_fjt(job_types: list[str]) -> str:
    mapping = {"cdi": "F", "cdd": "C", "stage": "I", "alternance": "I"}
    codes = [mapping[t] for t in job_types if t in mapping]
    if not codes:
        return ""
    return "%2C".join(sorted(set(codes)))


def build_linkedin_search_url(keyword: str, geoid: str = "105015875", remote_only: bool = False, page: int = 0, job_types: list[str] | None = None) -> str:
    """Construit l'URL de recherche LinkedIn.

    geoid : zone géographique (défaut France). remote_only : si True, ajoute le
    filtre télétravail f_WT=2 (utilisé pour l'international full remote).
    """
    from urllib.parse import quote
    kw = quote(keyword)
    params = [
        f"f_F=it%2Ceng",
        f"geoId={geoid}",
        f"keywords={kw}",
        f"f_TPR=r{config.MAX_JOB_AGE_SECONDS}",
        "origin=JOB_SEARCH_PAGE_KEYWORD_AUTOCOMPLETE",
        "originalSubdomain=fr",
        "refresh=true",
        "sortBy=R",
    ]
    fjt = _linkedin_fjt(job_types or config.JOB_TYPES)
    if fjt:
        params.insert(1, f"f_JT={fjt}")
    if remote_only:
        params.append("f_WT=2")  # LinkedIn : f_WT=2 = télétravail (remote)
    return "https://www.linkedin.com/jobs/search/?" + "&".join(params)


def _wttj_contract_types(job_types: list[str]) -> list[str]:
    mapping = {"cdi": "full_time", "cdd": "fixed_term", "stage": "internship", "alternance": "apprenticeship"}
    return [mapping[t] for t in job_types if t in mapping]


def build_wttj_search_url(keyword: str, job_types: list[str] | None = None) -> str:
    from urllib.parse import quote
    kw = quote(keyword)
    ctype_params = "".join(
        f"&refinementList%5Bcontract_type%5D%5B%5D={ct}"
        for ct in _wttj_contract_types(job_types or config.JOB_TYPES)
    )
    return (f"https://www.welcometothejungle.com/fr/jobs?query={kw}"
            f"&refinementList%5Boffices.country_code%5D%5B%5D=FR"
            f"&refinementList%5Boffices.state%5D%5B%5D=Ile-de-France"
            f"{ctype_params}"
            f"&refinementList%5Bcontract_duration_minimum%5D%5B%5D=25-36"
            f"&refinementList%5Bcontract_duration_minimum%5D%5B%5D=13-24"
            f"&refinementList%5Bcontract_duration_maximum%5D%5B%5D=25-36"
            f"&refinementList%5Bcontract_duration_maximum%5D%5B%5D=13-24"
            f"&refinementList%5Beducation_level%5D%5B%5D=bac_3"
            f"&refinementList%5Beducation_level%5D%5B%5D=bac_2"
            f"&refinementList%5Beducation_level%5D%5B%5D=no_diploma"
            f"&refinementList%5Beducation_level%5D%5B%5D=bac"
            f"&refinementList%5Beducation_level%5D%5B%5D=bac_1"
            f"&refinementList%5Beducation_level%5D%5B%5D=bac_4"
            f"&refinementList%5Blanguage%5D%5B%5D=fr"
            f"&refinementList%5Blanguage%5D%5B%5D=en"
            f"&aroundQuery=%C3%8Ele-de-France%20Region%2C%20France")


def run_apify_actor_sync(
    client: ApifyClient,
    actor_id: str,
    input_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Sync version for Apify actor calls."""
    logger.info(f"Running Apify actor: {actor_id}")

    run = client.actor(actor_id).call(run_input=input_data)

    if not run or not run.get("defaultDatasetId"):
        logger.warning(f"Actor {actor_id} returned no data")
        return []

    dataset_items = client.dataset(run["defaultDatasetId"]).list_items()
    return dataset_items.items


async def run_apify_actor_async(
    client: ApifyClient,
    actor_id: str,
    input_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Async wrapper for Apify actor calls."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, run_apify_actor_sync, client, actor_id, input_data
    )


async def scrape_linkedin(keyword: str, loc: dict, token: str, job_types: list[str] | None = None) -> List[Dict[str, Any]]:
    client = ApifyClient(token)
    max_pages = config.LINKEDIN_MAX_PAGES
    geoid = loc.get("linkedin_geoid", "105015875")
    remote_only = loc.get("linkedin_remote_only", False)
    label = loc.get("label", "?")

    all_jobs = []
    for page in range(max_pages):
        search_url = build_linkedin_search_url(
            keyword, geoid=geoid, remote_only=remote_only, page=page, job_types=job_types
        )

        input_data = {
            "urls": [search_url],
            "maxItems": 50,
        }

        logger.info(f"Scraping LinkedIn: {keyword} @ {label} (page {page+1}/{max_pages})")

        try:
            items = await run_apify_actor_async(client, config.APIFY_LINKEDIN_ACTOR, input_data)
        except Exception as e:
            logger.error(f"LinkedIn scrape failed: {e}")
            break

        jobs = [normalize_linkedin_job(j) for j in items if j.get("link")]
        all_jobs.extend(jobs)

    logger.info(f"LinkedIn: {len(all_jobs)} jobs fetched @ {label}")
    return all_jobs


_INDEED_JOBTYPE_MAP = {"cdi": "fulltime", "cdd": "contract", "stage": "internship", "alternance": "internship"}

# L'acteur Apify Indeed n'accepte que ces paliers pour fromDays.
_INDEED_ALLOWED_FROMDAYS = [1, 3, 7, 14]


def _indeed_from_days(days: int) -> str:
    """Plus petit palier Indeed autorisé >= days (jamais moins large que voulu ;
    filter_by_age recoupe ensuite à la fenêtre exacte). Au-delà de 14 -> "14"."""
    for allowed in _INDEED_ALLOWED_FROMDAYS:
        if allowed >= days:
            return str(allowed)
    return str(_INDEED_ALLOWED_FROMDAYS[-1])


async def scrape_indeed(keyword: str, loc: dict, token: str, job_types: list[str] | None = None) -> List[Dict[str, Any]]:
    country = loc.get("indeed_country")
    if not country:
        # Indeed est mono-pays : on ne le lance pas pour une zone internationale.
        logger.info(f"Indeed ignoré pour '{loc.get('label', '?')}' (source mono-pays)")
        return []

    client = ApifyClient(token)
    max_pages = config.INDEED_MAX_PAGES
    types = job_types or config.JOB_TYPES
    location = loc.get("indeed_location") or ""

    if len(types) == 1:
        t = types[0]
        type_suffix = {"cdi": " CDI", "cdd": " CDD", "stage": " stage", "alternance": " alternance"}
        suffix = type_suffix.get(t, "")
        kw = f"{keyword}{suffix}" if suffix and suffix.strip().lower() not in keyword.lower() else keyword
        jt = _INDEED_JOBTYPE_MAP.get(t, "")
    else:
        # Plusieurs types (ex: CDI + CDD) : Indeed ne prend qu'un seul jobType,
        # on n'en force aucun et on ne suffixe pas le mot-clé (le classifieur de
        # contrat filtre ensuite). Avant : suffixe "alternance" codé en dur.
        kw = keyword
        jt = ""

    all_jobs = []
    for page in range(max_pages):
        input_data = {
            "keyword": kw,
            "location": location,
            "country": country,
            "maxItems": 50,
            "sort": "date",
            # L'acteur Indeed n'accepte que 1/3/7/14 : on prend le plus petit
            # palier >= MAX_JOB_AGE_DAYS (jamais moins de jours que voulu ;
            # filter_by_age recoupe ensuite à la fenêtre exacte). 4 -> "7".
            "fromDays": _indeed_from_days(config.MAX_JOB_AGE_DAYS),
        }
        if jt:
            input_data["jobType"] = jt

        logger.info(f"Scraping Indeed: {kw} @ {location} (page {page+1}/{max_pages})")

        try:
            items = await run_apify_actor_async(client, config.APIFY_INDEED_ACTOR, input_data)
        except Exception as e:
            logger.error(f"Indeed scrape failed: {e}")
            break

        jobs = [normalize_indeed_job(j) for j in items if j.get("urls", {}).get("indeed")]
        all_jobs.extend(jobs)

    logger.info(f"Indeed: {len(all_jobs)} jobs fetched (pages 1-{max_pages})")
    return all_jobs


WTTJ_TITLE_KEYWORDS = [
    r"ia engineer",
    r"ingénieur ia",
    r"intégration ia",
    r"AI et automation",
    r"python",
    r"typescript",
    r"javascript",
    r"ingénieur logiciel",
    r"java",
    r"développeur",
    r"développeuse",
    r"developer",
    r"développement",
    r"AI automations",
    r"applications",
    r"web",
    r"api",
    r"cloud",
    r"docker",
    r"react",
]


_TECH_PATTERN = re.compile(
    r'(?:' + '|'.join(r'\b' + kw + r'\b' for kw in WTTJ_TITLE_KEYWORDS) + r')',
    re.IGNORECASE
)


def is_tech_job_wttj(job: Dict[str, Any]) -> bool:
    titre = job.get("titre", "")
    m = _TECH_PATTERN.search(titre)
    if m:
        logger.debug(f"[WTTJ MATCH] '{m.group()}' → {titre[:60]}")
    return bool(m)


async def scrape_wttj(keyword: str, token: str, job_types: list[str] | None = None) -> List[Dict[str, Any]]:
    client = ApifyClient(token)
    max_pages = config.WTTJ_MAX_PAGES

    search_url = build_wttj_search_url(keyword, job_types=job_types)

    input_data = {
        "start_url": search_url,
        "results_wanted": 50,
        "max_pages": max_pages,
    }

    logger.info(f"Scraping WTTJ: {keyword}")

    try:
        items = await run_apify_actor_async(client, config.APIFY_WTTJ_ACTOR, input_data)
    except Exception as e:
        logger.error(f"WTTJ scrape failed: {e}")
        return []

    jobs = [normalize_wttj_job(j) for j in items if j.get("url")]

    filtered_jobs = []
    for job in jobs:
        if is_tech_job_wttj(job):
            filtered_jobs.append(job)
        else:
            logger.info(f"[WTTJ FILTERED] Non-tech job: {job.get('titre', '')[:50]}")

    logger.info(f"WTTJ: {len(jobs)} jobs fetched → {len(filtered_jobs)} after tech filter")
    return filtered_jobs


# ── Garde-fou de fraîcheur : revérifie l'âge après scrape ──────────────────
# Les sources filtrent déjà à la publication (LinkedIn f_TPR, Indeed fromDays),
# mais certaines renvoient des offres légèrement plus vieilles, et WTTJ n'a
# aucun filtre de date natif. On recoupe donc l'âge ici, en restant PRUDENT :
# une date non interprétable => on garde l'offre (jamais de perte silencieuse).
_REL_DAYS = re.compile(r"(\d+)\s*\+?\s*(?:days?|jours?|j)\b", re.I)
_REL_HOURS = re.compile(r"(\d+)\s*\+?\s*(?:hours?|heures?|hrs?|h)\b", re.I)
_REL_MINUTES = re.compile(r"(\d+)\s*\+?\s*(?:minutes?|mins?)\b", re.I)
_REL_WEEKS = re.compile(r"(\d+)\s*\+?\s*(?:weeks?|semaines?)\b", re.I)
_REL_MONTHS = re.compile(r"(\d+)\s*\+?\s*(?:months?|mois)\b", re.I)


def _parse_age_days(value: Any) -> Optional[float]:
    """Âge de l'offre en jours depuis une date de publication hétérogène
    (ISO, relatif FR/EN « il y a 3 jours » / « 2 days ago », epoch).
    Renvoie None si non interprétable — l'appelant garde alors l'offre."""
    if value is None:
        return None
    now = datetime.now(timezone.utc)

    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:            # millisecondes -> secondes
            ts /= 1000.0
        try:
            return (now - datetime.fromtimestamp(ts, tz=timezone.utc)).total_seconds() / 86400.0
        except (OverflowError, OSError, ValueError):
            return None

    s = str(value).strip().lower()
    if not s:
        return None
    if any(w in s for w in ("aujourd", "today", "just ", "instant", "now")):
        return 0.0
    if "hier" in s or "yesterday" in s:
        return 1.0
    if _REL_HOURS.search(s) or _REL_MINUTES.search(s):
        return 0.0               # moins d'un jour
    if (m := _REL_DAYS.search(s)):
        return float(m.group(1))
    if (m := _REL_WEEKS.search(s)):
        return float(m.group(1)) * 7.0
    if (m := _REL_MONTHS.search(s)):
        return float(m.group(1)) * 30.0

    try:                          # ISO 8601 (avec ou sans fuseau)
        dt = datetime.fromisoformat(s.replace("z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).total_seconds() / 86400.0
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(s[:10], fmt).replace(tzinfo=timezone.utc)
            return (now - dt).total_seconds() / 86400.0
        except ValueError:
            continue
    return None


def filter_by_age(jobs: List[Dict[str, Any]], max_days: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retire les offres dont la date de publication dépasse la fenêtre J-max_days."""
    max_days = config.MAX_JOB_AGE_DAYS if max_days is None else max_days
    kept, dropped = [], 0
    for job in jobs:
        age = _parse_age_days(job.get("date_publication"))
        if age is not None and age > max_days:
            dropped += 1
            logger.debug(f"[AGE FILTER] {age:.0f}j > {max_days}j → {job.get('titre', '')[:50]}")
            continue
        kept.append(job)
    if dropped:
        logger.info(f"Age filter: {len(jobs)} → {len(kept)} (retiré {dropped} hors fenêtre {max_days}j)")
    return kept


def deduplicate_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    unique = []

    for job in jobs:
        lien = job.get("lien", "")
        if not lien:
            continue

        url_hash = utils.hash_url(lien)
        if url_hash not in seen:
            seen.add(url_hash)
            unique.append(job)

    logger.info(f"Deduplication: {len(jobs)} → {len(unique)} unique jobs")
    return unique


def filter_by_contract(jobs: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    """Ne garde que les offres dont le type de contrat est desire (config.JOB_TYPES).

    Le filtrage a la source LinkedIn/Indeed est imprecis (alternance et stage
    partagent f_JT=I / jobType=internship). On rattrape ici avec le classifieur
    partage : les CDI/CDD/stages qui passent au travers sont jetes des le scrape.
    """
    kept = []
    for job in jobs:
        keep, detected = utils.is_desired_contract(job)
        if keep:
            job["type_contrat"] = utils.CONTRACT_LABELS.get(detected, "Inconnu")
            kept.append(job)
        else:
            logger.info(f"[{source} CONTRAT] rejet '{detected}': {job.get('titre', '')[:55]}")
    logger.info(f"{source}: {len(jobs)} -> {len(kept)} apres filtre contrat")
    return kept


async def scrape_all(keyword: str, loc: dict, job_types: list[str] | None = None,
                     sources_override: list[str] | None = None) -> List[Dict[str, Any]]:
    types = job_types or config.JOB_TYPES
    if sources_override:
        # Override ponctuel (CLI --sources) : seules ces sources, quel que soit
        # l'état de config.SCRAPER_SOURCES.
        wanted = {s.strip().lower() for s in sources_override}
        sources = {k: (k in wanted) for k in ("linkedin", "indeed", "wttj")}
    else:
        sources = getattr(config, "SCRAPER_SOURCES", {"linkedin": True, "indeed": True, "wttj": False})

    # Construit dynamiquement la liste des scrapers actives pour cette zone.
    tasks = []
    labels = []
    if sources.get("linkedin"):
        token_linkedin = utils.get_env("APIFY_TOKEN_LINKEDIN")
        tasks.append(scrape_linkedin(keyword, loc, token_linkedin, job_types=types))
        labels.append("LinkedIn")
    if sources.get("indeed"):
        token_other = utils.get_env("APIFY_TOKEN_OTHER")
        tasks.append(scrape_indeed(keyword, loc, token_other, job_types=types))
        labels.append("Indeed")
    if sources.get("wttj"):
        token_other = utils.get_env("APIFY_TOKEN_OTHER")
        tasks.append(scrape_wttj(keyword, token_other, job_types=types))
        labels.append("WTTJ")

    if not tasks:
        logger.warning("Aucune source activee dans config.SCRAPER_SOURCES")
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_jobs: List[Dict[str, Any]] = []
    for label, res in zip(labels, results):
        if isinstance(res, Exception):
            logger.error(f"{label} failed: {res}")
            continue
        all_jobs.extend(filter_by_contract(res or [], label))

    # Zone de scrape persistée sur chaque offre (France / Canada / International) :
    # sert à la génération de CV pour déduire le marché cible (fr/ca-qc/ca-en/intl).
    zone = loc.get("label", "")
    for job in all_jobs:
        job["zone"] = zone

    return deduplicate_jobs(filter_by_age(all_jobs))