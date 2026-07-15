import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Save } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Toast from '../components/Toast';
import { fetchPrompts, savePrompts } from '../api/api';

export default function Prompts() {
  const [system, setSystem] = useState('');
  const [score, setScore] = useState('');
  const [toast, setToast] = useState<string | null>(null);
  const [toastType, setToastType] = useState<'success' | 'error'>('success');

  useEffect(() => {
    fetchPrompts().then(d => {
      setSystem(d.system_prompt);
      setScore(d.score_prompt);
    }).catch(() => {});
  }, []);

  const handleSave = useCallback(async () => {
    try {
      await savePrompts(system, score);
      setToastType('success');
      setToast('Modifications enregistrées');
    } catch (e) {
      setToastType('error');
      setToast(String(e));
    }
  }, [system, score]);

  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Prompts"
        description="Instructions envoyées au LLM pour le scoring des offres."
      />
      <Toast message={toast} type={toastType} onDone={() => setToast(null)} />

      <div className="card">
        <h3>Prompt système</h3>
        <p className="field-hint">Instructions système pour le scoring LLM</p>
        <textarea className="editor editor-lg" rows={16} value={system} onChange={e => setSystem(e.target.value)} spellCheck={false} />
      </div>

      <div className="card">
        <h3>Prompt de scoring</h3>
        <p className="field-hint">Template d'envoi avec les variables {'{title}'}, {'{company}'}, {'{description}'}</p>
        <textarea className="editor editor-lg" rows={12} value={score} onChange={e => setScore(e.target.value)} spellCheck={false} />
      </div>

      <button className="btn btn-primary" onClick={handleSave}>
        <Save size={14} strokeWidth={1.8} /> Sauvegarder
      </button>
    </motion.div>
  );
}
