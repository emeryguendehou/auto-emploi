import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import PageHeader from '../components/PageHeader';
import StatsGrid from '../components/StatsGrid';
import { fetchStats, fetchQuotas, type Stats, type QuotasData } from '../api/api';

export default function Overview() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [quotas, setQuotas] = useState<QuotasData | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [s, q] = await Promise.all([fetchStats(), fetchQuotas()]);
        setStats(s);
        setQuotas(q);
      } catch { /* ignore */ }
    };
    load();
    const si = setInterval(load, 30000);
    return () => clearInterval(si);
  }, []);

  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Vue d'ensemble"
        description="État du pipeline de prospection et consommation des quotas LLM."
      />
      <StatsGrid stats={stats} />

      {quotas && (
        <div className="card" style={{ marginTop: 24 }}>
          <h3>Quotas LLM</h3>
          <p className="field-hint">Consommation du jour, par fournisseur</p>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Provider</th>
                  <th>Modèle</th>
                  <th>Utilisé</th>
                  <th>Restant</th>
                  <th>Succès / Échecs</th>
                  <th>Consommation</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(quotas.quotas).map(([name, q]) => {
                  const usage = quotas.today_usage[name];
                  const used = usage?.used ?? 0;
                  const success = usage?.success ?? 0;
                  const fail = usage?.fail ?? 0;
                  const limit = q.daily_limit ?? 0;
                  const remaining = Math.max(0, limit - used);
                  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;
                  // Couleur : vert < 70 %, ambre < 90 %, rouge au-delà.
                  const barColor = pct >= 90 ? 'var(--red)' : pct >= 70 ? 'var(--amber)' : 'var(--green)';
                  return (
                    <tr key={name}>
                      <td style={{ fontWeight: 500 }}>{name}</td>
                      <td className="td-model">{q.model}</td>
                      <td className="td-num td-dim">{used} / {limit}</td>
                      <td className="td-num td-dim">{remaining}</td>
                      <td className="td-num">
                        <span style={{ color: 'var(--green)' }}>{success}</span>
                        <span className="td-dim"> / </span>
                        <span style={{ color: fail ? 'var(--red)' : 'var(--text-3)' }}>{fail}</span>
                      </td>
                      <td>
                        <div className="meter">
                          <div className="meter-fill" style={{ width: `${pct}%`, background: barColor }} />
                        </div>
                        <span className="meter-num">{pct}%</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </motion.div>
  );
}
