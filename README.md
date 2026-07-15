# Auto Emploi

Robot de recherche d'emploi (CDI / CDD) qui **collecte** les offres, les **score avec des LLM**
selon votre profil, génère des **CV ciblés** et se pilote depuis un **tableau de bord web** —
de la recherche à la candidature, au même endroit.

---

## Pourquoi ce projet

Le marché de l'emploi est saturé et, à la sortie d'école, décrocher un premier CDI relève du
parcours du combattant : il faut répéter les mêmes gestes des centaines de fois — taper des
mots-clés, ouvrir des dizaines d'annonces, juger si elles collent, réadapter son CV pour chacune,
postuler, puis suivre. C'est long, répétitif et décourageant.

Auto Emploi est né de ce constat : puisque le geste est répétitif, autant en faire **une solution
unique, réutilisable par tout le monde**. La machine ramène et trie le volume ; l'humain garde la
décision finale. Le projet est volontairement **piloté par la configuration** : on l'oriente vers
n'importe quel métier, contrat ou pays sans toucher au code.

---

## Ce que fait Auto Emploi

- **Collecte multi-sources** : LinkedIn et Indeed (via Apify), sur plusieurs zones (France, Canada, International remote).
- **Pré-filtre déterministe** : écarte le hors-cible (contrat, expérience trop élevée, géo incompatible) **sans coût LLM**.
- **Scoring par LLM** : chaque offre reçoit une note de fit (0-100), une catégorie, un résumé et quatre notes annexes (rémunération, entreprise, flexibilité, évolution), agrégées en un **score global** pondéré.
- **Génération de CV ciblés** : un CV PDF d'une page, adapté à l'annonce, à partir d'une source de vérité unique — sans rien inventer.
- **Tableau de bord web** : configuration, exécution en direct, suivi des candidatures, thème clair/sombre.
- **Export** CSV (Excel) et synchronisation Notion (optionnelle).

---

## Le pipeline

```
Sources (LinkedIn / Indeed)
        │  scraper.py — collecte + normalisation
        ▼
Pré-filtre (prefilter.py)  ──►  écarte le hors-cible, sans LLM
        ▼
Scoring (matcher.py)  ──►  note de fit + 4 axes → score global sur 100
        │                  rotation automatique des fournisseurs LLM
        ▼
Base locale (data/jobs_global.json)  ──►  dédup par identité
        ▼
Dashboard  ·  Export CSV  ·  Notion  ·  Génération de CV (cvgen/)
```

Deux « cerveaux » indépendants : **`matcher.py`** (le scoring) et le module **`cvgen/`** (le CV,
assemblage déterministe à partir de `profile_master.yaml`).

---

## Gratuit par conception

Tout le projet tourne sur des **offres gratuites**. Le problème des tiers gratuits, c'est la
**limite journalière** : impossible de scorer des milliers d'offres avec une seule clé. La parade :
le scoreur **répartit la charge sur plusieurs fournisseurs et plusieurs clés**, et **bascule
automatiquement** dès qu'un slot est épuisé ou en erreur. Un slot sans clé dans le `.env` est
simplement ignoré.

| Fournisseur | Slots / clés | Modèle | Limite / jour |
|---|---|---|---|
| Groq | 4 slots (2 comptes possibles) | `qwen3-32b`, `llama-3.3-70b` (×2), `gpt-oss-120b` | **1 000 / slot** |
| NVIDIA NIM | 1 | `llama-3.3-70b-instruct` | **100 000** |
| Gemini | jusqu'à 7 clés | `gemini-2.5-flash-lite` | **20 / clé** (≈ 140 cumulées) |
| OpenRouter | 2 slots | `gpt-oss-120b`, `nemotron-3-super-120b` | **40 / slot** |

