#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_cv.py — Génère un CV ciblé (PDF + HTML) à partir de :
  - profile_master.yaml   (base de contenu : bullets taggés FR/EN)
  - country_rules.yaml    (conventions par marché)
  - une offre JSON        (issue de la phase de scoring d'Auto Emploi)

Usage :
  python generate_cv.py --offer offer.json --out out/
  python generate_cv.py --offer offer.json --country ca-en --out out/

Format minimal de offer.json (adapter aux champs de jobs_global.json) :
{
  "title": "AI Workflow Engineer",
  "company": "Scale AI",
  "country": "ca-en",              # fr | ca-qc | ca-en | intl (sinon --country)
  "category": "AI Security",       # catégorie produite par ton scoring
  "description": "texte de l'offre...",
  "keywords": ["agents", "python", "prompt injection"]   # optionnel
}

Principe anti-hallucination : le script SÉLECTIONNE des bullets existants,
il n'en rédige jamais. Le profil = variante taggée de profile_master.yaml
+ phrase de disponibilité. Une accroche LLM peut optionnellement s'insérer
entre les deux via le paramètre `hook` de build_cv (voir cvgen/accroche.py).
"""

import argparse, json, re, sys, unicodedata
from pathlib import Path

import yaml
from jinja2 import Template

HERE = Path(__file__).parent

# ----------------------------------------------------------------------
# Correspondance mots de l'offre -> tags de la base de contenu.
# À enrichir au fil des offres rencontrées (c'est le "cerveau" du matching).
# ----------------------------------------------------------------------
KEYWORD_TO_TAGS = {
    # gouvernance / conformité
    "grc": ["grc"], "iso 27001": ["grc"], "27001": ["grc"], "nis2": ["grc"],
    "dora": ["grc"], "pci": ["grc", "banking"], "swift": ["grc", "banking"],
    "nist": ["grc"], "ebios": ["grc"], "compliance": ["grc"], "conformite": ["grc"],
    "gouvernance": ["grc", "ai-governance"], "governance": ["grc", "ai-governance"],
    "audit": ["grc"], "rssi": ["grc", "security-ops"], "ciso": ["grc", "security-ops"],
    "risk": ["grc"], "risque": ["grc"],
    # sécurité de l'IA
    "ai security": ["ai-security"], "securite de l'ia": ["ai-security"],
    "llm": ["ai-security", "llm", "ai-agents"], "jailbreak": ["ai-security", "llm"],
    "prompt injection": ["ai-security", "llm"], "injection": ["ai-security"],
    "adversarial": ["ai-security", "research"], "robustness": ["ai-security", "research"],
    "red team": ["ai-security", "security-ops"], "safety": ["ai-security"],
    # offensif / défensif (purple team, SOC…) — le vécu défendable le plus
    # proche est la sécurité opérationnelle + les campagnes d'attaques LLM
    "purple team": ["security-ops", "ai-security"], "blue team": ["security-ops"],
    "pentest": ["security-ops"], "intrusion": ["security-ops"],
    "siem": ["security-ops"], "edr": ["security-ops"],
    "detection": ["security-ops"], "incident": ["security-ops"],
    "transformer": ["transformers", "ai-security"], "poisoning": ["ai-security"],
    "quantum": ["quantum"], "quantique": ["quantum"],
    "research": ["research"], "recherche": ["research"],
    # agents / automatisation
    "agent": ["ai-agents", "automation"], "agents": ["ai-agents", "automation"],
    "automation": ["automation", "ai-agents"], "automatisation": ["automation", "ai-agents"],
    "workflow": ["automation", "ai-agents"], "orchestration": ["automation", "ai-agents"],
    "langchain": ["ai-agents"], "rag": ["ai-agents"], "n8n": ["automation", "ai-agents"],
    "fine-tuning": ["ai-agents"], "prompt": ["ai-agents"],
    "multi-step": ["ai-agents"], "multi-turn": ["ai-agents"],
    # dev / intégration
    "python": ["python"], "javascript": ["web", "python"], "sql": ["python", "data"],
    "api": ["api"], "backend": ["api", "python"], "rest": ["api"],
    "oauth": ["api"], "webhook": ["api", "automation"],
    "flask": ["python", "api"], "fastapi": ["python", "api"],
    "gmail": ["api", "automation", "ai-agents"], "microsoft graph": ["api"],
    "supabase": ["api", "data"], "database": ["data", "api"],
    # web / e-commerce / mobile
    "wordpress": ["web"], "woocommerce": ["e-commerce", "web"],
    "shopify": ["e-commerce"], "prestashop": ["e-commerce"],
    "e-commerce": ["e-commerce", "web"], "ecommerce": ["e-commerce", "web"],
    "mobile": ["mobile"], "android": ["mobile"], "ios": ["mobile"],
    "paiement": ["payments"], "payment": ["payments"], "stripe": ["payments"],
    # ops / infra / embarqué
    "active directory": ["security-ops"], "vulnerab": ["security-ops"],
    "firewall": ["security-ops"], "soc": ["security-ops"],
    "linux": ["infra", "security-ops"], "docker": ["infra"],
    "embedded": ["embedded"], "embarque": ["embedded"], "gstreamer": ["embedded", "video"],
    "video": ["video"], "hpc": ["hpc"], "slurm": ["hpc"], "gpu": ["hpc"],
    "banque": ["banking"], "bank": ["banking"], "finance": ["banking"],
    # contenu / communication
    "content": ["content"], "youtube": ["content", "video"],
    "documentation": ["communication"], "feedback": ["communication"],
    "training data": ["ai-agents", "content"],
    # conseil / relation client (cabinets : Synetis, Wavestone, Formind…)
    "conseil": ["consulting"], "consultant": ["consulting"], "consulting": ["consulting"],
    "cabinet": ["consulting"], "client": ["consulting", "client"],
    "clients": ["consulting", "client"], "avant-vente": ["consulting"],
    "restitution": ["consulting", "communication"],
    # sensibilisation / formation (volet GRC + communication)
    "sensibilisation": ["communication", "content", "grc"],
    "awareness": ["communication", "content", "grc"],
    "formation": ["communication"], "training": ["communication"],
    "pedagogie": ["communication", "content"],
    "mentorat": ["communication", "consulting"], "mentoring": ["communication", "consulting"],
    "coaching": ["communication", "consulting"],
    # gouvernance : compléments fréquents dans les offres FR
    "pssi": ["grc"], "smsi": ["grc"], "isms": ["grc"],
    "crise": ["grc"], "crisis": ["grc"], "continuite": ["grc"],
    "resilience": ["grc"], "22301": ["grc"],
    # gouvernance de l'IA (PSSI-IA Formind : EU AI Act, ISO 42001)
    "ai act": ["ai-governance", "grc"], "42001": ["ai-governance", "grc"],
    "ia de confiance": ["ai-governance", "ai-security"],
    "trustworthy ai": ["ai-governance", "ai-security"],
    "ia responsable": ["ai-governance"], "responsible ai": ["ai-governance"],
    # tests / QA (campagne de tests LLM à l'UQAC)
    "test": ["testing"], "tests": ["testing"], "testing": ["testing"],
    "pytest": ["testing", "python"], "unittest": ["testing", "python"],
    "non-regression": ["testing"], "non regression": ["testing"],
    "regression": ["testing"], "qa": ["testing"],
    "validation fonctionnelle": ["testing"], "recette": ["testing"],
    "benchmark": ["testing", "data"], "tdd": ["testing"],
    # IAM / gestion des identités et des accès (force réelle : Wallix WCA-P,
    # RSA SecurID, Active Directory dans le vécu BOA/Formind). Ces offres
    # (Proton, Felps, Devoteam IAM…) ne matchaient jusqu'ici que par catégorie.
    "iam": ["security-ops", "grc"], "identity": ["security-ops", "grc"],
    "identite": ["security-ops", "grc"], "identities": ["security-ops", "grc"],
    "access management": ["security-ops", "grc"], "iga": ["security-ops", "grc"],
    "gestion des acces": ["security-ops", "grc"], "gestion des identites": ["security-ops", "grc"],
    "entra": ["security-ops"], "entra id": ["security-ops"], "azure ad": ["security-ops"],
    "sso": ["security-ops"], "pam": ["security-ops", "grc"], "okta": ["security-ops"],
    "wallix": ["security-ops", "grc"], "sailpoint": ["security-ops"],
    "habilitation": ["security-ops", "grc"], "annuaire": ["security-ops"],
    "rsa securid": ["security-ops"], "cyberark": ["security-ops"],
    # Risque tiers / résilience opérationnelle (banque, assurance : HSBC,
    # Deloitte, DORA). Volet gouvernance très demandé côté GRC bancaire.
    "tiers": ["grc", "banking"], "third party": ["grc", "banking"],
    "third-party": ["grc", "banking"], "tprm": ["grc", "banking"],
    "sous-traitance": ["grc", "banking"], "outsourcing": ["grc", "banking"],
    "supplier risk": ["grc", "banking"], "risque fournisseur": ["grc", "banking"],
    "business continuity": ["grc"], "continuity": ["grc"],
    "pca": ["grc"], "pra": ["grc"], "resilience operationnelle": ["grc"],
    "operational resilience": ["grc"],
}

# Aligné sur config.JOB_CATEGORIES (matching par inclusion, insensible casse/accents).
CATEGORY_TO_TAGS = {
    "cyber grc": ["grc", "ai-governance"],
    "cyber technique": ["security-ops", "infra", "grc"],
    "ai security": ["ai-security", "llm", "research"],
    "ai governance": ["ai-governance", "grc"],
    "ai engineer": ["ai-agents", "automation", "python", "api"],
    "python/automation": ["python", "automation", "api"],
    # anciens libellés (offres d'exemple / rétrocompatibilité)
    "ai engineering": ["ai-agents", "automation", "python", "api"],
    "software": ["python", "api", "web"],
    "security ops": ["security-ops", "grc"],
}

UI_STRINGS = {
    "fr": {"profile": "Profil", "experience": "Expérience", "projects": "Projets",
           "education": "Formation", "skills": "Compétences techniques",
           "certifications": "Certifications", "languages": "Langues",
           "soft": "Compétences transversales",
           "interests": "Centres d'intérêt", "tech": "Technologies principales : "},
    "en": {"profile": "Profile", "experience": "Experience", "projects": "Projects",
           "education": "Education", "skills": "Technical Skills",
           "certifications": "Certifications", "languages": "Languages",
           "soft": "Soft skills",
           "interests": "Interests", "tech": "Key technologies: "},
}

MAX_BULLETS_PER_EXP = {"uqac": 3, "freelance": 3, "formind": 2, "boa": 2,
                       "yemunivers": 2, "poulet-braise": 1}
MAX_PROJECTS = 3
SCORED_EXP_THRESHOLD = 2.0   # score de tags minimal pour inclure une exp "scored"


def norm(s: str) -> str:
    """minuscules + sans accents, pour un matching robuste."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Nommage des fichiers CV : CV_{Entreprise}_{RôleDistinctif} (ex. CV_Thales_PurpleTeam),
# plus lisible que l'ancien slug intégral "thales-consultant-cybersecurite-purple-team-h-f".
_CO_NOISE = {"sas", "sasu", "sarl", "sa", "sl", "inc", "ltd", "llc", "gmbh",
             "corp", "corporation", "group", "groupe", "france", "europe", "intl"}
# Marqueurs genre / contrat, purs bruits d'intitulé.
_TITLE_NOISE = {
    "hf", "fh", "mf", "fm", "hfx", "xfm", "fmx", "wm", "mw", "fnh", "fnm", "hfd", "mfd",
    "h", "f", "m", "x", "w", "nb", "cdi", "cdd", "stage", "alternance", "apprentissage",
    "freelance", "interim", "poste", "de", "du", "des", "d", "la", "le", "les", "l",
    "en", "et", "ou", "pour", "un", "une", "au", "aux", "the", "and", "for", "of", "to",
    "a", "an", "with", "our", "your", "dans", "sur", "avec", "par", "sans", "sous",
    "vers", "chez", "ses", "son", "sa", "leur", "leurs", "ce", "cette", "que", "qui",
    "plus", "at", "in", "on",
}
# Mots de rôle génériques : retirés pour dégager la partie distinctive de l'intitulé,
# mais conservés en repli si rien de plus spécifique ne subsiste.
_TITLE_GENERIC = {
    "consultant", "consultante", "consultants", "ingenieur", "ingenieure", "ingenieurs",
    "senior", "junior", "confirme", "confirmee", "expert", "experte", "lead", "manager",
    "responsable", "chef", "cheffe", "charge", "chargee", "developpeur", "developpeuse",
    "cybersecurite", "cyber", "securite", "security", "informatique", "technique",
    "si", "ssi", "it", "specialiste", "analyste", "architecte", "officer", "engineer",
    "administrateur", "technicien", "conseil", "conseiller", "stagiaire",
}


def _pascal(tokens, max_tokens=3, max_len=26) -> str:
    out, total = [], 0
    for t in tokens:
        if not t:
            continue
        out.append(t[:1].upper() + t[1:])
        total += len(t)
        if len(out) >= max_tokens or total >= max_len:
            break
    return "".join(out)


def cv_basename(offer: dict) -> str:
    """Nom de fichier lisible pour le CV : CV_{Entreprise}_{RôleDistinctif}."""
    raw_co = re.split(r"[|,;/]", offer.get("company", "") or "")[0]
    co_tokens = [w for w in re.findall(r"[a-z0-9]+", norm(raw_co)) if w not in _CO_NOISE]
    company = _pascal(co_tokens, max_tokens=3, max_len=24) or "Entreprise"

    title = re.sub(r"\([^)]*\)", " ", offer.get("title", "") or "")  # retire (H/F) etc.
    toks = [w for w in re.findall(r"[a-z0-9]+", norm(title)) if w not in _TITLE_NOISE]
    distinctive = [w for w in toks if w not in _TITLE_GENERIC]
    role = _pascal(distinctive or toks, max_tokens=3, max_len=26) or "Poste"
    return f"CV_{company}_{role}"


def L(field, lang):
    """Champ localisé : accepte str ou {fr:..., en:...}."""
    if isinstance(field, dict):
        return field.get(lang) or field.get("fr") or field.get("en") or ""
    return field or ""


def extract_offer_tags(offer: dict) -> dict:
    """Transforme l'offre en poids de tags {tag: poids}."""
    text = norm(" ".join([
        offer.get("title", ""), offer.get("description", ""),
        " ".join(offer.get("keywords", []) or []),
    ]))
    weights = {}
    for kw, tags in KEYWORD_TO_TAGS.items():
        # nombre d'occurrences du mot-clé dans l'offre (plafonné à 3)
        n = min(len(re.findall(r"\b" + re.escape(norm(kw)) + r"\b", text)), 3)
        if n:
            for t in tags:
                weights[t] = weights.get(t, 0) + n
    cat = norm(offer.get("category", ""))
    for c, tags in CATEGORY_TO_TAGS.items():
        if c in cat:
            for t in tags:
                weights[t] = weights.get(t, 0) + 3  # la catégorie pèse lourd
    # le titre pèse double
    title = norm(offer.get("title", ""))
    for kw, tags in KEYWORD_TO_TAGS.items():
        if re.search(r"\b" + re.escape(norm(kw)) + r"\b", title):
            for t in tags:
                weights[t] = weights.get(t, 0) + 2
    return weights


def score_tags(item_tags, weights) -> float:
    return sum(weights.get(t, 0) for t in item_tags)


def select_content(master: dict, weights: dict, lang: str) -> dict:
    """Cœur du système : choisit et ordonne le contenu selon l'offre."""
    # --- Expériences ---
    # 1er passage : éligibilité + score, pour attribuer un bonus de bullets
    # aux expériences les plus pertinentes pour l'offre.
    eligible = []
    for e in master["experiences"]:
        s = score_tags(e["tags"], weights)
        if e["include"] == "never":
            continue
        if e["include"] == "scored" and s < SCORED_EXP_THRESHOLD:
            continue
        eligible.append((e, s))
    by_relevance = sorted(eligible, key=lambda x: -x[1])
    bullet_bonus = {}
    if by_relevance:
        bullet_bonus[by_relevance[0][0]["id"]] = 2   # exp la plus pertinente
    if len(by_relevance) > 1:
        bullet_bonus[by_relevance[1][0]["id"]] = 1

    exps = []
    for e, s in eligible:
        # bullets : triés par score, on garde les k meilleurs, on préserve
        # ensuite l'ordre d'origine (qui raconte la bonne histoire)
        scored_b = sorted(e["bullets"], key=lambda b: -score_tags(b["tags"], weights))
        k = MAX_BULLETS_PER_EXP.get(e["id"], 3) + bullet_bonus.get(e["id"], 0)
        keep_ids = {b["id"] for b in scored_b[:k]}
        # garantir au moins 2 bullets même si l'offre ne matche pas
        if len(keep_ids) < 2:
            keep_ids |= {b["id"] for b in e["bullets"][:2]}
        kept = [b for b in e["bullets"] if b["id"] in keep_ids]
        bullets = [L(b[lang], lang) if isinstance(b.get(lang), dict) else b[lang]
                   for b in kept]
        exps.append({
            "id": e["id"], "score": s, "start": e.get("start", ""),
            "org": L(e["org"], lang), "role": L(e["role"], lang),
            "location": L(e["location"], lang), "dates": L(e["dates"], lang),
            "bullets": bullets,
            # scores parallèles aux bullets, pour que la boucle d'ajustement
            # retire le MOINS pertinent (et non le dernier de la liste)
            "bscores": [score_tags(b["tags"], weights) for b in kept],
            # une exp "scored" peut être retirée entièrement si la page déborde
            "optional": e["include"] != "always",
        })
    # Ordre ANTICHRONOLOGIQUE (attendu par les recruteurs et les ATS) :
    # la pertinence joue sur la sélection et le nombre de bullets, pas sur l'ordre.
    exps.sort(key=lambda x: x["start"], reverse=True)

    # --- Projets ---
    projs = sorted(master["projects"], key=lambda p: -score_tags(p["tags"], weights))
    projects = []
    for p in projs[:MAX_PROJECTS]:
        if score_tags(p["tags"], weights) <= 0 and len(projects) >= 2:
            break  # pas de remplissage hors-sujet
        projects.append({
            "name": L(p["name"], lang), "desc": L(p["desc"], lang),
            "tech": p["tech"], "bullets": [L(b, lang) for b in
                                           ([x[lang] for x in p["bullets"]])],
        })

    # --- Compétences : réordonnées par pertinence ---
    skills = sorted(master["skills"], key=lambda s: -score_tags(s["tags"], weights))
    skills_out = [{"label": L(s["label"], lang), "content": L(s["content"], lang)}
                  for s in skills]

    # --- Soft skills : top 6 par pertinence (avec plancher universel) ---
    ss = sorted(master.get("soft_skills", []),
                key=lambda x: -score_tags(x["tags"], weights))
    picked = ss[:6]
    # garantir communication + autonomie si absents (universels)
    have = {x["id"] for x in picked}
    for uid in ("ss-comm", "ss-auto"):
        if uid not in have:
            picked[-1] = next(x for x in ss if x["id"] == uid)
            have = {x["id"] for x in picked}
    soft = " • ".join(x[lang] for x in picked)

    return {"experiences": exps, "projects": projects, "skills": skills_out,
            "soft_skills": soft}


# Bruit de recrutement à retirer du titre d'offre avant affichage en headline.
_HEADLINE_NOISE = re.compile(
    r"\s*[-–—/|(]*\s*\b(h\s*/\s*f(\s*/\s*[xd])?|f\s*/\s*h(\s*/\s*[xd])?|"
    r"m\s*/\s*f(\s*/\s*[xd])?|m\s*/\s*w(\s*/\s*[xd])?|h/f/x|f/h/x|"
    r"cdi|cdd|all genders?)\b\s*[)\s]*",
    re.IGNORECASE,
)

# Grades qu'un jeune diplômé ne peut pas afficher honnêtement sous son nom :
# le titre reprend les mots-clés de l'offre (ATS), jamais un grade surévalué.
_GRADE_RE = re.compile(
    r"\b(senior|sr\.?|lead|principal|staff|head\s+of|chief|director|"
    r"directeur|directrice|manager|mgr|vp|vice[- ]?pr[ée]sident(?:e)?|"
    r"expert(?:e)?)\b",
    re.IGNORECASE,
)

# Si le titre commence déjà par un nom de rôle, inutile d'en préfixer un.
_ROLE_NOUNS = ("consultant", "ingenieur", "engineer", "analyste", "analyst",
               "auditeur", "auditrice", "auditor", "architecte", "architect",
               "developpeur", "developer", "chercheur", "researcher",
               "specialiste", "specialist", "pentester", "chef de projet")

# Villes/régions fréquentes en suffixe de titre d'offre ("… - Paris").
_CITY_RE = re.compile(
    r"(paris|lyon|marseille|lille|toulouse|bordeaux|nantes|rennes|strasbourg|"
    r"nice|montpellier|grenoble|ile[- ]de[- ]france|idf|la defense|"
    r"issy(?:[- ]les[- ]moulineaux)?|boulogne(?:[- ]billancourt)?|france|"
    r"montreal|toronto|quebec|ottawa|vancouver|chicoutimi|canada)"
)


def clean_headline(title: str, category: str = "", lang: str = "fr") -> str:
    """Intitulé affiché sous le nom : mots-clés exacts de l'offre (ATS), moins
    le bruit de recrutement (H/F, CDI…), les suffixes de ville et les grades
    surévalués (Senior/Manager/Director → remplacés par un rôle honnête)."""
    t = _HEADLINE_NOISE.sub(" ", title or "")
    t = re.sub(r"\(\s*\)", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" -–—|/,")

    # ville en fin de titre : "(Paris)" ou dernier segment "- Paris"
    t = re.sub(r"\(\s*" + _CITY_RE.pattern + r"\s*\)\s*$", "", t, flags=re.I).strip()
    parts = re.split(r"\s*[-–—|,]\s*", t)
    while len(parts) > 1 and _CITY_RE.fullmatch(norm(parts[-1]).strip("() ")):
        parts.pop()
    t = " - ".join(p for p in parts if p)

    # grade surévalué : retiré, puis rôle honnête préfixé si nécessaire
    if _GRADE_RE.search(t):
        t = _GRADE_RE.sub(" ", t)
        t = re.sub(r"\s{2,}", " ", t).strip(" -–—|/,")
        t = re.sub(r"^(?:en|de|d'|du|des|of|in|for)\s+", "", t, flags=re.I)
        # pas de préfixe si un nom de rôle figure déjà dans le titre restant
        tn = norm(t)
        if not any(re.search(r"\b" + rn.split()[0], tn) for rn in _ROLE_NOUNS):
            consulting = any(x in norm(category) for x in ("grc", "governance"))
            prefix = ("Consultant" if consulting
                      else ("Ingénieur" if lang == "fr" else "Engineer"))
            t = f"{prefix} {t}".strip()

    return re.sub(r"\s{2,}", " ", t).strip(" -–—|/,")


# Règle du projet : tout lien présent sur le CV doit être CLIQUABLE dans le
# PDF. Les domaines nus cités dans les textes (ai-sortify.com, lxtravelgroup.com…)
# sont enveloppés dans <a href="https://…"> ; l'en-tête (email/LinkedIn/GitHub)
# est géré directement par le template.
_DOMAIN_RE = re.compile(
    r"(?<![@\w/])((?:[a-zA-Z0-9-]+\.)+(?:com|fr|ca|io|ai|dev|net|org))\b"
)


def linkify(text: str) -> str:
    return _DOMAIN_RE.sub(r'<a href="https://\1">\1</a>', text or "")


# Termes supplémentaires "boldables" dans le profil (au-delà des clés de
# KEYWORD_TO_TAGS) : référentiels et notions qui apparaissent dans les variantes.
EXTRA_BOLD_TERMS = [
    "iso 27001", "27002", "22301", "pci dss", "swift csp", "ebios rm",
    "eu ai act", "ai act", "iso 42001", "42001",
    "gouvernance cyber", "cyber governance", "intelligence artificielle",
    "cybersecurite", "cybersecurity", "securite de l'ia", "ai security",
    "securite des modeles", "model security", "ia", "ai",
    "robustesse adversariale", "adversarial robustness", "data poisoning",
    "jailbreak", "freelance",
]


def bold_profile(profile: str, offer_text: str) -> str:
    """Met en <b> les termes du profil qui figurent AUSSI dans l'offre.
    Déterministe : candidats = mots-clés du matching + EXTRA_BOLD_TERMS ;
    un terme n'est mis en gras que si l'offre le mentionne."""
    offer_n = norm(offer_text)
    profile_n = norm(profile)  # norm préserve la longueur -> indices communs
    spans = []
    for kw in set(KEYWORD_TO_TAGS) | set(EXTRA_BOLD_TERMS):
        k = norm(kw)
        if len(k) < 2 or not re.search(r"\b" + re.escape(k) + r"\b", offer_n):
            continue
        for m in re.finditer(r"\b" + re.escape(k) + r"\b", profile_n):
            spans.append(m.span())
    if not spans:
        return profile
    # fusionner les chevauchements (ex. "ia" dans "securite de l'ia")
    spans.sort()
    merged = [list(spans[0])]
    for a, b in spans[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    out = profile
    for a, b in reversed(merged):
        out = out[:a] + "<b>" + out[a:b] + "</b>" + out[b:]
    return out


def select_profile(master: dict, weights: dict, lang: str) -> str:
    """Choisit la variante de profil la plus alignée sur l'offre (repli :
    profile_base). Aucune rédaction. La phrase de disponibilité est ajoutée
    par build_cv, hors mise en gras."""
    best, best_score = None, 0
    for v in master.get("profile_variants", []):
        s = score_tags(v["tags"], weights)
        if s > best_score:
            best, best_score = v, s
    return (best or master["profile_base"])[lang].strip()


def build_cv(offer: dict, country: str, master: dict, rules: dict, outdir: Path,
             hook=None):
    """Génère le CV ciblé (HTML + PDF).

    `hook(offer, lang)` : accroche LLM optionnelle (voir cvgen/accroche.py),
    insérée entre la variante de profil et la phrase de disponibilité.
    Par défaut (None) : profil 100 % déterministe, aucune rédaction LLM."""
    rule = rules[country]
    lang = rule["language"]
    weights = extract_offer_tags(offer)
    content = select_content(master, weights, lang)

    # Liens cliquables : linkifier les domaines cités dans les textes.
    for e in content["experiences"]:
        e["bullets"] = [linkify(b) for b in e["bullets"]]
    for p in content["projects"]:
        p["name"] = linkify(p["name"])
        p["desc"] = linkify(p["desc"])
        p["bullets"] = [linkify(b) for b in p["bullets"]]

    idn = master["identity"]
    degree_hint = rule.get("degree_hint", "")
    education = []
    for ed in master["education"]:
        if ed.get("optional") and rule["page_limit"] == 1 and len(master["education"]) > 1:
            continue  # on garde le CV sur 1 page
        deg = L(ed["degree"], lang)
        if degree_hint and "ing" in norm(deg):
            deg = f"{deg} {degree_hint}"
        education.append({"degree": deg, "school": ed["school"],
                          "location": L(ed["location"], lang),
                          "dates": L(ed["dates"], lang)})

    # Profil = variante taggée (mots-clés de l'offre en gras)
    #        + accroche LLM optionnelle + phrase de disponibilité (sans gras).
    offer_text = " ".join([offer.get("title", ""), offer.get("description", ""),
                           " ".join(offer.get("keywords", []) or [])])
    parts = [bold_profile(select_profile(master, weights, lang), offer_text)]
    if hook is not None:
        accroche = (hook(offer, lang) or "").strip()
        if accroche:
            parts.append(accroche)
    avail = (master.get("availability") or {}).get(lang, "").strip()
    if avail:
        parts.append(avail)
    profile_text = " ".join(parts)

    tpl = Template((HERE / "template_cv.html").read_text(encoding="utf-8"))

    def render(c, interests_on=True):
        return tpl.render(
            lang=lang, T=UI_STRINGS[lang], colon=(" :" if lang == "fr" else ":"),
            identity=idn,
            headline=clean_headline(offer.get("title", ""),
                                    offer.get("category", ""), lang),
            phone=idn["phones"][rule["phone_key"]],
            address=idn["addresses"][rule["address_key"]],
            profile_text=profile_text,
            experiences=c["experiences"],
            projects=c["projects"],
            education=education,
            skills=c["skills"],
            certifications=master["certifications"],
            soft_skills=c.get("soft_skills", "") if rule.get("show_soft_skills", True) else "",
            languages=master["languages"][lang] if not rule["show_languages_cefr"]
                      or lang == "en" else master["languages"]["fr"],
            interests=(master["interests"][lang] if rule["show_interests"] and interests_on else ""),
        )

    def n_pages(html):
        return _pdf_engine().count_pages(html)

    # --- Boucle d'auto-ajustement : dégrader gracieusement JUSQU'À tenir ---
    # Leviers essayés dans l'ordre à chaque itération (du moins douloureux au
    # plus douloureux) ; la boucle tourne tant que la page déborde et qu'il
    # reste quelque chose à retirer.
    interests_on = True

    def _pop_bullet(min_bullets: int) -> bool:
        """Retire le bullet le moins pertinent de l'exp la moins pertinente
        (plancher min_bullets). L'ordre d'affichage étant chronologique, la
        pertinence se lit dans les scores. Égalité -> dernier du YAML."""
        candidates = [e for e in content["experiences"] if len(e["bullets"]) > min_bullets]
        if not candidates:
            return False
        e = min(candidates, key=lambda e: e["score"])
        bs = e["bscores"]
        i = len(bs) - 1 - bs[::-1].index(min(bs))
        e["bullets"].pop(i)
        e["bscores"].pop(i)
        return True

    def shrink_once() -> bool:
        nonlocal interests_on
        if interests_on:
            interests_on = False
            return True
        if len(content["skills"]) > 3:
            content["skills"].pop()            # le moins pertinent (déjà trié)
            return True
        if len(content["projects"]) > 2:
            content["projects"].pop()
            return True
        if _pop_bullet(2):
            return True
        # Derniers recours, par ordre de douleur croissante :
        optionals = [e for e in content["experiences"] if e.get("optional")]
        if optionals:                          # retirer une exp "scored" entière
            content["experiences"].remove(min(optionals, key=lambda e: e["score"]))
            return True
        if len(content["projects"]) > 1:
            content["projects"].pop()
            return True
        if len(content["skills"]) > 2:
            content["skills"].pop()
            return True
        return _pop_bullet(1)                  # plancher absolu : 1 bullet/exp

    html = render(content, interests_on)
    for _ in range(40):                        # garde-fou anti-boucle infinie
        if n_pages(html) <= rule["page_limit"]:
            break
        if not shrink_once():
            break                              # plus rien à retirer
        html = render(content, interests_on)
    pages = n_pages(html)

    base = cv_basename(offer)
    outdir.mkdir(parents=True, exist_ok=True)
    html_path = outdir / f"{base}.html"
    html_path.write_text(html, encoding="utf-8")

    pdf_path = outdir / f"{base}.pdf"
    try:
        _pdf_engine().write_pdf(html, pdf_path)
        print(f"[OK] {pdf_path} ({pages} page(s))")
    except Exception as exc:  # aucun moteur PDF : le HTML reste utilisable
        print(f"[WARN] PDF non généré ({exc}) — HTML disponible : {html_path}")
        pdf_path = None
    return html_path, pdf_path


def _pdf_engine():
    """Import paresseux du moteur PDF (package ou script)."""
    try:
        from . import pdf_engine
    except ImportError:
        import pdf_engine
    return pdf_engine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offer", required=True, help="fichier JSON de l'offre")
    ap.add_argument("--country", default=None, help="fr | ca-qc | ca-en | intl (défaut : champ 'country' de l'offre)")
    ap.add_argument("--out", default="out", help="dossier de sortie")
    args = ap.parse_args()

    offer = json.loads(Path(args.offer).read_text(encoding="utf-8"))
    country = args.country or offer.get("country") or "fr"
    master = yaml.safe_load((HERE / "profile_master.yaml").read_text(encoding="utf-8"))
    rules = yaml.safe_load((HERE / "country_rules.yaml").read_text(encoding="utf-8"))
    if country not in rules:
        sys.exit(f"Pays inconnu : {country} (choix : {', '.join(rules)})")

    build_cv(offer, country, master, rules, Path(args.out))


if __name__ == "__main__":
    main()
