import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Save, Check, Globe, MapPin } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Toast from '../components/Toast';
import { fetchScrapeZones, saveScrapeZones, type ScrapeZone } from '../api/api';

const ZONE_HINT: Record<string, string> = {
  'France': 'Tous modes de travail (présentiel, hybride, télétravail).',
  'Canada': 'Télétravail uniquement — réalisable depuis la France.',
  'International (full remote)': 'Tous les pays (monde entier), télétravail uniquement.',
};

export default function ScrapeZones() {
  const [zones, setZones] = useState<ScrapeZone[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const [toastType, setToastType] = useState<'success' | 'error'>('success');

  useEffect(() => {
    fetchScrapeZones().then(d => setZones(d.zones)).catch(() => {});
  }, []);

  const toggle = (label: string) => {
    setZones(prev => prev.map(z => (z.label === label ? { ...z, enabled: !z.enabled } : z)));
  };

  const handleSave = useCallback(async () => {
    try {
      if (!zones.some(z => z.enabled)) {
        setToastType('error');
        setToast('Activez au moins une zone.');
        return;
      }
      const map: Record<string, boolean> = {};
      zones.forEach(z => { map[z.label] = z.enabled; });
      await saveScrapeZones(map);
      setToastType('success');
      setToast('Zones enregistrées');
    } catch (e) {
      setToastType('error');
      setToast(String(e));
    }
  }, [zones]);

  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Zones de scrape"
        description="Choisissez les zones géographiques interrogées lors du scraping."
      />
      <Toast message={toast} type={toastType} onDone={() => setToast(null)} />

      <div className="card">
        <h3>Zones actives</h3>
        <p className="field-hint">
          Une zone désactivée est ignorée au prochain scraping ; les offres déjà collectées restent en base.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
          {zones.map(z => (
            <label
              key={z.label}
              className={`check-chip${z.enabled ? ' checked' : ''}`}
              style={{ justifyContent: 'flex-start', padding: '12px 14px', alignItems: 'flex-start' }}
            >
              <input type="checkbox" checked={z.enabled} onChange={() => toggle(z.label)} />
              <span className="check-box" style={{ marginTop: 2 }}>
                {z.enabled && <Check size={11} strokeWidth={3} />}
              </span>
              <span style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                <span style={{ fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  {z.label.startsWith('International')
                    ? <Globe size={14} strokeWidth={1.8} />
                    : <MapPin size={14} strokeWidth={1.8} />}
                  {z.label}
                </span>
                <span className="field-hint" style={{ margin: 0 }}>
                  {ZONE_HINT[z.label] ?? ''}
                  {z.indeed ? ' · LinkedIn + Indeed' : ' · LinkedIn seul'}
                </span>
              </span>
            </label>
          ))}
        </div>
      </div>

      <button className="btn btn-primary" onClick={handleSave}>
        <Save size={14} strokeWidth={1.8} /> Sauvegarder
      </button>
    </motion.div>
  );
}
