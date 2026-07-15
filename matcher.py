import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

import json
from datetime import datetime
from pathlib import Path

import data_loader
import litellm
from litellm import acompletion
from google import genai
import utils
import config
import prefilter
import llm_logger

load_dotenv(Path(__file__).parent.parent / ".env")
logger = utils.setup_logging("matcher")

CRITERES_FILE = config.DATA_DIR / "criteres.md"

SYSTEM_PROMPT = """
Tu es un évaluateur d'offres d'emploi (CDI/CDD) en cybersécurité et en intelligence artificielle. Tu analyses chaque offre selon un profil candidat et retournes un score JSON.

## ÉTAPE 1 — CRITÈRES ÉLIMINATOIRES (vérifie en premier, stop si déclenché)
- Pas un CDI ni un CDD (stage, alternance, apprentissage, freelance, intérim) → score = 0
- Aucun lien avec cybersécurité, IA, software ou Python (ex: commercial pur, RH, comptabilité, logistique sans dimension technique) → score = 0
- Poste commercial / vente / avant-vente / business development / account management, MÊME dans une entreprise de cybersécurité ou d'IA (ex: "Ingénieur Commercial Cybersécurité") → score = 0
- Sécurité PHYSIQUE : gardiennage, sûreté des sites/personnes, supervision de sécurité physique, prévention incendie (ex: "Security Supervisor" d'un site) → score = 0
- Lutte contre la fraude (fraude bancaire, fraude aux paiements, fraude documentaire) sans ingénierie de sécurité des SI → score = 0
- GRC / risques / conformité / audit / contrôle PUREMENT financiers, bancaires ou réglementaires, sans dimension sécurité des SI explicite : risques financiers ou prudentiels, résolution bancaire, contrôle interne, audit financier ou comptable, conformité KYC / LCB-FT / Sapin II / anticorruption → score = 0
- RÈGLE IMPORTANTE : les mots "risques", "conformité", "gouvernance", "audit", "contrôle" ne comptent comme cybersécurité QUE si l'offre porte explicitement sur la sécurité des systèmes d'information (ISO 27001, SMSI, PSSI, SSI, SOC, EBIOS RM, NIS2, DORA volet cyber, homologation...). En cas de doute sur la dimension cyber → considère l'offre hors cible (score = 0).
- Expérience minimale exigée STRICTEMENT supérieure à 3 ans (ex: "4 ans", "5+ years", "5 à 8 ans", "minimum 6 ans") → score = 0. ACCEPTÉ : exigence de 3 ans ou moins, fourchette démarrant à 3 ans ou moins (ex: "3 à 5 ans"), ou aucune mention d'expérience. ATTENTION : ne pas confondre avec l'ancienneté de l'entreprise ("depuis plus de 20 ans, notre société...").
- Poste senior ou de direction DE FAIT, quand AUCUNE exigence d'années n'est précisée : Head of / Director / Chief / CISO / RSSI titulaire (un ADJOINT reste acceptable) / Senior / Lead / Principal / Staff / Manager d'équipe / Responsable de service → score = 0. PRIORITÉ : si l'offre précise des années, c'est la règle des années ci-dessus qui s'applique (un "Consultant Senior" à "3 ans minimum" est ACCEPTÉ). Exception : postes explicitement ouverts aux jeunes diplômés (ex: armées, ministères avec formation intégrée).
- Contrat freelance / portage salarial / intérim → score = 0 (rappel : seuls CDI et CDD sont acceptés).
- Techno principale legacy sans rapport (COBOL, Fortran, LabVIEW) → score = 0
- Poste hors de France, OU exigeant une EXPATRIATION / relocation / mobilité à l'étranger (même si l'annonce est localisée en France, ex. "expatriation aux Pays-Bas"), NON réalisable en full remote depuis la France → score = 0. Le candidat ne veut PAS s'installer à l'étranger. En revanche : un poste en France (tous modes) OU un poste étranger 100 % télétravail faisable depuis la France est ACCEPTÉ.

## ÉTAPE 2 — SCORE DE BASE
Commence à 50 si aucun critère éliminatoire n'est déclenché.

## ÉTAPE 3 — BONUS (cumulables, domaines cibles)
- Cybersécurité GRC — gouvernance / conformité / risques / audit DE LA SÉCURITÉ DES SI (ISO 27001, SMSI, PSSI, EBIOS RM, NIS2, DORA, homologation) → +20 (jamais pour la GRC financière/bancaire, voir critères éliminatoires)
- Gouvernance de l'IA (AI Governance / AI Risk / Responsible AI) → +20
- Sécurité de l'IA / LLM Security / sécurité des modèles → +20
- Cybersécurité technique (cloud security, AppSec, IAM / gestion des accès) → +15
- AI Engineer : agents, RAG, orchestration LLM, intégration IA → +10
- Développement Python orienté IA, automatisation ou cybersécurité → +10
- Poste accessible à un profil junior / jeune diplômé (0-3 ans d'expérience) → +5
- Télétravail : hybride → +5 ; full remote → +10 ; remote international / work-from-anywhere → +10
- CDI (poste stable) → +5

## ÉTAPE 4 — MALUS
- Description vague, périmètre/stack non mentionnés → -10
- Séniorité modérée exigée (3 ans demandés, poste "confirmé") → -5 (léger : le candidat junior reste éligible ; la séniorité STRICTEMENT > 3 ans est déjà éliminatoire, voir ÉTAPE 1)

## SCORE FINAL
- Additionne base + bonus - malus
- Clamp entre 0 et 100
- Ne jamais inventer des infos absentes : si non mentionné → neutre (pas de bonus, pas de malus)

## ORIENTATION (axe grossier)
- Cybersécurité dominante → "Cyber"
- IA dominante → "IA"
- Les deux (ex: AI Security, sécurité des LLM) → "Cyber+IA"

## CATEGORIE (domaine principal de l'offre)
Choisis UNE valeur dans la liste de categories fournie a la fin de ce prompt.
La categorie doit etre juste meme si le score est faible.

## TAGS
3 a 5 mots-cles techniques concrets detectes dans l'offre (outils, frameworks,
normes : ex ["Python", "ISO 27001", "Azure", "SIEM", "LangChain"]). Pas de phrases.

## FORMAT JSON uniquement, aucun texte autour
{
  "score": 0-100,
  "resume_ia": "5 lignes max : domaine & stack | type de contrat | adéquation profil | niveau/séniorité | télétravail & intérêt",
  "raisons_score": "Base 50 + [bonus] - [malus] = X",
  "tags": ["tag1", "tag2", "tag3"],
  "orientation": "Cyber | IA | Cyber+IA",
  "categorie": "une valeur de la liste fournie",
  "salaire": "fourchette exacte si mentionnée dans l'offre (ex: '45-55 k€', '80k CAD', '$120k'), sinon 'Non précisé'. Ne jamais inventer.",
  "note_remuneration": "0-100 : niveau de rémunération estimé (basé sur le salaire si présent, sinon selon poste/séniorité/secteur/pays)",
  "note_entreprise": "0-100 : qualité / réputation / intérêt de l'entreprise",
  "note_flexibilite": "0-100 : 0 = présentiel strict, 60 = hybride, 100 = full remote international / work-from-anywhere",
  "note_evolution": "0-100 : perspectives d'évolution et de montée en compétence"
}
"""


