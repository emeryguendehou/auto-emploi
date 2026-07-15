import { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { ExternalLink, FileDown, Loader2, Check, Ban } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { fetchOffers, generateCv, cvUrl, setPostule, setClosed, setOfferScore, type Offer } from '../api/api';

const STATUT_BADGE: Record<string, string> = {
  'Prioritaire': 'badge-green',
  'À étudier': 'badge-amber',
  'Ignorée': 'badge-red',
  'Éliminée': 'badge-gray',
  'À traiter': 'badge-blue',
};

type Filter = { key: string; label: string; match: (o: Offer) => boolean };

const FILTERS: Filter[] = [
  { key: 'retenues', label: 'Retenues', match: (o) => o.statut === 'Prioritaire' || o.statut === 'À étudier' },
  { key: 'all', label: 'Toutes', match: () => true },
  { key: 'a_traiter', label: 'À traiter', match: (o) => o.statut === 'À traiter' },
  { key: 'prioritaire', label: 'Prioritaires', match: (o) => o.statut === 'Prioritaire' },
  { key: 'a_etudier', label: 'À étudier', match: (o) => o.statut === 'À étudier' },
  { key: 'ignoree', label: 'Ignorées', match: (o) => o.statut === 'Ignorée' },
  { key: 'eliminee', label: 'Éliminées', match: (o) => o.statut === 'Éliminée' },
];

const MAX_ROWS = 300;

function scoreClass(score: number | null | undefined): string {
  if (score == null) return 'score-low';
  if (score >= 75) return 'score-high';
  if (score >= 50) return 'score-mid';
  return 'score-low';
}

// Compacte les localisations franciliennes omniprésentes pour éviter que le
// tableau ne déborde ("Montrouge, Île-de-France, France" -> "Montrouge").
export function shortLoc(loc: string): string {
  return loc
    .replace(/,?\s*Île-de-France/i, '')
    .replace(/,?\s*France$/i, '')
    .trim()
    .replace(/,$/, '') || 'Île-de-France';
}

export function shortSalaire(s: string): string {
  return !s || /non précisé/i.test(s) ? '—' : s;
}

export default function Offers() {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [filter, setFilter] = useState('retenues');
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState<string | null>(null);
  const [genError, setGenError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editVal, setEditVal] = useState('');

  const startEdit = (o: Offer) => { setEditing(o.id); setEditVal(String(o.score ?? '')); };

  const commitEdit = async (o: Offer) => {
    const v = Math.max(0, Math.min(100, parseInt(editVal, 10)));
    setEditing(null);
    if (Number.isNaN(v) || v === o.score) return;
    try {
      const r = await setOfferScore(o.id, v);
      if (r.ok) {
        setOffers((prev) => prev.map((x) =>
          x.id === o.id ? { ...x, score: r.score, score_global: r.score_global } : x));
      }
    } catch (e) {
      setGenError(`Échec de la correction de score : ${String(e)}`);
    }
  };

  const onGenerate = async (o: Offer) => {
    if (generating) return;
    setGenerating(o.id);
    setGenError(null);
    try {
      const r = await generateCv(o.id);
      if (r.ok) {
        setOffers((prev) => prev.map((x) => (x.id === o.id ? { ...x, cv_genere: true } : x)));
      }
    } catch (e) {
      setGenError(`Échec de génération pour ${o.entreprise} : ${String(e)}`);
    } finally {
      setGenerating(null);
    }
  };

  useEffect(() => {
    fetchOffers()
      .then((d) => { setOffers(d.offers); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const onPostule = async (o: Offer) => {
    // Optimiste : l'offre bascule immédiatement vers la page Candidatures.
    setOffers((prev) => prev.map((x) => (x.id === o.id ? { ...x, postule: true } : x)));
    try {
      await setPostule(o.id, true);
    } catch {
      setOffers((prev) => prev.map((x) => (x.id === o.id ? { ...x, postule: false } : x)));
    }
  };

  const onClose = async (o: Offer) => {
    // Optimiste : l'offre bascule vers la page Offres fermées.
    setOffers((prev) => prev.map((x) => (x.id === o.id ? { ...x, closed: true } : x)));
    try {
      await setClosed(o.id, true);
    } catch {
      setOffers((prev) => prev.map((x) => (x.id === o.id ? { ...x, closed: false } : x)));
    }
  };

  // Les offres postulées (Candidatures) et fermées (Offres fermées) sortent d'ici.
  const pool = useMemo(() => offers.filter((o) => !o.postule && !o.closed), [offers]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const f of FILTERS) c[f.key] = pool.filter(f.match).length;
    return c;
  }, [pool]);

  const active = FILTERS.find((f) => f.key === filter) ?? FILTERS[0];
  const filtered = pool.filter(active.match);
  const shown = filtered.slice(0, MAX_ROWS);

  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Offres"
        description="Offres collectées, scorées puis classées par le pipeline LLM."
      />

      <div className="tabs">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`tab${filter === f.key ? ' active' : ''}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
            <span className="tab-count">{counts[f.key] ?? 0}</span>
          </button>
        ))}
      </div>

      {genError && <p className="error-note">{genError}</p>}

      {loading ? (
        <p className="empty-note">Chargement…</p>
      ) : (
        <div className="card">
          <p className="table-meta">
            {filtered.length} offre{filtered.length > 1 ? 's' : ''}
            {filtered.length > MAX_ROWS ? ` — ${MAX_ROWS} premières affichées` : ''}
            {' · triées par score global'}
          </p>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Global</th><th>Fit</th><th>Statut</th><th>Catégorie</th><th>Contrat</th>
                  <th>Entreprise</th><th>Poste</th><th>Localisation</th><th>Salaire</th><th>Lien</th><th>CV</th><th>Suivi</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((o, i) => (
                  <tr key={i}>
                    <td><span className={`score-pill ${scoreClass(o.score_global)}`}>{o.score_global ?? '—'}</span></td>
                    <td className="td-num td-dim">
                      {editing === o.id ? (
                        <input
                          type="number" min={0} max={100} value={editVal} autoFocus
                          onChange={(e) => setEditVal(e.target.value)}
                          onBlur={() => commitEdit(o)}
                          onKeyDown={(e) => { if (e.key === 'Enter') commitEdit(o); if (e.key === 'Escape') setEditing(null); }}
                          style={{ width: 48 }}
                        />
                      ) : (
                        <span
                          onClick={() => startEdit(o)}
                          title="Cliquer pour corriger le score"
                          style={{ cursor: 'pointer', borderBottom: '1px dotted var(--border, #999)' }}
                        >{o.score ?? '—'}</span>
                      )}
                    </td>
                    <td><span className={`badge ${STATUT_BADGE[o.statut] ?? 'badge-gray'}`}>{o.statut}</span></td>
                    <td className="td-dim">{o.categorie}</td>
                    <td className="td-dim">{o.type_contrat}</td>
                    <td style={{ fontWeight: 500 }}>{o.entreprise}</td>
                    <td>{o.titre}</td>
                    <td className="td-dim">{shortLoc(o.localisation)}</td>
                    <td className="td-dim">{shortSalaire(o.salaire)}</td>
                    <td>
                      {o.lien && (
                        <a href={o.lien} target="_blank" rel="noreferrer" title="Ouvrir l'annonce">
                          <ExternalLink size={14} strokeWidth={1.8} />
                        </a>
                      )}
                    </td>
                    <td>
                      {o.cv_genere ? (
                        <a href={cvUrl(o.id)} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                          <FileDown size={14} strokeWidth={1.8} /> PDF
                        </a>
                      ) : o.score && o.score > 0 ? (
                        <button
                          className="btn btn-secondary btn-sm"
                          disabled={generating !== null}
                          onClick={() => onGenerate(o)}
                        >
                          {generating === o.id
                            ? <Loader2 size={13} strokeWidth={2} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                            : 'Générer'}
                        </button>
                      ) : null}
                    </td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="row-action"
                          title="Marquer comme postulée — l'offre passe dans Candidatures"
                          onClick={() => onPostule(o)}
                        >
                          <Check size={14} strokeWidth={2.2} />
                        </button>
                        <button
                          className="row-action row-action-danger"
                          title="Marquer comme fermée — l'offre passe dans Offres fermées"
                          onClick={() => onClose(o)}
                        >
                          <Ban size={13} strokeWidth={1.8} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </motion.div>
  );
}
