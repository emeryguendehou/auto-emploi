import { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { ExternalLink, RotateCcw, Ban } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { fetchOffers, setClosed, type Offer } from '../api/api';
import { shortLoc } from './Offers';

const STATUT_BADGE: Record<string, string> = {
  'Prioritaire': 'badge-green',
  'À étudier': 'badge-amber',
  'Ignorée': 'badge-red',
  'Éliminée': 'badge-gray',
  'À traiter': 'badge-blue',
};

export default function Closed() {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchOffers()
      .then((d) => { setOffers(d.offers); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const onReopen = async (o: Offer) => {
    setOffers((prev) => prev.map((x) => (x.id === o.id ? { ...x, closed: false } : x)));
    try {
      await setClosed(o.id, false);
    } catch {
      setOffers((prev) => prev.map((x) => (x.id === o.id ? { ...x, closed: true } : x)));
    }
  };

  // Fermées non postulées : une offre à laquelle on a postulé reste dans Candidatures.
  const closed = useMemo(
    () => offers
      .filter((o) => o.closed && !o.postule)
      .sort((a, b) => (b.date_closed || '').localeCompare(a.date_closed || '')),
    [offers],
  );

  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Offres fermées"
        description="Offres pourvues ou n'acceptant plus de candidatures. Rouvrir pour les renvoyer dans la liste."
      />

      {loading ? (
        <p className="empty-note">Chargement…</p>
      ) : closed.length === 0 ? (
        <div className="card empty-state">
          <Ban size={20} strokeWidth={1.5} />
          <p className="empty-note">
            Aucune offre fermée — utilisez le bouton « Fermer » sur la page Offres.
          </p>
        </div>
      ) : (
        <div className="card">
          <p className="table-meta">
            {closed.length} offre{closed.length > 1 ? 's' : ''} fermée{closed.length > 1 ? 's' : ''} · les plus récentes d'abord
          </p>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Fermée le</th><th>Global</th><th>Statut</th><th>Catégorie</th>
                  <th>Entreprise</th><th>Poste</th><th>Localisation</th><th>Lien</th><th></th>
                </tr>
              </thead>
              <tbody>
                {closed.map((o) => (
                  <tr key={o.id}>
                    <td className="td-num" style={{ whiteSpace: 'nowrap' }}>{o.date_closed || '—'}</td>
                    <td><span className="score-pill score-low">{o.score_global ?? '—'}</span></td>
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
                      <button
                        className="btn btn-ghost btn-sm"
                        title="Rouvrir — renvoyer l'offre dans la liste"
                        onClick={() => onReopen(o)}
                      >
                        <RotateCcw size={13} strokeWidth={1.8} />
                        Rouvrir
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
