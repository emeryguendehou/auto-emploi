import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
GENERATED_DIR = DATA_DIR / "generated"
LOGS_DIR = BASE_DIR / "logs"

GENERATED_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

KEYWORDS = [
    "Cybersécurité GRC",
    "Gouvernance Risques Conformité",
    "IAM Engineer",
    "Cloud Security Engineer",
    "Application Security Engineer",
    "AI Security Engineer",
    "LLM Security",
    "AI Governance",
    "AI Engineer",
    "Prompt Engineer",
    "Développeur Python IA",
]

JOB_TYPES = [
    "cdi",
    "cdd",
]

# Sources de scraping activables/desactivables sans toucher au code.
# WTTJ est OFF par defaut (le site a change, l'acteur Apify n'est plus fiable).
# Repasser a True si Welcome to the Jungle / l'acteur redeviennent exploitables.
SCRAPER_SOURCES = {
    "linkedin": True,
    "indeed": True,
    "wttj": False,
}

# Categories de classification (pilotent le scoring LLM ET les options Notion).
# Editable librement : ajouter/retirer une categorie se repercute partout
# (prompt LLM, options du select Notion, script setup_notion.py).
JOB_CATEGORIES = [
    "Cyber GRC",          # gouvernance, conformité, risques, audit
    "Cyber Technique",    # cloud sec, appsec, IAM
    "AI Security",        # sécurité de l'IA / LLM security
    "AI Governance",      # gouvernance de l'IA
    "AI Engineer",        # agents, RAG, intégration LLM
    "Python/Automation",  # dev Python orienté IA / automatisation / cyber
    "Autre",
]

MAX_JOBS_PER_SCRAPE = 10

# Fenêtre de fraîcheur du scrape : on ne ramène que les offres publiées entre
# aujourd'hui (J) et J-MAX_JOB_AGE_DAYS. Piloté à la source (LinkedIn f_TPR,
# Indeed fromDays) ET revérifié après scrape (scraper.filter_by_age).
MAX_JOB_AGE_DAYS = 4
MAX_JOB_AGE_SECONDS = MAX_JOB_AGE_DAYS * 24 * 3600  # fenêtre en secondes (LinkedIn f_TPR)

# Zones de recherche (multi-pays).
# - France : tous modes de travail (présentiel / hybride / télétravail).
# - Canada : zone dédiée (priorité), mais full remote uniquement (retour France).
# - International : le reste du monde en full remote (geoId "Worldwide" 92000000
#   + f_WT=2), LinkedIn seul. Couvre Europe, US, etc.
# Pour l'étranger (Canada + International), seul le 100 % télétravail faisable
# depuis la France est visé. Indeed étant mono-pays, il n'est lancé que là où
# indeed_country est défini.
# geoId LinkedIn éditables : France=105015875, Worldwide=92000000,
# Île-de-France=104246759, Canada=101174742.
SEARCH_LOCATIONS = [
    {
        "label": "France",
        "linkedin_geoid": "105015875",
        "linkedin_remote_only": False,
        "indeed_country": "FR",
        "indeed_location": "France",
    },
    {
        "label": "Canada",
        "linkedin_geoid": "101174742",
        "linkedin_remote_only": True,   # étranger -> full remote faisable depuis la France
        "indeed_country": "CA",
        "indeed_location": "Canada",
    },
    {
        # Europe en remote : geoId "Union Européenne" (91000000). Le geoId
        # "Worldwide" (92000000) ne renvoie RIEN pour une recherche d'emploi
        # LinkedIn -> on cible l'UE, la plus réaliste pour un poste tenable
        # depuis la France (fuseau + droit au travail UE). LinkedIn seul
        # (Indeed est mono-pays). geoId USA=103644278 si besoin un jour.
        "label": "Europe (remote)",
        "linkedin_geoid": "91000000",
        "linkedin_remote_only": True,
        "indeed_country": None,   # Indeed est mono-pays -> non lancé ici
        "indeed_location": None,
    },
]