def build_system_prompt() -> str:
    """SYSTEM_PROMPT + liste des categories injectee dynamiquement depuis config.

    Permet de garder SYSTEM_PROMPT editable depuis le dashboard tout en pilotant
    la taxonomie via config.JOB_CATEGORIES (modifiable sans toucher au prompt).
    """
    categories = getattr(config, "JOB_CATEGORIES", ["SWE/Web", "AI Engineer", "Autre"])
    cats = " | ".join(categories)
    return f"{SYSTEM_PROMPT}\n\n## Categories disponibles (categorie)\nChoisis exactement une valeur parmi : {cats}\n"

SCORE_PROMPT = """
Évalue la pertinence de cette offre d'emploi (CDI/CDD) pour le profil candidat ci-dessous.

## Offre à analyser
- Titre : {titre}
- Entreprise : {entreprise}
- Localisation : {localisation}
- Description : {description}

## Profil candidat
{profil}

Applique les critères éliminatoires en premier. Si aucun n'est déclenché, calcule le score avec les bonus.
Réponds uniquement avec ce JSON:
{{
  "score": 0-100,
  "resume_ia": "5 lignes max: domaine & stack, type de contrat, points adaptation CV, niveau attendu, télétravail & intérêt",
  "raisons_score": "Explication courte du score",
  "tags": ["tag1", "tag2"],
  "orientation": "Cyber | IA | Cyber+IA",
  "categorie": "une valeur de la liste fournie",
  "salaire": "fourchette si mentionnée, sinon 'Non précisé' (ne jamais inventer)",
  "note_remuneration": 0-100,
  "note_entreprise": 0-100,
  "note_flexibilite": 0-100,
  "note_evolution": 0-100
}}
"""



