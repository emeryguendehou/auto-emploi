import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Save, Check, Filter } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Toast from '../components/Toast';
import { fetchPrefilter, savePrefilter } from '../api/api';

export default function Prefilter() {
  const [enabled, setEnabled] = useState(true);
  const [foreign, setForeign] = useState(true);
  const [maxExp, setMaxExp] = useState(3);
  const [contract, setContract] = useState('');
  const [global, setGlobal] = useState('');
  const [toast, setToast] = useState<string | null>(null);
  const [toastType, setToastType] = useState<'success' | 'error'>('success');

  useEffect(() => {
    fetchPrefilter().then(p => {
      setEnabled(p.enabled);
      setForeign(p.foreign_require_global_remote);
      setMaxExp(p.max_exp_years);
      setContract(p.contract_terms.join('\n'));
      setGlobal(p.global_remote_terms.join('\n'));
    }).catch(() => {});
  }, []);

  const handleSave = useCallback(async () => {
    try {
      await savePrefilter({
        enabled,
        foreign_require_global_remote: foreign,
        max_exp_years: Number(maxExp) || 3,
        contract_terms: contract.split('\n').map(s => s.trim()).filter(Boolean),
        global_remote_terms: global.split('\n').map(s => s.trim()).filter(Boolean),
      });
      setToastType('success');
      setToast('Pré-filtre enregistré');
    } catch (e) {
      setToastType('error');
      setToast(String(e));
    }
  }, [enabled, foreign, maxExp, contract, global]);

  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Pré-filtre"
        description="Écarte les offres hors-cible AVANT le scoring LLM — économise les quotas. Tout est éditable ici."
      />
      <Toast message={toast} type={toastType} onDone={() => setToast(null)} />

      <div className="card">
        <h3>Activation</h3>
        <p className="field-hint">
          Le pré-filtre complète les « Exclusions par titre » (page Mots-clés) : il écarte à 0, sans appel LLM,
          les contrats hors CDI/CDD, l'expérience trop élevée et l'étranger non full-remote.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
          <label className={`check-chip${enabled ? ' checked' : ''}`} style={{ justifyContent: 'flex-start' }}>
            <input type="checkbox" checked={enabled} onChange={() => setEnabled(v => !v)} />
            <span className="check-box">{enabled && <Check size={11} strokeWidth={3} />}</span>
            Pré-filtre activé
          </label>
          <label className={`check-chip${foreign ? ' checked' : ''}`} style={{ justifyContent: 'flex-start' }}>
            <input type="checkbox" checked={foreign} onChange={() => setForeign(v => !v)} />
            <span className="check-box">{foreign && <Check size={11} strokeWidth={3} />}</span>
            Étranger : exiger un remote mondial explicite (sinon éliminé)
          </label>
        </div>
      </div>

      <div className="card">
        <h3>Expérience maximale</h3>
        <p className="field-hint">Une exigence strictement supérieure élimine l'offre. Mettre 99 pour désactiver.</p>
        <input
          type="number" min={0} max={99} value={maxExp}
          onChange={e => setMaxExp(Number(e.target.value))}
          style={{ width: 90 }} className="editor"
        /> <span className="field-hint" style={{ marginLeft: 8 }}>ans</span>
      </div>

      <div className="card">
        <h3>Termes « contrat hors CDI/CDD »</h3>
        <p className="field-hint">
          Patterns regex (titre + description). Une correspondance élimine l'offre (mission, gig, horaire, B2B…).
          Un par ligne, pas de crochets [ ].
        </p>
        <textarea className="editor" rows={10} value={contract} onChange={e => setContract(e.target.value)} spellCheck={false} />
      </div>

      <div className="card">
        <h3>Termes « remote mondial »</h3>
        <p className="field-hint">
          Pour un poste étranger, la présence d'un de ces termes le SAUVE de l'élimination géographique
          (work from anywhere, worldwide…). Un par ligne.
        </p>
        <textarea className="editor" rows={8} value={global} onChange={e => setGlobal(e.target.value)} spellCheck={false} />
      </div>

      <button className="btn btn-primary" onClick={handleSave}>
        <Save size={14} strokeWidth={1.8} /> Sauvegarder
      </button>
      <p className="field-hint" style={{ marginTop: 10, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <Filter size={13} strokeWidth={1.8} /> S'applique au prochain scoring (phase process).
      </p>
    </motion.div>
  );
}