# Zones ACTIVÉES pour le scraping (éditable via le dashboard → « Zones de scrape »,
# ou en ponctuel via `--zones`). Clé = label d'une entrée de SEARCH_LOCATIONS.
# Une zone à False est simplement ignorée au scraping ; ses offres déjà en base
# restent. On filtre ici pour ne jamais toucher aux geoId de SEARCH_LOCATIONS.
SCRAPE_ZONES_ENABLED = {
    "France": False,
    "Canada": False,
    "Europe (remote)": True,
}

# Alias acceptés par l'override CLI `--zones` (insensible casse/accents).
_ZONE_ALIASES = {
    "france": "France", "fr": "France",
    "canada": "Canada", "ca": "Canada",
    "europe": "Europe (remote)", "eu": "Europe (remote)", "ue": "Europe (remote)",
    "international": "Europe (remote)", "intl": "Europe (remote)",
}


def active_search_locations(only=None):
    """Zones de SEARCH_LOCATIONS effectivement scrapées.

    - `only` (liste de labels/alias) : override ponctuel qui IGNORE
      SCRAPE_ZONES_ENABLED (ex. `--zones canada`).
    - sinon : les zones dont SCRAPE_ZONES_ENABLED[label] est vrai.
    """
    if only:
        wanted = set()
        for tok in only:
            t = tok.strip().lower()
            if not t:
                continue
            wanted.add(_ZONE_ALIASES.get(t, t))
        return [
            loc for loc in SEARCH_LOCATIONS
            if loc["label"] in wanted
            or any(w in loc["label"].lower() for w in wanted)
        ]
    return [loc for loc in SEARCH_LOCATIONS if SCRAPE_ZONES_ENABLED.get(loc["label"], True)]


DEFAULT_LOCATION = "FR"

SCORE_PRIORITAIRE = 80
SCORE_SEUIL = 60
SCORE_NOTION = 60

# Classement multi-critères : pondération du "score global" (0-100).
# Le LLM note chaque axe (0-100) ; le score global = moyenne pondérée, MAIS
# ramené à 0 si le fit vaut 0 (offre éliminée : hors cible / mauvais contrat /
# étranger non-remote). "Argent d'abord" -> rémunération lourde. Éditable.
RANKING_WEIGHTS = {
    "fit": 0.35,           # adéquation profil (= score principal, éliminatoire)
    "remuneration": 0.30,  # niveau de salaire
    "flexibilite": 0.15,   # télétravail / remote international
    "entreprise": 0.10,    # qualité / réputation de l'entreprise
    "evolution": 0.10,     # perspectives d'évolution
}

# Generation CV/lettre de motivation (phase --phase generate).
# La redaction demande du RAISONNEMENT (choisir les experiences pertinentes,
# adapter a l'offre) -> modele de raisonnement generaliste en primaire
# (DeepSeek V4 pro via NVIDIA NIM, gratuit), Gemini 2.5 Flash en secours.
# Editable : ex. "openrouter/deepseek/deepseek-r1:free" ou "gemini/gemini-2.5-pro".
# Necessite NVIDIA_NIM_API_KEY dans .env (sinon bascule sur le fallback Gemini).
SCORE_GENERATE = 80
GENERATOR_PRIMARY_MODEL = "nvidia_nim/deepseek-ai/deepseek-v4-pro"
GENERATOR_FALLBACK_MODEL = "gemini/gemini-2.5-flash"

SCHEDULE_ENABLED = False  # Set True for automatic daily runs
SCHEDULE_HOUR = 9
SCHEDULE_MINUTE = 0
SCHEDULE_DAYS = [1, 2, 3, 4, 5]

APIFY_LINKEDIN_ACTOR = "hKByXkMQaC5Qt9UMN"
APIFY_INDEED_ACTOR = "BIeK7ZcYUrdxDgOEQ"
APIFY_WTTJ_ACTOR = "TtyMcBQsSh3wzxbl9"

INDEED_RATIO = 0.7
WTTJ_RATIO = 0.3

LINKEDIN_MAX_PAGES = 1
INDEED_MAX_PAGES = 3
WTTJ_MAX_PAGES = 3

# groq_r1 (gpt-oss-120b) retiré : ce modèle de raisonnement dépasse le budget de
# tokens avant de finir son JSON (erreurs "json_validate_failed"). On garde les
# modèles fiables. Réactivable plus tard avec un max_tokens plus élevé si besoin.
GROQ_ROTATION = ["groq_70b", "groq_70b_2", "groq_qwq"]

