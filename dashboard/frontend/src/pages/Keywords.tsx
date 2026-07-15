import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Save } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Toast from '../components/Toast';
import { fetchKeywords, saveKeywords } from '../api/api';

export default function Keywords() {
  const [keywords, setKeywords] = useState('');
  const [wttj, setWttj] = useState('');
  const [exclusion, setExclusion] = useState('');
  const [titleExclusion, setTitleExclusion] = useState('');
  const [toast, setToast] = useState<string | null>(null);
  const [toastType, setToastType] = useState<'success' | 'error'>('success');

  useEffect(() => {
    fetchKeywords().then(d => {
      setKeywords(d.keywords.join('\n'));
      setWttj(d.wttj_keywords.join('\n'));
      setExclusion(d.exclusion.join('\n'));
      setTitleExclusion((d.title_exclusion ?? []).join('\n'));
    }).catch(() => {});
  }, []);

  const handleSave = useCallback(async () => {
    try {
      const kw = keywords.split('\n').map(s => s.trim()).filter(Boolean);
      const wj = wttj.split('\n').map(s => s.trim()).filter(Boolean);
      const ex = exclusion.split('\n').map(s => s.trim()).filter(Boolean);
      const tex = titleExclusion.split('\n').map(s => s.trim()).filter(Boolean);
      await saveKeywords(kw, wj, ex, tex);
      setToastType('success');
      setToast('Modifications enregistrées');
    } catch (e) {
      setToastType('error');
      setToast(String(e));
    }
  }, [keywords, wttj, exclusion, titleExclusion]);

  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Mots-clés"
        description="Termes de recherche et filtres appliqués lors du scraping des offres."
      />
      <Toast message={toast} type={toastType} onDone={() => setToast(null)} />

      <div className="card">
        <h3>Recherche</h3>
        <p className="field-hint">Mots-clés de recherche, un par ligne</p>
        <textarea className="editor" rows={8} value={keywords} onChange={e => setKeywords(e.target.value)} spellCheck={false} />
      </div>

      <div className="card">
        <h3>Titres WTTJ</h3>
        <p className="field-hint">Patterns regex pour filtrer les titres Welcome to the Jungle</p>
        <textarea className="editor" rows={8} value={wttj} onChange={e => setWttj(e.target.value)} spellCheck={false} />
      </div>

      <div className="card">
        <h3>Exclusions par titre</h3>
        <p className="field-hint">
          Patterns regex appliqués au titre de l'offre uniquement — intitulés métiers hors-cible
          (commercial, anti-fraude, sécurité physique, GRC financière…). Pas de crochets [ ] dans les patterns.
        </p>
        <textarea className="editor" rows={12} value={titleExclusion} onChange={e => setTitleExclusion(e.target.value)} spellCheck={false} />
      </div>

      <div className="card">
        <h3>Exclusions globales</h3>
        <p className="field-hint">Patterns regex appliqués au titre + description — à réserver aux termes sans ambiguïté (technos legacy…)</p>
        <textarea className="editor" rows={6} value={exclusion} onChange={e => setExclusion(e.target.value)} spellCheck={false} />
      </div>

      <button className="btn btn-primary" onClick={handleSave}>
        <Save size={14} strokeWidth={1.8} /> Sauvegarder
      </button>
    </motion.div>
  );
}