class LLMRouter:
    def __init__(self):
        self.quotas = config.LLM_QUOTAS
        self.counters = {key: 0 for key in self.quotas.keys()}
        self.pause_counters = {key: 0 for key in self.quotas.keys()}
        self.failed_providers = set()
        self.last_reset = datetime.now().date()
        self.last_used_provider = None
        self.openrouter_alternate = False

    def can_use_provider(self, provider: str) -> tuple[bool, str]:
        """Check if provider is available. Returns (available, reason)."""
        quota = self.quotas.get(provider, {})
        current = self.counters.get(provider, 0)
        limit = quota.get("daily_limit", 999999)

        if provider in self.failed_providers:
            return False, f"FAILED previously in this job"

        # Slot sans clé API configurée -> ignoré (aucun essai gaspillé). Permet
        # d'ajouter des clés Gemini/Groq sans code : les GEMINI_API_KEY_N absentes
        # du .env sautent automatiquement.
        api_key_env = quota.get("api_key_env")
        if api_key_env and not os.getenv(api_key_env):
            return False, f"{provider}: clé {api_key_env} absente"

        # daily_limit est la SEULE source de verite du plafond (Gemini compris).
        if current >= limit:
            return False, f"{provider}: {current}/{limit} (LIMITE ATTEINTE)"
        return True, f"{provider}: {current}/{limit} OK"

    def check_quota(self, provider: str) -> bool:
        if datetime.now().date() > self.last_reset:
            self.counters = {key: 0 for key in self.quotas.keys()}
            self.pause_counters = {key: 0 for key in self.quotas.keys()}
            self.failed_providers = set()
            self.last_reset = datetime.now().date()
            self.openrouter_alternate = False
            logger.info("Daily quotas reset")

        available, _ = self.can_use_provider(provider)
        return available

    def mark_provider_failed(self, provider: str):
        self.failed_providers.add(provider)

    def reset_failed_providers(self):
        self.failed_providers = set()

    def get_next_provider(self, job_index: int) -> Optional[str]:
        """Rotation circulaire sur les slots Groq, puis fallback Gemini (toutes les
        clés) puis OpenRouter. La liste des fallbacks est construite dynamiquement
        depuis config.LLM_QUOTAS : ajouter une clé Gemini = ajouter un slot ici."""

        # Rotation circulaire Groq
        groq_rotation = config.GROQ_ROTATION
        preferred = groq_rotation[job_index % len(groq_rotation)]

        # On essaie le Groq préféré en premier
        available, reason = self.can_use_provider(preferred)
        if available:
            logger.info(f"[SELECT] {preferred} (rotation {job_index % len(groq_rotation)}): {reason}")
            return preferred
        else:
            logger.warning(f"[SKIP] {preferred}: {reason}")

        # Si le Groq préféré est épuisé/sans clé, on essaie les autres Groq
        for provider in groq_rotation:
            if provider == preferred:
                continue
            available, reason = self.can_use_provider(provider)
            if available:
                logger.info(f"[SELECT] {provider} (Groq fallback): {reason}")
                return provider
            logger.warning(f"[SKIP] {provider}: {reason}")

        # Tous les Groq épuisés → fallbacks : Gemini d'abord (rapide mais ~20
        # req/jour/clé en free tier), puis NVIDIA NIM (sans plafond journalier
        # mais lent aux heures de pointe : à garder en dernier recours), puis
        # OpenRouter.
        nvidia_providers = [k for k in self.quotas if k.startswith("nvidia")]
        gemini_providers = [k for k in self.quotas if k.startswith("gemini")]
        openrouter_providers = [k for k in self.quotas if k.startswith("openrouter")]
        for provider in gemini_providers + nvidia_providers + openrouter_providers:
            available, reason = self.can_use_provider(provider)
            if available:
                logger.info(f"[SELECT] {provider} (fallback): {reason}")
                return provider
            logger.warning(f"[SKIP] {provider}: {reason}")

        return None

    def _log_quota_call(self, provider: str, success: bool):
        try:
            history_path = config.LOGS_DIR / "quota_history.json"
            today = datetime.now().strftime("%Y-%m-%d")
            history = {}
            if history_path.exists():
                history = json.loads(history_path.read_text(encoding="utf-8"))
            day = history.setdefault(today, {})
            prov = day.setdefault(provider, {"used": 0, "success": 0, "fail": 0})
            prov["used"] += 1
            if success:
                prov["success"] += 1
            else:
                prov["fail"] += 1
            history_path.write_text(
                json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass

    async def _handle_pause(self, provider: str):
        quota = self.quotas[provider]
        pause_every = quota.get("pause_every")
        pause_duration = quota.get("pause_duration")
        
        if pause_every and self.pause_counters[provider] >= pause_every:
            logger.info(f"Pause {pause_duration}s after {pause_every} requests on {provider}")
            await asyncio.sleep(pause_duration)
            self.pause_counters[provider] = 0
    
    async def call_provider(self, prompt: str, provider: str) -> Optional[str]:
        self.counters[provider] += 1
        self.pause_counters[provider] += 1
        self.last_used_provider = provider

        quota = self.quotas[provider]
        model = quota["model"]

        if "groq" in provider:
            result = await self._call_groq(prompt, model, provider)  # ← Pass provider
        elif "gemini" in provider:
            result = await self._call_gemini(prompt, provider)  # ← clé par slot
        elif "nvidia" in provider:
            result = await self._call_nvidia(prompt, model, provider)
        elif "openrouter" in provider:
            result = await self._call_openrouter(prompt, model)
        else:
            result = None

        self._log_quota_call(provider, success=result is not None)

        if result:
            await self._handle_pause(provider)

        return result

    async def _call_groq(self, prompt: str, model: str, provider: str) -> Optional[str]:
        try:
            # Get API key from config based on provider
            api_key_env = config.LLM_QUOTAS[provider].get("api_key_env", "GROQ_API_KEY_1")
            api_key = os.getenv(api_key_env)
            
            # Models that don't support json_object mode
            NO_JSON_MODE = ["qwen3", "qwen/qwen3"]
            use_json_mode = not any(m in model.lower() for m in NO_JSON_MODE)
            
            kwargs = {
                "model": model,
                "api_key": api_key,  # Explicit key per account
                "messages": [
                    {"role": "system", "content": build_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1024,
            }
            
            if use_json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            else:
                # For Qwen3: reinforce JSON in prompt
                kwargs["messages"][-1]["content"] += "\n\nIMPORTANT: Reply with JSON only, no text before or after the JSON object."
            
            response = await acompletion(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            if "rate limit" in error_msg.lower() and "retry in" in error_msg.lower():
                match = re.search(r"retry in ([\d.]+)", error_msg)
                if match:
                    retry_seconds = float(match.group(1)) + 1
                    logger.warning(f"Rate limit hit, waiting {retry_seconds:.1f}s")
                    await asyncio.sleep(retry_seconds)
            logger.warning(f"Groq call failed ({model}): {e}")
            return None

    async def _call_nvidia(self, prompt: str, model: str, provider: str) -> Optional[str]:
        """NVIDIA NIM (endpoint OpenAI-compatible via litellm). Pas de mode
        json_object garanti selon les modèles : on renforce le JSON en prompt,
        parse_llm_response extrait l'objet."""
        try:
            api_key_env = config.LLM_QUOTAS[provider].get("api_key_env", "NVIDIA_NIM_API_KEY")
            api_key = os.getenv(api_key_env)
            response = await acompletion(
                model=model,
                api_key=api_key,
                messages=[
                    {"role": "system", "content": build_system_prompt()},
                    {"role": "user", "content": prompt +
                     "\n\nIMPORTANT: Reply with JSON only, no text before or after the JSON object."},
                ],
                max_tokens=1024,
                temperature=0.1,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"NVIDIA NIM call failed ({model}): {e}")
            return None

    async def _call_gemini(self, prompt: str, provider: str = "gemini_1") -> Optional[str]:
        try:
            # Clé propre au slot (GEMINI_API_KEY_1, _2, ...).
            api_key_env = config.LLM_QUOTAS.get(provider, {}).get("api_key_env", "GEMINI_API_KEY_1")
            api_key = os.getenv(api_key_env)
            model = config.LLM_QUOTAS.get(provider, {}).get("model", "gemini-2.5-flash-lite")
            client = genai.Client(api_key=api_key)
            full_prompt = f"{build_system_prompt()}\n\n{prompt}"

            response = client.models.generate_content(
                model=model,
                contents=[full_prompt],
                config={
                    "response_mime_type": "application/json",
                    "max_output_tokens": 1024,
                }
            )
            return response.text
        except Exception as e:
            logger.warning(f"Gemini call failed ({provider}): {e}")
            return None

    async def _call_openrouter(self, prompt: str, model: str) -> Optional[str]:
        try:
            response = await acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": build_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=1024,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"OpenRouter call failed ({model}): {e}")
            return None

    async def get_delay(self, provider: str) -> float:
        return self.quotas[provider]["delay_seconds"]


def _clamp_note(v: Any) -> int:
    """Convertit une note en entier borné 0-100 (None-safe)."""
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        n = 0
    return max(0, min(100, n))


def compute_global_score(result: Dict[str, Any], weights: Optional[Dict[str, float]] = None) -> int:
    """Score global (0-100) = moyenne pondérée des axes, gardé à 0 si le fit est 0.

    Le fit (result['score']) reste l'éliminatoire : une offre écartée (hors cible,
    mauvais contrat, étranger non-remote) a un score global de 0, peu importe les
    autres axes. Sinon on combine fit + rémunération + flexibilité + entreprise +
    évolution selon config.RANKING_WEIGHTS.
    """
    fit = result.get("score", 0) or 0
    if fit <= 0:
        return 0
    weights = weights or getattr(config, "RANKING_WEIGHTS", {"fit": 1.0})
    axes = {
        "fit": fit,
        "remuneration": result.get("note_remuneration", 0) or 0,
        "flexibilite": result.get("note_flexibilite", 0) or 0,
        "entreprise": result.get("note_entreprise", 0) or 0,
        "evolution": result.get("note_evolution", 0) or 0,
    }
    total_w = sum(weights.get(k, 0) for k in axes)
    if total_w <= 0:
        return int(fit)
    g = sum(axes[k] * weights.get(k, 0) for k in axes) / total_w
    return int(round(g))


async def load_profil() -> str:
    if not CRITERES_FILE.exists():
        logger.warning(f"Profil file not found: {CRITERES_FILE}")
        return "Étudiant en école d'ingénieur cherchant une alternance en développement software."

    with open(CRITERES_FILE, "r", encoding="utf-8") as f:
        return f.read()


def parse_llm_response(response_text: Optional[str]) -> Optional[Dict[str, Any]]:
    if not response_text:
        return None
    try:
        # Extraire le JSON même s'il y a du texte autour (ex: reasoning tokens)
        # Chercher d'abord un code block JSON
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Sinon chercher directement { ... }
            json_match = re.search(r'(\{.*?\})', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                logger.error("No JSON found in response")
                return None
        
        data = json.loads(json_str)
        
        # Handle case where response is a list instead of dict
        if isinstance(data, list):
            if len(data) > 0:
                data = data[0]
            else:
                logger.warning("LLM response is empty list")
                return None
        
        # Handle case where data is still not a dict
        if not isinstance(data, dict):
            logger.warning(f"LLM response is not a dict: {type(data)}")
            return None
            
        # Extract fields with None-safe defaults
        score = int(data.get("score") or 0)
        resume_ia = (data.get("resume_ia") or "")[:600]
        raisons_score = (data.get("raisons_score") or "")[:200]
        tags = data.get("tags") or []
        if isinstance(tags, list):
            tags = tags[:5]
        else:
            tags = []
        orientation = (data.get("orientation") or "SWE/Web")[:50]

        # Categorie : on valide contre la liste configuree (sinon "Autre").
        categories = getattr(config, "JOB_CATEGORIES", [])
        raw_cat = (data.get("categorie") or data.get("category") or "").strip()
        if categories:
            match = next((c for c in categories if c.lower() == raw_cat.lower()), None)
            categorie = match or ("Autre" if "Autre" in categories else (categories[-1]))
        else:
            categorie = raw_cat or orientation

        salaire = (str(data.get("salaire") or data.get("salary") or "").strip() or "Non précisé")[:120]

        return {
            "score": score,
            "resume_ia": resume_ia,
            "raisons_score": raisons_score,
            "tags": tags,
            "orientation": orientation,
            "categorie": categorie,
            "salaire": salaire,
            "note_remuneration": _clamp_note(data.get("note_remuneration")),
            "note_entreprise": _clamp_note(data.get("note_entreprise")),
            "note_flexibilite": _clamp_note(data.get("note_flexibilite")),
            "note_evolution": _clamp_note(data.get("note_evolution")),
        }
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing LLM response: {e}")
        return None


def _match_exclusion(patterns: list, target: str) -> str | None:
    for term in patterns:
        try:
            if re.search(term, target, re.IGNORECASE):
                return term
        except re.error:
            # fallback: substring match if pattern is not valid regex
            if term.lower() in target.lower():
                return term
    return None


def check_exclusion_list(job: Dict[str, Any]) -> tuple[bool, str]:
    titre = job.get("titre", "")
    description = job.get("description", "")

    # Exclusions par titre seul : intitulés métiers hors-cible (commercial,
    # anti-fraude, sécurité physique, GRC financière...) qu'on ne peut pas
    # matcher sur la description sans faux positifs.
    term = _match_exclusion(getattr(config, 'TITLE_EXCLUSION_LIST', []), titre)
    if term:
        logger.debug(f"[EXCLU TITRE] '{term}' → {titre[:60]}")
        return True, f"titre: {term}"

    texte = f"{titre} {description}"
    term = _match_exclusion(getattr(config, 'EXCLUSION_LIST', []), texte)
    if term:
        logger.debug(f"[EXCLU MATCH] '{term}' → {titre[:60]}")
        return True, term

    return False, ""


router = LLMRouter()


def _rejected_result(job: Dict[str, Any], resume: str, raison: str, by: str) -> Dict[str, Any]:
    """Résultat d'élimination (score 0) sans appel LLM, avec traçabilité `by`."""
    return {
        "score": 0,
        "resume_ia": resume,
        "raisons_score": raison,
        "tags": [],
        "titre": job.get("titre", ""),
        "entreprise": job.get("entreprise", ""),
        "localisation": job.get("localisation", ""),
        "description": job.get("description", "")[:3000],
        "source": job.get("source", ""),
        "lien": job.get("lien", ""),
        "orientation": "SWE/Web",
        "categorie": "Autre",
        "type_contrat": job.get("type_contrat", utils.contract_label(job)),
        "score_global": 0,
        "scored_by": by,
    }


async def analyze_job(job: Dict[str, Any], profil: str, job_index: int = 0) -> Dict[str, Any]:
    excluded, reason = check_exclusion_list(job)
    if excluded:
        logger.info(f"[EXCLUDED] Matched: '{reason}'")
        return _rejected_result(
            job, f"Exclu: {reason}",
            f"Exclu automatiquement - terme interdit détecté: {reason}", "exclusion")

    # Pré-filtre déterministe (contrat, expérience, étranger) : évite un appel
    # LLM sur les offres structurellement hors-cible. Piloté par config.
    pf_reason = prefilter.check_prefilter(job)
    if pf_reason:
        logger.info(f"[PREFILTER] {pf_reason} → {job.get('titre','')[:50]}")
        return _rejected_result(
            job, f"Pré-filtré : {pf_reason}",
            f"Éliminé par le pré-filtre — {pf_reason}", "prefilter")

    prompt = SCORE_PROMPT.format(
        titre=job.get("titre", ""),
        entreprise=job.get("entreprise", ""),
        localisation=job.get("localisation", ""),
        description=job.get("description", "")[:3000],
        profil=profil[:3000],
    )

    router.reset_failed_providers()
    response_text = None
    attempts = 0
    # Budget d'essais = nombre de slots configurés (+2 de marge) : avec 5, les
    # clés gemini_3..7 n'étaient JAMAIS atteintes (3 Groq + gemini_1/2 = 5)
    # et les jobs tombaient en "Erreur LLM" alors que 5 clés restaient fraîches.
    max_attempts = len(router.quotas) + 2
    prompt_logged = False
    
    while not response_text and attempts < max_attempts:
        attempts += 1
        provider = router.get_next_provider(job_index)

        if not provider:
            logger.warning("All daily quotas exhausted, retrying tomorrow")
            return {
                "score": 0,
                "resume_ia": "Quota epuisé",
                "raisons_score": "Tous les quotas LLM epuisés",
                "tags": [],
                "titre": job.get("titre", ""),
                "entreprise": job.get("entreprise", ""),
                "localisation": job.get("localisation", ""),
                "description": job.get("description", "")[:3000],
                "source": job.get("source", ""),
                "lien": job.get("lien", ""),
                "orientation": "SWE/Web",
                "categorie": "Autre",
                "type_contrat": job.get("type_contrat", utils.contract_label(job)),
                "_failed": True,  # échec transitoire (quota) -> ne PAS persister, réessayer
            }

        # Logger le prompt avec le provider selectionne (une seule fois)
        if config.LLM_LOG_ENABLED and not prompt_logged:
            llm_logger.log_prompt(
                job=job,
                user_prompt=prompt,
                provider=provider,
                system_prompt=build_system_prompt(),
            )
            prompt_logged = True

        logger.info(f"Using provider: {provider} (attempt {attempts})")
        
        response_text = await router.call_provider(prompt, provider)

        if response_text:
            result = parse_llm_response(response_text)
            if result is None:
                logger.warning(f"Invalid JSON from {provider}, trying next provider")
                router.mark_provider_failed(provider)
                response_text = None
        else:
            router.mark_provider_failed(provider)
            delay = await router.get_delay(provider)
            logger.info(f"Provider {provider} failed, trying next provider")
            await asyncio.sleep(min(delay, 2))

    if not response_text:
        return {
            "score": 0,
            "resume_ia": "Erreur LLM",
            "raisons_score": "No response after all attempts",
            "tags": [],
            "titre": job.get("titre", ""),
            "entreprise": job.get("entreprise", ""),
            "localisation": job.get("localisation", ""),
            "description": job.get("description", "")[:3000],
            "source": job.get("source", ""),
            "lien": job.get("lien", ""),
            "orientation": "SWE/Web",
            "categorie": "Autre",
            "type_contrat": job.get("type_contrat", utils.contract_label(job)),
            "_failed": True,  # échec transitoire (aucune réponse) -> réessayer
        }

    result = parse_llm_response(response_text)
    if result is None:
        result = {
            "score": 0,
            "resume_ia": "Erreur d'analyse",
            "raisons_score": "Parse error",
            "tags": [],
            "_failed": True,  # échec transitoire (JSON invalide) -> réessayer
        }

    # Log la reponse du LLM
    if config.LLM_LOG_ENABLED and result:
        llm_logger.log_response(
            job_id=job.get("job_id", ""),
            response=result,
            provider=router.last_used_provider or "unknown",
        )

    result["titre"] = job.get("titre", "")
    result["entreprise"] = job.get("entreprise", "")
    result["localisation"] = job.get("localisation", "")
    result["description"] = job.get("description", "")[:3000]
    result["source"] = job.get("source", "")
    result["lien"] = job.get("lien", "")
    result["orientation"] = result.get("orientation", "SWE/Web")
    result["categorie"] = result.get("categorie", "Autre")
    result["salaire"] = result.get("salaire", "Non précisé")
    result["type_contrat"] = job.get("type_contrat", utils.contract_label(job))
    # Notes multi-critères (None-safe) + score global pondéré.
    result["note_remuneration"] = _clamp_note(result.get("note_remuneration"))
    result["note_entreprise"] = _clamp_note(result.get("note_entreprise"))
    result["note_flexibilite"] = _clamp_note(result.get("note_flexibilite"))
    result["note_evolution"] = _clamp_note(result.get("note_evolution"))
    result["score_global"] = compute_global_score(result)

    delay = await router.get_delay(router.last_used_provider)
    logger.info(f"Waiting {delay}s before next job")
    await asyncio.sleep(delay)

    return result


def should_persist_result(result: Dict[str, Any]) -> bool:
    """Décide si un résultat d'analyse doit être sauvegardé.

    - vrai résultat du LLM (y compris un rejet légitime, score 0) -> True (on
      mémorise pour ne plus jamais le re-scorer).
    - échec transitoire (_failed : quota épuisé, erreur API, JSON invalide)
      -> False (reste score=None, sera réessayé au prochain run).
    """
    return not result.get("_failed", False)


async def analyze_jobs_batch(
    jobs: List[Dict[str, Any]],
    profil: Optional[str] = None
) -> List[Dict[str, Any]]:
    if not profil:
        profil = await load_profil()

    logger.info(f"Analyzing {len(jobs)} jobs with LLM rotation...")

    results = []
    for i, job in enumerate(jobs):
        logger.info(f"Processing job {i+1}/{len(jobs)}: {job.get('titre', '')[:40]}")

        result = await analyze_job(job, profil, i)
        
        # 🚀 SAUVEGARDE IMMÉDIATE après chaque job.
        # On persiste TOUT résultat réel du LLM — y compris un rejet légitime
        # (score 0) — pour ne PAS le re-scorer au prochain run. On ne persiste
        # PAS les échecs transitoires (_failed : quota/erreur/JSON) : ils restent
        # score=None et seront réessayés plus tard.
        job_id = data_loader.generate_job_id(result)
        if job_id and should_persist_result(result):
            data_loader.update_job_score(
                job_id,
                result.get("score", 0),
                result.get("resume_ia", ""),
                result.get("raisons_score", ""),
                result.get("tags", []),
                result.get("orientation", "SWE/Web"),
                result.get("categorie", "Autre"),
                result.get("salaire", "Non précisé"),
                extra={
                    "score_global": result.get("score_global", 0),
                    "note_remuneration": result.get("note_remuneration", 0),
                    "note_entreprise": result.get("note_entreprise", 0),
                    "note_flexibilite": result.get("note_flexibilite", 0),
                    "note_evolution": result.get("note_evolution", 0),
                    # traçabilité : "llm" (scoré), "prefilter" ou "exclusion" (écarté sans LLM)
                    "scored_by": result.get("scored_by", "llm"),
                },
            )
            logger.info(f"  → Saved: fit {result.get('score')}/100 | global {result.get('score_global', 0)}/100 | {result.get('categorie', 'Autre')}")
        elif result.get("_failed"):
            logger.warning(f"  → Non sauvegardé ({result.get('resume_ia', 'échec')}) — sera réessayé au prochain run")

        results.append({
            "titre": result.get("titre", ""),
            "entreprise": result.get("entreprise", ""),
            "localisation": result.get("localisation", ""),
            "description": result.get("description", ""),
            "score": result["score"],
            "resume_ia": result["resume_ia"],
            "raisons_score": result["raisons_score"],
            "tags": result["tags"],
            "orientation": result.get("orientation", "SWE/Web"),
            "categorie": result.get("categorie", "Autre"),
            "salaire": result.get("salaire", "Non précisé"),
            "score_global": result.get("score_global", 0),
            "note_remuneration": result.get("note_remuneration", 0),
            "note_entreprise": result.get("note_entreprise", 0),
            "note_flexibilite": result.get("note_flexibilite", 0),
            "note_evolution": result.get("note_evolution", 0),
            "type_contrat": result.get("type_contrat", ""),
            "source": result.get("source", ""),
            "lien": result.get("lien", ""),
        })

    # Finaliser le log LLM
    if config.LLM_LOG_ENABLED:
        llm_logger.finalize_log()

    return results


def filter_jobs(
    analyzed_jobs: List[Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    prioritaires = []
    a_etudier = []
    ignores = []

    for job in analyzed_jobs:
        score = job.get("score", 0)
        if score >= config.SCORE_PRIORITAIRE:
            prioritaires.append(job)
        elif score >= config.SCORE_SEUIL:
            a_etudier.append(job)
        else:
            ignores.append(job)

    logger.info(f"Filtering: {len(prioritaires)} prioritaires, {len(a_etudier)} à étudier, {len(ignores)} ignorés")

    return {
        "prioritaires": prioritaires,
        "a_etudier": a_etudier,
        "ignores": ignores,
    }


async def match_jobs(jobs: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    logger.info(f"Starting matching for {len(jobs)} jobs...")

    analyzed = await analyze_jobs_batch(jobs)
    filtered = filter_jobs(analyzed)

    logger.info(f"Matching complete: {len(filtered['prioritaires'])} prioritaires, {len(filtered['a_etudier'])} à étudi")
    return filtered