LLM_LOG_ENABLED = True
LLM_LOG_DIR = LOGS_DIR / "llm"

NOTION_DB_ID = os.getenv("NOTION_DB_ID", "")
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")

# Clés Gemini : remplis-en autant que tu veux dans .env (GEMINI_API_KEY_1..N).
# Les slots sans clé sont AUTOMATIQUEMENT ignorés (aucun essai gaspillé).
# Gemini 2.5 Flash Lite est gratuit (palier Google AI Studio). Monte GEMINI_KEYS_COUNT
# pour prévoir plus de slots ; ajoute juste les variables correspondantes dans .env.
# daily_limit = 20 : limite REELLE du free tier flash-lite (constatee via 429
# "limit: 20" le 06/07/2026) ; 1000 faisait gaspiller des tentatives au routeur.
GEMINI_KEYS_COUNT = 7
_GEMINI_QUOTAS = {
    f"gemini_{i}": {
        "model": "gemini-2.5-flash-lite",
        "api_key_env": f"GEMINI_API_KEY_{i}",
        "daily_limit": 20,
        "delay_seconds": 4,
    }
    for i in range(1, GEMINI_KEYS_COUNT + 1)
}

LLM_QUOTAS = {
    # Compte Groq 1
    "groq_qwq": {
        "model": "groq/qwen/qwen3-32b",
        "api_key_env": "GROQ_API_KEY_1",
        "daily_limit": 1000,
        "tpm_limit": 6000,
        "delay_seconds": 15,
        "pause_every": 20,
        "pause_duration": 60,
    },
    "groq_70b": {
        "model": "groq/llama-3.3-70b-versatile",
        "api_key_env": "GROQ_API_KEY_1",
        "daily_limit": 1000,
        "tpm_limit": 6000,
        "delay_seconds": 15,
        "pause_every": 20,
        "pause_duration": 60,
    },
    # Compte Groq 2
    "groq_70b_2": {
        "model": "groq/llama-3.3-70b-versatile",
        "api_key_env": "GROQ_API_KEY_2",
        "daily_limit": 1000,
        "tpm_limit": 6000,
        "delay_seconds": 15,
        "pause_every": 20,
        "pause_duration": 60,
    },
    "groq_r1": {
        "model": "groq/openai/gpt-oss-120b",
        "api_key_env": "GROQ_API_KEY_2",
        "daily_limit": 1000,
        "tpm_limit": 6000,
        "delay_seconds": 15,
        "pause_every": 20,
        "pause_duration": 60,
    },
    # NVIDIA NIM (build.nvidia.com) : gratuit, ~40 req/min, pas de plafond
    # journalier — fallback prioritaire quand Groq est épuisé (TPD), car les
    # clés Gemini free tier sont plafonnées à ~20 requêtes/jour chacune.
    "nvidia_llama": {
        "model": "nvidia_nim/meta/llama-3.3-70b-instruct",
        "api_key_env": "NVIDIA_NIM_API_KEY",
        "daily_limit": 100000,
        "delay_seconds": 2,
    },
    # Fallbacks Gemini (mêmes clés que LLM_QUOTAS)
    **_GEMINI_QUOTAS,
    "openrouter_gpt": {
        "model": "openrouter/openai/gpt-oss-120b",
        "api_key_env": "OPENROUTER_API_KEY",
        "daily_limit": 40,
        "delay_seconds": 90,
    },
    "openrouter_nemotron": {
        "model": "openrouter/nvidia/nemotron-3-super-120b-a12b",
        "api_key_env": "OPENROUTER_API_KEY",
        "daily_limit": 40,
        "delay_seconds": 90,
    },
}

