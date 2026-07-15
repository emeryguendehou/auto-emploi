import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Save, Check } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Toast from '../components/Toast';
import { fetchJobTypes, saveJobTypes } from '../api/api';

const ALL_TYPES = ['cdi', 'cdd', 'stage', 'alternance'];

export default function JobTypes() {
  const [selected, setSelected] = useState<string[]>([]);
  const [preview, setPreview] = useState({ linkedin: '', wttj: '', indeed: '' });
  const [toast, setToast] = useState<string | null>(null);
  const [toastType, setToastType] = useState<'success' | 'error'>('success');

  useEffect(() => {
    fetchJobTypes().then(d => {
      setSelected(d.job_types);
      setPreview(d.preview);
    }).catch(() => {});
  }, []);

  const toggle = (t: string) => {
    setSelected(prev => prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t]);
  };

  const handleSave = useCallback(async () => {
    try {
      const data = await saveJobTypes(selected.length ? selected : ['alternance']);
      if (data && typeof data === 'object' && 'preview' in data) {
        setPreview((data as any).preview);
      }
      setToastType('success');
      setToast('Modifications enregistrées');
    } catch (e) {
      setToastType('error');
      setToast(String(e));
    }
  }, [selected]);

  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Types de contrat"
        description="Contrats ciblés par le scraping — les URLs de recherche sont générées automatiquement."
      />
      <Toast message={toast} type={toastType} onDone={() => setToast(null)} />

      <div className="card">
        <h3>Contrats recherchés</h3>
        <p className="field-hint">Sélectionnez au moins un type de contrat</p>
        <div className="checkbox-group">
          {ALL_TYPES.map(t => {
            const checked = selected.includes(t);
            return (
              <label key={t} className={`check-chip${checked ? ' checked' : ''}`}>
                <input type="checkbox" checked={checked} onChange={() => toggle(t)} />
                <span className="check-box">{checked && <Check size={11} strokeWidth={3} />}</span>
                {t.toUpperCase()}
              </label>
            );
          })}
        </div>
      </div>

      {selected.length > 0 && (
        <div className="card">
          <h3>Aperçu des URLs</h3>
          <p className="field-hint">URLs de recherche générées pour chaque source</p>
          {preview.linkedin && (
            <div className="preview-source">
              <div className="preview-label">LinkedIn</div>
              <div className="preview-url">{preview.linkedin}</div>
            </div>
          )}
          {preview.wttj && (
            <div className="preview-source">
              <div className="preview-label">Welcome to the Jungle</div>
              <div className="preview-url">{preview.wttj}</div>
            </div>
          )}
          {preview.indeed && (
            <div className="preview-source">
              <div className="preview-label">Indeed</div>
              <div className="preview-url">{preview.indeed}</div>
            </div>
          )}
        </div>
      )}

      <button className="btn btn-primary" onClick={handleSave}>
        <Save size={14} strokeWidth={1.8} /> Sauvegarder
      </button>
    </motion.div>
  );
}