Ordre de bascule : **Groq → NVIDIA → Gemini → OpenRouter**. Côté scraping, **Apify** offre un crédit
mensuel gratuit (≈ 5 $, soit quelques milliers d'offres). Les quotas sont éditables dans le
dashboard (page **Quotas LLM**) ou dans `config.py` (`LLM_QUOTAS`).

---

## Installation

Prérequis : **Python 3.12**, **Poetry**, **Node.js**.

```bash
git clone <url-du-repo> auto-emploi
cd auto-emploi

# 1. Dépendances Python
poetry install

# 2. Frontend du dashboard (une fois, puis après chaque modif React)
cd dashboard/frontend && npm install && npm run build && cd ../..

# 3. Fichiers de configuration (copier les exemples anonymisés)
cp .env.example .env                              # clés API
cp cvgen/profile_master.example.yaml cvgen/profile_master.yaml   # votre CV
cp data/criteres.example.md data/criteres.md      # profil pour le scoring
```

Puis lancer le dashboard :

```bash
poetry run uvicorn dashboard.app:app --port 9090   # http://127.0.0.1:9090
```

---

## Configuration pas à pas (avec exemples anonymisés)

Tout se règle depuis le dashboard, mais voici ce que chaque étape attend.

### 1. Clés API — `.env`

Copiez `.env.example` et remplissez ce que vous avez (un slot vide est ignoré) :

```dotenv
APIFY_TOKEN_LINKEDIN=apify_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_API_KEY_1=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GEMINI_API_KEY_1=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# ... GEMINI_API_KEY_2 à _7, GROQ_API_KEY_2, OPENROUTER_API_KEY, etc.
```

### 2. Mon CV — `cvgen/profile_master.yaml`

La source de vérité de vos CV. On y remplit une **bibliothèque** d'expériences taguées ; le
générateur sélectionne les plus pertinentes par offre. Chaque bloc existe **en FR et EN**, avec des
**tags** (mots-thèmes en minuscules : `grc`, `python`, `ai-security`…) qui pilotent la sélection.

```yaml
experiences:
  - id: acme-bank
    include: always            # always | scored | never
    start: "2024-01"
    org:  {fr: "ACME Bank — France", en: "ACME Bank — France"}
    role: {fr: "Analyste sécurité (équipe RSSI)", en: "Security Analyst (CISO team)"}
    tags: [grc, security-ops, banking]
    bullets:
      - id: acme-iso
        tags: [grc, banking]
        fr: "Appliqué ISO 27001 et PCI DSS : politiques, contrôle d'accès, revues périodiques."
        en: "Applied ISO 27001 and PCI DSS: policies, access control, periodic reviews."
```

### 3. Profil candidat — `data/criteres.md`

Un texte libre décrivant qui vous êtes et ce que vous cherchez. Il est **injecté dans le prompt de
scoring** : plus il est précis, plus le tri est juste. (À ne pas confondre avec `profile_master.yaml`,
qui sert au CV, pas au scoring.)

```markdown
## OBJECTIF (par priorité)
1. Cybersécurité GRC : gouvernance, risque, conformité, audit.
2. Sécurité technique : cloud, AppSec, IAM.
3. Développement Python & automatisation.
```

### 4. Mots-clés — page « Mots-clés »

Les termes envoyés aux sites (un par ligne). Exemple cybersécurité :

```
cybersécurité
consultant GRC
analyste SOC
IAM
ingénieur cybersécurité
```

Les champs d'exclusion utilisent des expressions régulières (voir la documentation intégrée).

### 5. Types de contrat — page « Types de contrat »

Cases à cocher : `CDI`, `CDD`, `STAGE`, `ALTERNANCE`. Exemple : cocher **CDI** et **CDD** uniquement.

### 6. Zones de scrape — page « Zones de scrape »

- **France** — tous modes (présentiel, hybride, télétravail).
- **Canada** — télétravail uniquement, réalisable depuis la France.
- **International (full remote)** — monde entier, télétravail uniquement.

### 7. Pré-filtre — page « Pré-filtre »

Écarte avant le LLM. Exemple : **expérience maximale = 3 ans**, et termes regex qui éliminent les
contrats hors CDI/CDD :

```
\bfreelance\b
\bportage\b
mission
```

### 8. Prompts & Quotas — pages dédiées

**Prompts** : la grille de notation du LLM (à ajuster pour durcir/assouplir le tri). **Quotas LLM** :
les limites journalières et la cadence de chaque fournisseur.

---

## Utilisation

### Dashboard (recommandé)

`http://127.0.0.1:9090` — pages **Vue d'ensemble**, **Offres**, **Candidatures**, **Offres fermées**,
**Exécution** (lancer les phases avec logs en direct), **Assistant** (à venir), et toute la
**Configuration** (Mots-clés, Types de contrat, Zones, Pré-filtre, Prompts, Profil candidat, Mon CV,
Quotas). Une page **Documentation** intégrée explique chaque écran ; un sélecteur de thème
clair/sombre est en haut à droite.

### CLI

```bash
poetry run python main.py --phase all                    # cycle complet
poetry run python main.py --phase scrape                 # collecte
poetry run python main.py --phase process --limit 30     # scoring par lots de 30
poetry run python main.py --phase generate               # CV ciblés
poetry run python export_csv.py --min 60                 # export CSV des retenues
```

Le scoring **avance** : une offre déjà jugée (retenue ou rejetée) ne repasse jamais ; seuls les
échecs transitoires (quota/réseau) sont réessayés. La dédup se fait sur `titre|entreprise|localisation`.

---

## Génération de CV

Le CV n'est pas rédigé par une IA à chaque fois : il est **assemblé de façon déterministe** à partir
de `cvgen/profile_master.yaml`. Le système lit l'offre, en déduit les thèmes importants (via les
**tags**), sélectionne les bullets pertinents, applique les **règles pays** (format FR / Québec /
international) et rend un **PDF d'une page** via un navigateur headless. Avantage : **zéro
hallucination** — chaque ligne du CV existe déjà dans votre profil.

