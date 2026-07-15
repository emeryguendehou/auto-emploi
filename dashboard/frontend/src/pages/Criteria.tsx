import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Save } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Toast from '../components/Toast';
import { fetchCriteria, saveCriteria } from '../api/api';

export default function Criteria() {
  const [content, setContent] = useState('');
  const [toast, setToast] = useState<string | null>(null);
  const [toastType, setToastType] = useState<'success' | 'error'>('success');

  useEffect(() => {
    fetchCriteria().then(d => setContent(d.content)).catch(() => {});
  }, []);

  const handleSave = useCallback(async () => {
    try {
      await saveCriteria(content);
      setToastType('success');
      setToast('Modifications enregistrées');
    } catch (e) {
      setToastType('error');
      setToast(String(e));
    }
  }, [content]);

  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Profil candidat"
        description="Ce profil est injecté dans le prompt système à chaque scoring d'offre."
      />
      <Toast message={toast} type={toastType} onDone={() => setToast(null)} />

      <div className="card">
        <textarea className="editor editor-lg" rows={20} value={content} onChange={e => setContent(e.target.value)} spellCheck={false} />
      </div>

      <button className="btn btn-primary" onClick={handleSave}>
        <Save size={14} strokeWidth={1.8} /> Sauvegarder
      </button>
    </motion.div>
  );
}
