import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Save, RotateCcw } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Toast from '../components/Toast';
import { fetchQuotas, saveQuotas, resetQuotas, type QuotaProvider } from '../api/api';

export default function Quotas() {
  const [providers, setProviders] = useState<Record<string, QuotaProvider>>({});
  const [toast, setToast] = useState<string | null>(null);
  const [toastType, setToastType] = useState<'success' | 'error'>('success');

  useEffect(() => {
    fetchQuotas().then(d => setProviders(d.quotas)).catch(() => {});
  }, []);

  const update = (name: string, key: string, val: string) => {
    setProviders(prev => ({
      ...prev,
      [name]: { ...prev[name], [key]: val === '' ? 0 : Number(val) },
    }));
  };

  const handleSave = useCallback(async () => {
    try {
      await saveQuotas(providers as unknown as Record<string, unknown>);
      setToastType('success');
      setToast('Quotas mis à jour');
    } catch (e) {
      setToastType('error');
      setToast(String(e));
    }
  }, [providers]);

  const handleReset = useCallback(async () => {
    try {
      await resetQuotas();
      const d = await fetchQuotas();
      setProviders(d.quotas);
      setToastType('success');
      setToast('Quotas réinitialisés');
    } catch (e) {
      setToastType('error');
      setToast(String(e));
    }
  }, []);

  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Quotas LLM"
        description="Limites journalières et cadence d'appel pour chaque fournisseur."
      />
      <Toast message={toast} type={toastType} onDone={() => setToast(null)} />

      <div className="card">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Provider</th>
                <th>Modèle</th>
                <th>Limite / jour</th>
                <th>TPM</th>
                <th>Délai (s)</th>
                <th>Pause toutes les</th>
                <th>Pause (s)</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(providers).map(([name, q]) => (
                <tr key={name}>
                  <td style={{ fontWeight: 500 }}>{name}</td>
                  <td className="td-model">{q.model}</td>
                  <td><input type="number" className="input-sm" value={q.daily_limit} onChange={e => update(name, 'daily_limit', e.target.value)} /></td>
                  <td><input type="number" className="input-sm" value={q.tpm_limit ?? ''} onChange={e => update(name, 'tpm_limit', e.target.value)} /></td>
                  <td><input type="number" className="input-sm" value={q.delay_seconds} onChange={e => update(name, 'delay_seconds', e.target.value)} /></td>
                  <td><input type="number" className="input-sm" value={q.pause_every ?? ''} onChange={e => update(name, 'pause_every', e.target.value)} /></td>
                  <td><input type="number" className="input-sm" value={q.pause_duration ?? ''} onChange={e => update(name, 'pause_duration', e.target.value)} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="btn-group">
        <button className="btn btn-primary" onClick={handleSave}>
          <Save size={14} strokeWidth={1.8} /> Sauvegarder
        </button>
        <button className="btn btn-ghost" onClick={handleReset}>
          <RotateCcw size={14} strokeWidth={1.8} /> Réinitialiser
        </button>
      </div>
    </motion.div>
  );
}
