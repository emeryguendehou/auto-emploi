import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import PageHeader from '../components/PageHeader';

type Field = { name: string; desc: ReactNode };

function Fields({ head, rows }: { head: [string, string]; rows: Field[] }) {
  return (
    <div className="table-wrap" style={{ margin: '14px 0' }}>
      <table className="table">
        <thead><tr><th>{head[0]}</th><th>{head[1]}</th></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td className="fname">{r.name}</td>
              <td className="td-dim">{r.desc}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PageDoc({ id, eyebrow, title, to, children }:
  { id: string; eyebrow: string; title: string; to: string; children: ReactNode }) {
  return (
    <section id={id} className="doc-section card">
      <div className="doc-pagehead">
        <div>
          <p className="doc-eyebrow">{eyebrow}</p>
          <h3 className="doc-h">{title}</h3>
        </div>
        <Link className="doc-visit" to={to}>Ouvrir la page →</Link>
      </div>
      {children}
    </section>
  );
}

export default function Documentation() {
  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Documentation"
        description="Comment fonctionne Auto Emploi — le pipeline, le scoring, la génération de CV, et chaque page du tableau de bord."
      />

      <div className="doc-toc">
        <a href="#doc-archi">Architecture</a>
        <a href="#doc-scoring">Scoring</a>
        <a href="#doc-cv">Génération CV</a>
        <a href="#doc-moncv">Mon CV</a>
        <a href="#doc-overview">Vue d'ensemble</a>
        <a href="#doc-offers">Offres</a>
        <a href="#doc-applications">Candidatures</a>
        <a href="#doc-closed">Fermées</a>
        <a href="#doc-run">Exécution</a>
        <a href="#doc-chat">Assistant</a>
        <a href="#doc-keywords">Mots-clés</a>
        <a href="#doc-jobtypes">Contrats</a>
        <a href="#doc-zones">Zones</a>
        <a href="#doc-prefilter">Pré-filtre</a>
        <a href="#doc-prompts">Prompts</a>
        <a href="#doc-criteria">Profil</a>
        <a href="#doc-quotas">Quotas</a>
        <a href="#doc-workflow">Flux type</a>
      </div>

      {/* COMPRENDRE */}
      <section className="doc-section card">
        <p className="doc-eyebrow">Comprendre · 01</p>
        <h3 className="doc-h">À quoi ça sert</h3>
        <p className="doc-p">
          Chercher un poste, c'est répéter les mêmes gestes des centaines de fois. <strong>Auto Emploi</strong> industrialise
          cette boucle sans vous retirer la décision : la machine ramène et trie le volume, vous gardez le jugement final.
        </p>
        <div className="doc-grid">
          <div className="card doc-mini"><h4>🔎 Elle ramène</h4><p>Scraping multi-sources (LinkedIn, Indeed, WTTJ) sur les zones et contrats choisis.</p></div>
          <div className="card doc-mini"><h4>⚖️ Elle trie</h4><p>Un pré-filtre déterministe écarte le hors-cible, puis un LLM note chaque offre sur 100.</p></div>
          <div className="card doc-mini"><h4>📄 Elle rédige</h4><p>Un CV PDF d'une page, ciblé sur l'annonce, à partir d'une source de vérité unique.</p></div>
          <div className="card doc-mini"><h4>🎛️ Vous pilotez</h4><p>Tout se règle et se suit ici : filtres, quotas, statuts de candidature, exécution en direct.</p></div>
        </div>
      </section>

      <section id="doc-archi" className="doc-section card">
        <p className="doc-eyebrow">Comprendre · 02</p>
        <h3 className="doc-h">Architecture &amp; pipeline</h3>
        <p className="doc-p">Chaque offre traverse le même parcours, de la source brute à une fiche scorée et actionnable.</p>
        <div className="doc-flow">
          <div className="doc-step"><div className="n">01</div><div className="t">Scrape</div><div className="d">Collecte via les acteurs Apify (LinkedIn / Indeed / WTTJ).</div></div>
          <div className="doc-arrow">→</div>
          <div className="doc-step"><div className="n">02</div><div className="t">Filtre</div><div className="d">Exclusions par titre + pré-filtre : écarte sans coût LLM.</div></div>
          <div className="doc-arrow">→</div>
          <div className="doc-step"><div className="n">03</div><div className="t">Score</div><div className="d">Le LLM note fit + 4 axes → score global sur 100.</div></div>
          <div className="doc-arrow">→</div>
          <div className="doc-step"><div className="n">04</div><div className="t">Pilote</div><div className="d">Dashboard, Notion, génération de CV, suivi.</div></div>
        </div>
        <p className="doc-p" style={{ marginTop: 12 }}>
          Deux « cerveaux » indépendants : <code className="dc">matcher.py</code> (scoring) et <code className="dc">cvgen/</code> (CV).
          La base unique <code className="dc">jobs_global.json</code> est le point de vérité. Pour tenir sur des quotas gratuits, le
          scoring bascule automatiquement de fournisseur : <code className="dc">Groq → NVIDIA → Gemini → OpenRouter</code>.
        </p>
      </section>

      <section id="doc-scoring" className="doc-section card">
        <p className="doc-eyebrow">Comprendre · 03</p>
        <h3 className="doc-h">Le moteur de scoring</h3>
        <p className="doc-p">
          Chaque offre reçoit une <strong>note de fit</strong> (0–100) et un <strong>score global</strong> pondéré. Le
          {' '}<Link to="/criteria">Profil candidat</Link> et les <Link to="/prompts">Prompts</Link> sont injectés dans chaque
          évaluation — c'est là qu'on règle la sévérité.
        </p>
        <ul className="doc-ul">
          <li className="doc-li"><strong>Critères éliminatoires</strong> — contrat hors cible, expérience trop élevée ou géo incompatible → fit = 0.</li>
          <li className="doc-li"><strong>Base 50</strong>, puis bonus / malus selon l'adéquation aux compétences réelles.</li>
          <li className="doc-li"><strong>Catégorie</strong> — Cyber GRC, Cyber Technique, AI Security, AI Governance, AI Engineer, Python-Automation, Autre.</li>
          <li className="doc-li"><strong>4 axes annexes</strong> — rémunération, entreprise, flexibilité, évolution.</li>
        </ul>
        <div className="doc-formula">score_global = fit·0.35 + rémunération·0.30 + flexibilité·0.15 + entreprise·0.10 + évolution·0.10<br />→ forcé à 0 si fit = 0</div>
        <div className="doc-legend">
          <span className="doc-pill hi">≥ 75 — fort</span>
          <span className="doc-pill mid">50–74 — à étudier</span>
          <span className="doc-pill lo">&lt; 50 — écarté</span>
        </div>
        <div className="doc-note"><strong>Correction manuelle.</strong> Sur la page <Link to="/offers">Offres</Link>, la colonne <em>Fit</em> est cliquable : corrigez la note à la main, le score global se recalcule.</div>
      </section>

      <section id="doc-cv" className="doc-section card">
        <p className="doc-eyebrow">Comprendre · 04</p>
        <h3 className="doc-h">La génération de CV</h3>
        <p className="doc-p">
          Le CV est <strong>assemblé de façon déterministe</strong> à partir d'une source de vérité unique
          (<code className="dc">profile_master.yaml</code>). On ne rédige jamais à la volée : on <strong>sélectionne</strong> les éléments
          les plus pertinents pour l'annonce.
        </p>
        <div className="doc-flow">
          <div className="doc-step"><div className="n">A</div><div className="t">profile_master</div><div className="d">Vos expériences taguées, FR/EN, chiffres réels.</div></div>
          <div className="doc-arrow">→</div>
          <div className="doc-step"><div className="n">B</div><div className="t">Sélection</div><div className="d">Les mots-clés de l'offre choisissent bullets, intitulé, gras.</div></div>
          <div className="doc-arrow">→</div>
          <div className="doc-step"><div className="n">C</div><div className="t">Règles pays</div><div className="d">FR / Québec / international : adresse, mentions, langue.</div></div>
          <div className="doc-arrow">→</div>
          <div className="doc-step"><div className="n">D</div><div className="t">PDF 1 page</div><div className="d">Rendu Edge headless, ajusté pour tenir sur une page.</div></div>
        </div>
        <div className="doc-note"><strong>Zéro hallucination</strong> : le CV ne peut contenir que ce qui existe dans le profil maître — chaque ligne est défendable en entretien. Bouton <em>Générer</em> sur la page <Link to="/offers">Offres</Link>.</div>
        <p className="doc-p" style={{ marginTop: 12 }}>
          Le contenu vit dans le fichier <code className="dc">cvgen/profile_master.yaml</code>, mais vous l'éditez
          entièrement depuis la page <Link to="/profile-master">Mon CV</Link> (voir le guide juste en dessous). À ne pas
          confondre avec le <Link to="/criteria">Profil candidat</Link>, qui sert au <em>scoring</em> des offres, pas à la
          rédaction du CV.
        </p>
      </section>

      {/* La page Mon CV — guide de remplissage */}
      <section id="doc-moncv" className="doc-section card">
        <div className="doc-pagehead">
          <div>
            <p className="doc-eyebrow">Comprendre · La page Mon CV</p>
            <h3 className="doc-h">« Mon CV » — comment remplir son profil</h3>
          </div>
          <Link className="doc-visit" to="/profile-master">Ouvrir la page →</Link>
        </div>
        <p className="doc-p">
          <strong>Tout ce qui apparaît sur vos CV générés vient de cette page.</strong> Vous ne rédigez pas un CV figé :
          vous remplissez une <em>bibliothèque</em> d'expériences, de compétences et de projets, et le générateur en
          {' '}<strong>sélectionne</strong> les morceaux les plus pertinents pour chaque offre.
        </p>

        <h4 className="doc-h4">Trois règles d'or</h4>
        <ul className="doc-ul">
          <li className="doc-li"><strong>Tout en double, FR et EN.</strong> Selon le pays de l'offre, le CV sort en français ou en anglais — les deux versions doivent exister.</li>
          <li className="doc-li"><strong>Des faits vrais et chiffrés.</strong> Chaque ligne doit être défendable en entretien («&nbsp;11 sites livrés&nbsp;», «&nbsp;~30 utilisateurs&nbsp;»).</li>
          <li className="doc-li"><strong>Les tags décident de tout.</strong> C'est par eux que le système sait quoi mettre en avant.</li>
        </ul>

        <h4 className="doc-h4">Les tags — le cœur du système (à lire absolument)</h4>
        <p className="doc-p">
          Un <strong>tag</strong> est un mot-thème court qui étiquette un élément (une expérience, un bullet, une compétence…).
          À la génération, le système lit l'offre, en déduit les <em>thèmes importants</em>, puis remonte les éléments dont les
          tags correspondent. En clair, un tag dit «&nbsp;ce bullet parle de GRC / de Python&nbsp;».
        </p>
        <Fields head={['Règle', 'Détail']} rows={[
          { name: 'Format', desc: <>minuscules, sans espace, tiret pour lier — <code className="dc">grc</code>, <code className="dc">ai-security</code>, <code className="dc">active-directory</code></> },
          { name: 'Quantité', desc: '2 à 5 tags par élément — uniquement les thèmes qui le décrivent vraiment.' },
          { name: 'Cohérence', desc: <>réutilisez toujours le même mot — pas <code className="dc">cyber</code> ici et <code className="dc">cybersecurite</code> là.</> },
          { name: 'Saisie', desc: 'dans le champ, séparez-les par des virgules ; le système gère le reste.' },
        ]} />
        <p className="doc-p">Un vocabulaire de départ (réutilisez-le tel quel)&nbsp;:</p>
        <pre className="doc-pre">{`grc · conformite · ai-governance         gouvernance & conformité
ai-security · llm · research              sécurité de l'IA / recherche
ai-agents · automation · api · python     dev & automatisation IA
security-ops · infra · active-directory   sécurité opérationnelle
banking · consulting · client             secteurs / posture
web · e-commerce · mobile                 développement`}</pre>

        <h4 className="doc-h4">Les champs qui reviennent partout</h4>
        <Fields head={['Champ', 'À quoi ça sert']} rows={[
          { name: 'ID', desc: 'Identifiant technique court et unique (ex. acme-sec). Jamais affiché sur le CV — sert au système. Gardez-le stable.' },
          { name: 'FR / EN', desc: 'Le texte réel, dans les deux langues. C\'est ce qui s\'imprime sur le CV.' },
          { name: 'Tags', desc: 'Les thèmes de l\'élément (voir ci-dessus).' },
          { name: 'Inclusion (expériences)', desc: <><strong>Toujours</strong> = sur tous les CV · <strong>Selon le score</strong> = seulement si les tags collent à l'offre · <strong>Jamais</strong> = en réserve (activé à la main).</> },
          { name: 'Début (AAAA-MM)', desc: 'Sert au tri antichronologique (le plus récent en haut). Ex. 2024-01.' },
        ]} />

        <h4 className="doc-h4">Exemple complet — une expérience (anonymisé)</h4>
        <pre className="doc-pre">{`ID            acme-sec
Inclusion     Toujours
Début         2024-01
Organisation  FR: ACME Bank — France            EN: ACME Bank — France
Poste         FR: Analyste sécurité (équipe RSSI)   EN: Security Analyst (CISO team)
Lieu          FR: Paris, France                 EN: Paris, France
Dates         FR: Janv. 2024 – Août 2024        EN: Jan 2024 – Aug 2024
Tags          grc, security-ops, banking

  ▸ Bullet 1
    ID     acme-iso
    Tags   grc, banking
    FR: Appliqué les normes ISO 27001 et PCI DSS : politiques, contrôle d'accès, revues périodiques.
    EN: Applied ISO 27001 and PCI DSS standards: policies, access control, periodic reviews.

  ▸ Bullet 2
    ID     acme-ad
    Tags   security-ops, banking
    FR: Administré l'Active Directory et déployé la double authentification (~30 utilisateurs).
    EN: Administered Active Directory and rolled out two-factor authentication (~30 users).`}</pre>
        <div className="doc-note">
          <strong>À vous&nbsp;:</strong> remplacez ce contenu par le vôtre en gardant la logique — un ID court, 2 à 4 tags, FR + EN,
          des chiffres réels. Un même bullet bien taggé peut resservir sur des dizaines d'offres différentes.
        </div>

        <h4 className="doc-h4">Le reste des sections en un coup d'œil</h4>
        <Fields head={['Section', 'Ce qu\'on y met']} rows={[
          { name: 'Identité', desc: 'Coordonnées. Deux téléphones / adresses (FR et CA) selon le pays visé.' },
          { name: 'Profil (résumé)', desc: 'Le paragraphe d\'accroche par défaut + la phrase de disponibilité (toujours affichée).' },
          { name: 'Variantes de profil', desc: 'Des accroches alternatives taggées : le système choisit celle qui colle le mieux à l\'offre.' },
          { name: 'Administratif', desc: 'Faits stables (droit au travail, salaire, mobilité) pour pré-remplir les formulaires de candidature.' },
          { name: 'Projets', desc: 'Comme les expériences, mais taggés et sélectionnés 2 à 3 par CV.' },
          { name: 'Formation', desc: 'Diplômes ; cochez « optionnel » pour ceux à retirer si la place manque.' },
          { name: 'Compétences', desc: 'Groupes (ex. « Gouvernance & conformité ») réordonnés selon l\'offre.' },
          { name: 'Soft skills', desc: 'Taggés ; 5 à 6 retenus par offre.' },
        ]} />

        <div className="doc-note warn">
          <strong>Sauvegarde.</strong> Le bouton réécrit <code className="dc">profile_master.yaml</code> (une copie
          {' '}<code className="dc">.bak</code> est faite avant). Vos données sont conservées à l'identique&nbsp;; seuls les
          commentaires techniques du fichier sont retirés.
        </div>
      </section>

      <div className="doc-divider" />

      {/* PILOTAGE */}
      <PageDoc id="doc-overview" eyebrow="Pilotage" title="Vue d'ensemble" to="/">
        <p className="doc-p">L'écran d'accueil : l'état du pipeline et la consommation des quotas LLM du jour. Lecture seule, rafraîchi toutes les 30 secondes.</p>
        <Fields head={['Élément', 'Ce qu\'il indique']} rows={[
          { name: 'Tuiles de stats', desc: 'Total offres · À traiter · Exclues · Prioritaires · À étudier · Ignorées · Candidatures · Fermées · Dans Notion.' },
          { name: 'Table Quotas', desc: 'Par fournisseur : modèle, appels utilisés / limite, restant, succès / échecs, jauge de consommation.' },
          { name: 'Jauge couleur', desc: <>vert &lt; 70 % · ambre &lt; 90 % · rouge ≥ 90 %.</> },
        ]} />
      </PageDoc>

      <PageDoc id="doc-offers" eyebrow="Pilotage" title="Offres" to="/offers">
        <p className="doc-p">La page centrale — toutes les offres collectées, scorées et classées. Onglets de filtre (avec compteurs) : Retenues, Toutes, À traiter, Prioritaires, À étudier, Ignorées, Éliminées. Trié par score global (300 lignes max).</p>
        <Fields head={['Colonne / action', 'Rôle & utilisation']} rows={[
          { name: 'Global', desc: 'Le score global sur 100 (pastille colorée).' },
          { name: 'Fit', desc: <><strong>Cliquez</strong> pour corriger la note (0–100). Entrée valide, Échap annule — le global se recalcule.</> },
          { name: 'Statut', desc: <><span className="badge badge-green">Prioritaire</span> <span className="badge badge-amber">À étudier</span> <span className="badge badge-red">Ignorée</span> <span className="badge badge-gray">Éliminée</span> <span className="badge badge-blue">À traiter</span></> },
          { name: 'Lien', desc: 'Ouvre l\'annonce d\'origine.' },
          { name: 'CV', desc: 'Bouton Générer → produit le PDF ciblé (puis lien PDF). Visible si fit > 0.' },
          { name: 'Suivi ✓', desc: <>« Postulé » — bascule vers <Link to="/applications">Candidatures</Link>.</> },
          { name: 'Suivi ⊘', desc: <>« Fermer » — bascule vers <Link to="/closed">Offres fermées</Link>.</> },
        ]} />
        <div className="doc-note">Une offre postulée ou fermée quitte cette liste ; on peut toujours l'annuler / la rouvrir depuis sa page dédiée.</div>
      </PageDoc>

      <PageDoc id="doc-applications" eyebrow="Pilotage" title="Candidatures" to="/applications">
        <p className="doc-p">Le journal daté de vos candidatures (les plus récentes en tête). Sert de preuve et de suivi. Marquer « postulé » déclenche aussi une synchro Notion en arrière-plan (best-effort).</p>
        <Fields head={['Élément', 'Rôle']} rows={[
          { name: 'Postulé le', desc: 'Date d\'enregistrement (tri décroissant).' },
          { name: 'CV', desc: 'Lien vers le PDF ciblé s\'il a été généré.' },
          { name: 'Annuler', desc: 'Renvoie l\'offre dans la liste Offres.' },
        ]} />
      </PageDoc>

      <PageDoc id="doc-closed" eyebrow="Pilotage" title="Offres fermées" to="/closed">
        <p className="doc-p">Les offres écartées manuellement — poste pourvu, candidatures closes, ou candidature impossible (compte requis, détection de robot). Elles sortent de la file active sans être perdues.</p>
        <Fields head={['Élément', 'Rôle']} rows={[
          { name: 'Fermée le', desc: 'Date de fermeture.' },
          { name: 'Rouvrir', desc: 'Renvoie l\'offre dans la liste Offres.' },
        ]} />
        <p className="field-hint">Une offre à laquelle vous avez postulé reste dans Candidatures même fermée — la candidature prime.</p>
      </PageDoc>

      <PageDoc id="doc-run" eyebrow="Pilotage" title="Exécution" to="/run">
        <p className="doc-p">Le poste de commande : lancez une phase du pipeline et suivez sa sortie en direct (flux temps réel + barre de progression). Chaque phase tourne dans un sous-processus dédié.</p>
        <Fields head={['Phase', 'Ce qu\'elle fait']} rows={[
          { name: 'Scrape', desc: 'Collecte de nouvelles offres sur les sources et zones activées.' },
          { name: 'Filter', desc: 'Applique exclusions par titre + pré-filtre (marque les éliminées).' },
          { name: 'Process', desc: 'Scoring LLM des offres non traitées, puis ajout des retenues à Notion.' },
          { name: 'Notion', desc: 'Pousse / met à jour les fiches vers la base Notion.' },
          { name: 'Keep', desc: 'Étape de rétention / nettoyage de la base.' },
          { name: 'Pipeline complet', desc: 'Enchaîne toutes les phases dans l\'ordre.' },
          { name: 'Stop', desc: 'Interrompt l\'exécution en cours.' },
        ]} />
      </PageDoc>

      <PageDoc id="doc-chat" eyebrow="Pilotage" title="Assistant" to="/chat">
        <p className="doc-p"><span className="badge badge-amber">À venir</span></p>
        <p className="doc-p">
          Fonctionnalité en préparation — <strong>rien de concret pour le moment</strong>. À terme&nbsp;: un chat en langage
          naturel pour interroger votre base (« quelles offres GRC à Paris au-dessus de 70&nbsp;? », « combien de candidatures
          cette semaine&nbsp;? ») sans avoir à construire de filtre.
        </p>
      </PageDoc>

      <div className="doc-divider" />

      {/* CONFIGURATION */}
      <PageDoc id="doc-keywords" eyebrow="Configuration" title="Mots-clés" to="/keywords">
        <p className="doc-p">
          Cette page décide <strong>ce que le robot cherche</strong> et <strong>ce qu'il ignore</strong>. Une saisie par ligne.
          Le premier champ prend de simples mots&nbsp;; les trois autres prennent des <strong>expressions régulières</strong> (regex),
          un mini-langage pour décrire des motifs de texte.
        </p>

        <h4 className="doc-h4">1 · Recherche — les termes envoyés aux sites</h4>
        <p className="doc-p">De simples mots-clés (pas de regex), tapés tels quels sur LinkedIn / Indeed. Exemple pour un profil cybersécurité&nbsp;:</p>
        <pre className="doc-pre">{`cybersécurité
sécurité informatique
ingénieur cybersécurité
consultant GRC
analyste SOC
IAM
pentest
gouvernance de la sécurité
ISO 27001
AI security`}</pre>
        <p className="field-hint">Un terme trop large ramène du bruit, un terme trop précis rate des offres — variez les formulations.</p>

        <h4 className="doc-h4">2 · Mémo regex — pour les trois champs d'exclusion</h4>
        <p className="doc-p">Une regex décrit un motif de texte. Les symboles qui reviennent tout le temps&nbsp;:</p>
        <Fields head={['Symbole', 'Signifie — exemple']} rows={[
          { name: '\\b', desc: <>frontière de mot (vise un mot entier) — <code className="dc">\bsales\b</code> matche «&nbsp;sales&nbsp;», pas «&nbsp;wholesaler&nbsp;»</> },
          { name: '\\w*', desc: <>0 ou + lettres/chiffres — <code className="dc">ingénieur\w*</code> → ingénieur, ingénieurs, ingénieure</> },
          { name: '\\s+', desc: <>1 ou + espaces — <code className="dc">head\s+of</code> → «&nbsp;head of&nbsp;»</> },
          { name: '(?:…|…)', desc: <>un choix entre options — <code className="dc">(?:é|e)</code> → «&nbsp;é&nbsp;» ou «&nbsp;e&nbsp;»</> },
          { name: '?', desc: <>rend l'élément précédent optionnel — <code className="dc">fraudes?</code> → «&nbsp;fraude&nbsp;» ou «&nbsp;fraudes&nbsp;»</> },
          { name: '|', desc: <>OU — <code className="dc">manager|executive</code></> },
          { name: '.', desc: <>n'importe quel caractère (pratique pour l'apostrophe) — <code className="dc">d.affaires</code> → «&nbsp;d'affaires&nbsp;»</> },
        ]} />

        <h4 className="doc-h4">3 · Exclusions par titre — retirer des métiers hors-cible</h4>
        <p className="doc-p">
          Regex appliqués <strong>au titre seul</strong> de l'offre. Parfait pour écarter des intitulés voisins mais hors sujet
          (commercial, sûreté physique, LCB-FT, audit financier) ou des niveaux trop élevés. Exemples réels&nbsp;:
        </p>
        <pre className="doc-pre">{`\\bcommercial(?:e|aux)?\\b            → commercial · commerciale · commerciaux
account\\s+(?:manager|executive)     → account manager · account executive
\\bfraudes?\\b                       → fraude · fraudes
agent\\w*\\s+de\\s+s(?:é|e)curit(?:é|e)   → agent(s) de sécurité
\\bsenior\\b  \\blead\\b  \\bhead of\\b  \\bvp\\b   → niveaux trop élevés`}</pre>
        <div className="doc-note">
          <strong>Construire le vôtre&nbsp;:</strong> partez du mot gênant → entourez-le de <code className="dc">\bmot\b</code> pour
          viser le mot entier → remplacez les accents par <code className="dc">(?:é|e)</code>, les espaces par
          {' '}<code className="dc">\s+</code>, et les fins variables par <code className="dc">s?</code> ou
          {' '}<code className="dc">(?:e|aux)?</code>. Testez-le mentalement sur un vrai titre.
          {' '}<strong>Jamais de crochets <code className="dc">[ ]</code></strong> dans ces champs.
        </div>

        <h4 className="doc-h4">4 · Exclusions globales — titre + description</h4>
        <p className="doc-p">
          Même syntaxe regex, mais le motif est cherché dans <strong>tout le texte</strong> de l'annonce (titre <em>et</em>{' '}
          description). Beaucoup plus tranchant&nbsp;: un seul mot présent n'importe où élimine l'offre. À
          {' '}<strong>réserver aux termes sans aucune ambiguïté</strong> (ex. une techno que vous refusez catégoriquement),
          sinon vous perdez de bonnes offres par faux positif.
        </p>

        <h4 className="doc-h4">5 · Titres WTTJ</h4>
        <p className="field-hint">Regex dédiés aux intitulés Welcome to the Jungle — même mémo que ci-dessus.</p>
      </PageDoc>

      <PageDoc id="doc-jobtypes" eyebrow="Configuration" title="Types de contrat" to="/job-types">
        <p className="doc-p">Cochez les contrats ciblés. Les URLs de recherche de chaque source sont régénérées et affichées en aperçu.</p>
        <Fields head={['Champ', 'Détail']} rows={[
          { name: 'Contrats recherchés', desc: 'CDI · CDD · STAGE · ALTERNANCE. Au moins un requis.' },
          { name: 'Aperçu des URLs', desc: 'URLs générées pour LinkedIn, WTTJ et Indeed selon la sélection.' },
        ]} />
      </PageDoc>

      <PageDoc id="doc-zones" eyebrow="Configuration" title="Zones de scrape" to="/scrape-zones">
        <p className="doc-p">Les zones géographiques interrogées. Une zone désactivée est ignorée au prochain scraping ; les offres déjà collectées restent en base. Au moins une zone active.</p>
        <Fields head={['Zone', 'Portée']} rows={[
          { name: 'France', desc: 'Tous modes de travail (présentiel, hybride, télétravail). LinkedIn + Indeed.' },
          { name: 'Canada', desc: 'Télétravail uniquement — réalisable depuis la France.' },
          { name: 'International', desc: 'Monde entier, télétravail uniquement.' },
        ]} />
      </PageDoc>

      <PageDoc id="doc-prefilter" eyebrow="Configuration" title="Pré-filtre" to="/prefilter">
        <p className="doc-p">Écarte les offres hors-cible <strong>avant</strong> le scoring LLM — donc sans consommer de quota. Complète les « Exclusions par titre ». S'applique au prochain <em>Process</em>.</p>
        <Fields head={['Champ', 'Comment le remplir']} rows={[
          { name: 'Pré-filtre activé', desc: 'Interrupteur maître.' },
          { name: 'Remote mondial exigé', desc: 'Un poste à l\'étranger est éliminé sauf s\'il mentionne un remote mondial explicite.' },
          { name: 'Expérience max', desc: <>Années : une exigence strictement supérieure élimine. Mettre <code className="dc">99</code> pour désactiver.</> },
          { name: 'Termes « hors CDI/CDD »', desc: 'Regex (titre + desc) ; une correspondance élimine (mission, gig, B2B…).' },
          { name: 'Termes « remote mondial »', desc: 'La présence d\'un terme sauve un poste étranger de l\'élimination géo (worldwide…).' },
        ]} />
        <p className="field-hint" style={{ marginTop: 10 }}>
          Les deux champs de termes utilisent des regex — voir le <a href="#doc-keywords">mémo regex</a> (page Mots-clés).
        </p>
      </PageDoc>

      <PageDoc id="doc-prompts" eyebrow="Configuration" title="Prompts" to="/prompts">
        <p className="doc-p">Les instructions envoyées au LLM pour le scoring — le levier le plus puissant sur la sévérité et la grille. À modifier avec soin.</p>
        <Fields head={['Champ', 'Rôle']} rows={[
          { name: 'Prompt système', desc: 'La grille de notation : critères éliminatoires, base, bonus/malus, catégories, axes.' },
          { name: 'Prompt de scoring', desc: <>Le gabarit par offre, variables <code className="dc">{'{title}'}</code> <code className="dc">{'{company}'}</code> <code className="dc">{'{description}'}</code>.</> },
        ]} />
      </PageDoc>

      <PageDoc id="doc-criteria" eyebrow="Configuration" title="Profil candidat" to="/criteria">
        <p className="doc-p">Votre profil en texte libre, <strong>injecté dans le prompt système à chaque scoring</strong>. C'est la référence par rapport à laquelle chaque offre est jugée — plus il est précis, plus le tri est juste.</p>
        <div className="doc-note warn"><strong>À ne pas confondre</strong> avec <code className="dc">profile_master.yaml</code> : ce texte sert au <strong>scoring</strong> ; le YAML sert à la <strong>génération de CV</strong>. Deux fichiers, deux usages.</div>
      </PageDoc>

      <PageDoc id="doc-quotas" eyebrow="Configuration" title="Quotas LLM" to="/quotas">
        <p className="doc-p">Les limites journalières et la cadence de chaque fournisseur — pour éviter de se faire couper (rate-limit) en pleine session.</p>
        <Fields head={['Colonne', 'Signification']} rows={[
          { name: 'Provider · Modèle', desc: 'Fournisseur et identifiant de modèle (lecture seule).' },
          { name: 'Limite / jour', desc: 'Appels max/jour avant bascule vers le fournisseur suivant.' },
          { name: 'TPM', desc: 'Tokens par minute autorisés.' },
          { name: 'Délai (s)', desc: 'Attente minimale entre deux appels.' },
          { name: 'Pause toutes les / (s)', desc: 'Insère une pause de N s tous les M appels.' },
          { name: 'Réinitialiser', desc: 'Remet à zéro les compteurs du jour.' },
        ]} />
      </PageDoc>

      <div className="doc-divider" />

      {/* WORKFLOW */}
      <section id="doc-workflow" className="doc-section card">
        <p className="doc-eyebrow">Prise en main</p>
        <h3 className="doc-h">Flux de travail type</h3>
        <ul className="doc-ul">
          <li className="doc-li"><strong>1. Régler la cible</strong> — <Link to="/criteria">Profil</Link>, <Link to="/keywords">Mots-clés</Link>, <Link to="/job-types">Contrats</Link>, <Link to="/scrape-zones">Zones</Link>, <Link to="/prefilter">Pré-filtre</Link>.</li>
          <li className="doc-li"><strong>2. Collecter</strong> — <Link to="/run">Exécution</Link> → Scrape, puis Filter.</li>
          <li className="doc-li"><strong>3. Scorer</strong> — Process (surveillez les <Link to="/quotas">quotas</Link>).</li>
          <li className="doc-li"><strong>4. Trier</strong> — <Link to="/offers">Offres</Link>, onglet Retenues ; corrigez un fit d'un clic si besoin.</li>
          <li className="doc-li"><strong>5. Postuler</strong> — Générer le CV, ouvrir le lien, puis Postulé (✓) ou Fermer (⊘).</li>
          <li className="doc-li"><strong>6. Suivre</strong> — <Link to="/applications">Candidatures</Link> tient le journal ; l'<Link to="/chat">Assistant</Link> répond à vos questions.</li>
        </ul>
      </section>

      <p className="field-hint" style={{ marginTop: 22, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <ArrowRight size={13} strokeWidth={1.8} /> Chaque titre de section renvoie vers la page réelle correspondante.
      </p>
    </motion.div>
  );
}
