import { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { ExternalLink, FileDown, Undo2, Send } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { fetchOffers, cvUrl, setPostule, type Offer } from '../api/api';
import { shortLoc } from './Offers';

const STATUT_BADGE: Record<string, string> = {
  'Prioritaire': 'badge-green',
  'À étudier': 'badge-amber',
  'Ignorée': 'badge-red',
  'Éliminée': 'badge-gray',
  'À traiter': 'badge-blue',
};

export default function Applications() {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchOffers()
      .then((d) => { setOffers(d.offers); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const onCancel = async (o: Offer) => {
    setOffers((prev) => prev.map((x) => (x.id === o.id ? { ...x, postule: false } : x)));
    try {
      await setPostule(o.id, false);
    } catch {
      setOffers((prev) => prev.map((x) => (x.id === o.id ? { ...x, postule: true } : x)));
    }
  };

  const applied = useMemo(
    () => offers
      .filter((o) => o.postule)
      .sort((a, b) => (b.date_postule || '').localeCompare(a.date_postule || '')),
    [offers],
  );

  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Candidatures"
        description="Les offres auxquelles vous avez postulé. Décochez pour renvoyer une offre dans la liste."
      />

      {loading ? (
        <p className="empty-note">Chargement…</p>
      ) : applied.length === 0 ? (
        <div className="card empty-state">
          <Send size={20} strokeWidth={1.5} />
          <p className="empty-note">
            Aucune candidature pour le moment — utilisez le bouton « Postulé » sur la page Offres.
          </p>
        </div>
      ) : (
        <div className="card">
          <p className="table-meta">
            {applied.length} candidature{applied.length > 1 ? 's' : ''} · les plus récentes d'abord
          </p>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Postulé le</th><th>Global</th><th>Statut</th><th>Catégorie</th>
                  <th>Entreprise</th><th>Poste</th><th>Localisation</th><th>Lien</th><th>CV</th><th></th>
                </tr>
              </thead>
              <tbody>
                {applied.map((o) => (
                  <tr key={o.id}>
                    <td className="td-num" style={{ whiteSpace: 'nowrap' }}>{o.date_postule || '—'}</td>
                    <td><span className="score-pill score-high">{o.score_global ?? '—'}</span></td>
                    <td><span className={`badge ${STATUT_BADGE[o.statut] ?? 'badge-gray'}`}>{o.statut}</span></td>
                    <td className="td-dim">{o.categorie}</td>
                    <td style={{ fontWeight: 500 }}>{o.entreprise}</td>
                    <td>{o.titre}</td>
                    <td className="td-dim">{shortLoc(o.localisation)}</td>
                    <td>
                      {o.lien && (
                        <a href={o.lien} target="_blank" rel="noreferrer" title="Ouvrir l'annonce">
                          <ExternalLink size={14} strokeWidth={1.8} />
                        </a>
                      )}
                    </td>
                    <td>
                      {o.cv_genere && (
                        <a href={cvUrl(o.id)} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                          <FileDown size={14} strokeWidth={1.8} /> PDF
                        </a>
                      )}
                    </td>
                    <td>
                      <button
                        className="btn btn-ghost btn-sm"
                        title="Annuler — renvoyer l'offre dans la liste"
                        onClick={() => onCancel(o)}
                      >
                        <Undo2 size={13} strokeWidth={1.8} />
                        Annuler
                      </button>
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