---

## Stack technique

Python (Poetry) · FastAPI + SSE · React + TypeScript (Vite) · Apify · litellm (Groq / Gemini /
NVIDIA / OpenRouter) · Notion API · rendu PDF via navigateur headless.

---

## Structure du projet

```
auto-emploi/
├── config.py            # Configuration centrale
├── main.py              # Orchestrateur CLI (phases)
├── scraper.py           # Scraping multi-sources + normalisation
├── prefilter.py         # Pré-filtre déterministe (avant LLM)
├── matcher.py           # Scoring LLM + rotation des fournisseurs
├── data_loader.py       # Base JSON locale, statuts, dédup
├── generator.py         # Lettre de motivation (délègue le CV à cvgen/)
├── notion_db.py         # Synchronisation Notion (optionnelle)
├── utils.py             # Logging, env, helpers
├── export_csv.py        # Export CSV (Excel)
│
├── cvgen/               # Génération de CV ciblés (déterministe)
│   ├── profile_master.example.yaml   # exemple anonymisé (à copier)
│   ├── generate_cv.py · offer_mapping.py · pdf_engine.py · ...
│
├── dashboard/
│   ├── app.py           # API FastAPI + SSE
│   └── frontend/        # SPA React + TypeScript (Vite)
│
├── data/
│   └── criteres.example.md           # exemple anonymisé (à copier)
│
├── .env.example         # modèle de clés API
└── pyproject.toml
```

Les fichiers de données personnelles (`profile_master.yaml`, `criteres.md`, `data/*.json`, `.env`)
sont **exclus du dépôt** ; seuls leurs équivalents `*.example.*` sont versionnés.

---

## Contributeurs

- **Emery Guendehou** — auteur et mainteneur
<!-- CONTRIBUTEUR -->

---

## Licence

Distribué sous licence **MIT** — voir [`LICENSE`](LICENSE).
