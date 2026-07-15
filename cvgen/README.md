# Module CV ciblé — pour la phase `generate` d'Auto Emploi

## Philosophie (les 3 couches)

1. **CONTENU** (`profile_master.yaml`) — la seule source de vérité. Tous les
   bullets sont pré-rédigés en FR et EN, chiffrés, et taggés. On ne rédige
   JAMAIS au moment de postuler : on sélectionne. C'est ce qui garantit
   qu'aucun CV généré ne contient d'invention.
2. **SÉLECTION** (`generate_cv.py`) — les mots-clés de l'offre sont convertis
   en poids de tags (`KEYWORD_TO_TAGS`), puis chaque bullet/projet/groupe de
   compétences est scoré. On garde les meilleurs, on réordonne.
3. **RENDU** (`country_rules.yaml` + `template_cv.html`) — un seul gabarit
   visuel (style une colonne compatible ATS), des conventions par pays
   (langue, adresse/téléphone, hobbies ou non, vocabulaire de contrat).

## Usage

    pip install jinja2 pyyaml weasyprint
    python generate_cv.py --offer offer.json --out out/
    python generate_cv.py --offer offer.json --country ca-en --out out/

Sans WeasyPrint, le script produit quand même le HTML (imprimable en PDF via
le navigateur). Deux offres d'exemple sont fournies (`offer_scaleai.json`,
`offer_grc_fr.json`).

## Intégration dans ton pipeline

Dans ta phase `generate`, pour chaque offre retenue de `jobs_global.json` :

    from generate_cv import build_cv
    build_cv(offer_dict, country, master, rules, Path("out/cvs"))

Mapping recommandé de tes champs → `offer_dict` :
title, company, description (texte brut), category (celle de ton scoring),
keywords (si ton scorer en extrait), country (déduis-le de la zone de scrape :
France→fr, Canada→ca-qc si l'offre est en français sinon ca-en, International→intl).

## Le hook LLM (accroche)

`llm_hook()` est le SEUL endroit où un LLM peut écrire du texte. Branche-y
Groq/Gemini avec ce contrat strict dans le prompt :
- interdiction d'inventer une expérience, un outil, un chiffre ;
- 35 mots max, uniquement le lien profil ↔ offre ;
- même langue que le CV.
Tout le reste du CV vient de la base : zéro hallucination possible.

## Auto-ajustement à 1 page

Le générateur rend le PDF, compte les pages et dégrade gracieusement dans
cet ordre : centres d'intérêt → groupe de compétences le moins pertinent →
3e projet → bullets les moins scorés. Ordre modifiable dans `shrink_steps`.

## Entretien du système (le vrai secret du "CV parfait")

- Nouvelle mission freelance ? Ajoute 1-2 bullets taggés dans le YAML,
  en FR et EN, avec un chiffre. 5 minutes, et toutes tes futures
  candidatures en profitent.
- Une offre matche mal ? Le problème est presque toujours dans
  `KEYWORD_TO_TAGS` : ajoute le vocabulaire de l'offre (ex. "purple team",
  "MLOps", "SOC 2") vers les bons tags. Le "cerveau" du matching, c'est ce
  dictionnaire — enrichis-le à chaque candidature.
- Vérifie TOUJOURS le PDF avant envoi. L'automatisation prépare à 95 %,
  ton œil fait les 5 % restants (et détecte les cas limites).

## À compléter

- `profile_master.yaml` → `identity.addresses.ca` : ton adresse exacte à
  Chicoutimi (placeholder actuellement).
- Éventuellement une adresse e-mail plus durable que @et.esiea.fr / plus
  pro que entertainmentemery si tu en crées une.