DEFAULT_LLM_QUOTAS = {
    # Compte Groq 1
    "groq_qwq": {
        "model": "groq/qwen/qwen3-32b",
        "api_key_env": "GROQ_API_KEY_1",
        "daily_limit": 1000,
        "tpm_limit": 6000,
        "delay_seconds": 15,
        "pause_every": 20,
        "pause_duration": 60,
    },
    "groq_70b": {
        "model": "groq/llama-3.3-70b-versatile",
        "api_key_env": "GROQ_API_KEY_1",
        "daily_limit": 1000,
        "tpm_limit": 6000,
        "delay_seconds": 15,
        "pause_every": 20,
        "pause_duration": 60,
    },
    # Compte Groq 2
    "groq_70b_2": {
        "model": "groq/llama-3.3-70b-versatile",
        "api_key_env": "GROQ_API_KEY_2",
        "daily_limit": 1000,
        "tpm_limit": 6000,
        "delay_seconds": 15,
        "pause_every": 20,
        "pause_duration": 60,
    },
    "groq_r1": {
        "model": "groq/openai/gpt-oss-120b",
        "api_key_env": "GROQ_API_KEY_2",
        "daily_limit": 1000,
        "tpm_limit": 6000,
        "delay_seconds": 15,
        "pause_every": 20,
        "pause_duration": 60,
    },
    # NVIDIA NIM (build.nvidia.com) : gratuit, ~40 req/min, pas de plafond
    # journalier — fallback prioritaire quand Groq est épuisé (TPD), car les
    # clés Gemini free tier sont plafonnées à ~20 requêtes/jour chacune.
    "nvidia_llama": {
        "model": "nvidia_nim/meta/llama-3.3-70b-instruct",
        "api_key_env": "NVIDIA_NIM_API_KEY",
        "daily_limit": 100000,
        "delay_seconds": 2,
    },
    # Fallbacks Gemini (mêmes clés que LLM_QUOTAS)
    **_GEMINI_QUOTAS,
    "openrouter_gpt": {
        "model": "openrouter/openai/gpt-oss-120b",
        "api_key_env": "OPENROUTER_API_KEY",
        "daily_limit": 40,
        "delay_seconds": 90,
    },
    "openrouter_nemotron": {
        "model": "openrouter/nvidia/nemotron-3-super-120b-a12b",
        "api_key_env": "OPENROUTER_API_KEY",
        "daily_limit": 40,
        "delay_seconds": 90,
    },
}

# Liste VOLONTAIREMENT MINIMALE. Pour une recherche cyber/IA, presque tout terme
# technique peut être pertinent (ex. "SAP security", "PeopleSoft IAM",
# "COBOL audit"...). La pertinence métier est donc jugée par le LLM (SYSTEM_PROMPT).
# Le type de contrat (CDI/CDD vs stage/alternance) est géré par le classifieur,
# PAS ici. On ne garde que du legacy/industriel clairement hors-cible.
# (Avant le pivot : ~85 patterns qui excluaient CDI/CDD, les villes, data/ML/cyber
#  — soit exactement la nouvelle cible. Tout retiré.)
EXCLUSION_LIST = [
    r"\bcobol\b",
    r"\bfortran\b",
    r"\blabview\b",
]

