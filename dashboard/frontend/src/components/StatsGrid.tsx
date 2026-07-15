import type { Stats } from '../api/api';

const CARD_CONFIG = [
  { key: 'total', label: 'Total offres', color: 'var(--accent)' },
  { key: 'unprocessed', label: 'À traiter', color: 'var(--blue)' },
  { key: 'excluded', label: 'Exclues', color: 'var(--gray)' },
  { key: 'prioritaires', label: 'Prioritaires', color: 'var(--green)' },
  { key: 'a_etudier', label: 'À étudier', color: 'var(--amber)' },
  { key: 'ignores', label: 'Ignorées', color: 'var(--red)' },
  { key: 'postule', label: 'Candidatures', color: '#6f7ae0' },
  { key: 'closed', label: 'Offres fermées', color: '#d9704f' },
  { key: 'in_notion', label: 'Dans Notion', color: '#a78bfa' },
] as const;

interface Props {
  stats: Stats | null;
}

export default function StatsGrid({ stats }: Props) {
  if (!stats) return null;

  return (
    <div className="stats-grid">
      {CARD_CONFIG.map(c => (
        <div key={c.key} className="stat-card">
          <div className="stat-head">
            <span className="stat-dot" style={{ background: c.color, color: c.color }} />
            <span className="stat-label">{c.label}</span>
          </div>
          <div className="stat-value">{stats[c.key as keyof Stats]}</div>
        </div>
      ))}
    </div>
  );
}