# Exclusions appliquées au TITRE UNIQUEMENT (matcher.check_exclusion_list).
# Contrairement à EXCLUSION_LIST (titre + description), on peut y mettre des
# intitulés métiers hors-cible sans risquer d'éliminer une offre cyber dont la
# description mentionne le mot en passant ("fraude", "commercial", "audit"...).
# Faux positifs observés (retenues à tort) : commercial cyber, lutte anti-fraude,
# sécurité physique, GRC bancaire/financière (contrôle interne, audit financier,
# résolution bancaire, KYC). Les cas ambigus ("risque et conformité" sans plus)
# restent tranchés par le LLM (SYSTEM_PROMPT, critères éliminatoires).
# NB : pas de crochets [] dans les patterns (l'éditeur du dashboard parse la
# liste avec un regex qui s'arrête au premier ']') -> utiliser (?:é|e) etc.
TITLE_EXCLUSION_LIST = [
    r"ing(?:é|e)nieur\w*\s+commercial",
    r"\bcommercial(?:e|aux)?\b",
    r"business\s+develop",
    r"account\s+(?:manager|executive)",
    r"avant(?:-|\s)vente",
    r"\bsales\b",
    r"\bfraudes?\b",
    r"fraud\s+(?:analyst|officer|manager)",
    r"security\s+(?:supervisor|guard)",
    r"agent\w*\s+de\s+s(?:é|e)curit(?:é|e)",
    r"s(?:û|u)ret(?:é|e)",
    r"contr(?:ô|o)le\s+interne",
    r"contr(?:ô|o)leur\w*\s+interne",
    r"audit\w*\s+(?:financier|comptable)",
    r"auditeur.*?financ",
    r"analystes?\s+r(?:é|e)solution",
    r"r(?:é|e)solution\s+bancaire",
    r"\bkyc\b",
    r"lcb(?:-|\s)?ft",
    r"risques?\s+financiers?",
    r"prudentiel",
    # Ajouts après audit manuel du 06/07/2026 (66 faux positifs purgés)
    r"charg(?:é|e)\S*\s+d.affaires",
    r"\binternal audit",
    r"auditeur\w*\s+interne",
    r"directeur\w*\s+de\s+l.audit",
    r"\bmlro\b",
    r"money laundering",
    r"tracfin",
    r"blanchiment",
    r"\bjuriste\b",
    r"brand protection",
    r"bcbs\s*239",
    r"reportings?\s+r(?:é|e)glementaires?",
    r"operational risk",
    r"risques?\s+op(?:é|e)rationnels?",
    r"risques?\s+et\s+opportunit(?:é|e)s",
    r"quality\s+(?:&|and)\s+risk management",
    r"protection de la client(?:è|e)le",
    r"services d.investissement",
    r"conformit(?:é|e)\s+assurance",
    r"head of compliance",
    r"ing(?:é|e)nieur\w*\s+poste de travail",
    r"workstation engineer",
    r"\bgmao\b",
    # Séniorité (audit du 07/07/2026) : uniquement les titres SANS ambiguïté.
    # "senior" au singulier, "lead", "manager", "expert", "confirmé" restent
    # tranchés par le LLM : des offres à <= 3 ans d'expérience portent ces titres.
    r"\bseniors\b",
    r"\bhead of\b",
    r"\bchief\b",
    r"\bdirectors?\b",
    r"\bprincipal\b",
    r"\bfreelance\b",
    r"vice(?:-|\s)president",
    r"\bvp\b",
]

# ── PRÉ-FILTRE DÉTERMINISTE (avant scoring LLM) ──────────────────────
# Écarte à 0 des offres structurellement hors-cible AVANT d'appeler le LLM
# (économie de quotas). Complète TITLE_EXCLUSION_LIST (titres senior) avec :
# contrat non CDI/CDD, expérience > N ans, et étranger sans remote mondial.
# TOUT est éditable via le dashboard (page « Pré-filtre ») — rien n'est figé.
# NB éditeur : pas de crochets [] dans les patterns (le parseur s'arrête au 1er ']').
PREFILTER_ENABLED = True

# Contrat non CDI/CDD (mission/gig/horaire) détecté dans titre + description.
PREFILTER_CONTRACT_TERMS = [
    r"hourly contract",
    r"per hour",
    r"\bb2b\b",
    r"corp(?:-|\s)to(?:-|\s)corp",
    r"\bc2c\b",
    r"incorporated entities",
    r"\bportage\b",
    r"\bfreelance\b",
    r"\bint(?:é|e)rim\b",
    r"contract ending",
    r"month contract",
    r"contrat de mission",
]

# Expérience minimale : une exigence STRICTEMENT supérieure à N ans élimine.
# Mettre une valeur haute (ex. 99) désactive ce contrôle.
PREFILTER_MAX_EXP_YEARS = 3

# Zones considérées « locales » (tenables en télétravail depuis la France sans
# remote mondial) : exemptées du filtre géo strict ci-dessous. La France et
# l'Europe en font partie (fuseau + droit au travail UE) ; le LLM tranche
# ensuite la faisabilité au cas par cas. Éditable.
PREFILTER_LOCAL_ZONES = ["france", "europe"]

# Étranger HORS zones locales : éliminé SAUF si un vrai remote mondial est
# mentionné. Résout le « remote Canada/US » qui exige une présence locale.
PREFILTER_FOREIGN_REQUIRE_GLOBAL_REMOTE = True
PREFILTER_GLOBAL_REMOTE_TERMS = [
    r"work(?:-|\s)from(?:-|\s)anywhere",
    r"anywhere in the world",
    r"anywhere globally",
    r"globally distributed",
    r"\bworldwide\b",
    r"fully remote",
    r"remote(?:,)? global",
    r"partout dans le monde",
]