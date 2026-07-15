import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Play, Square, Loader2, CircleCheck, CircleX, CirclePause, Circle } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import TerminalLog from '../components/TerminalLog';
import ProgressBar from '../components/ProgressBar';
import Toast from '../components/Toast';
import { startPhase, stopRun } from '../api/api';
import { useSSE } from '../api/useSSE';

const PHASES = [
  { key: 'scrape', label: 'Scrape' },
  { key: 'filter', label: 'Filter' },
  { key: 'process', label: 'Process' },
  { key: 'notion', label: 'Notion' },
  { key: 'keep', label: 'Keep' },
  { key: 'all', label: 'Pipeline complet' },
] as const;

const STATUS_META: Record<string, { label: string; color: string; icon: typeof Circle }> = {
  idle: { label: 'En attente', color: 'var(--text-2)', icon: Circle },
  running: { label: 'En cours', color: 'var(--accent-hover)', icon: Loader2 },
  completed: { label: 'Terminé', color: 'var(--green)', icon: CircleCheck },
  failed: { label: 'Échec', color: 'var(--red)', icon: CircleX },
  stopped: { label: 'Arrêté', color: 'var(--amber)', icon: CirclePause },
};

export default function Run() {
  const { state, connect, disconnect, clearLogs } = useSSE();
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  const handleStart = async (phase: string) => {
    clearLogs();
    try {
      await startPhase(phase);
    } catch { /* ignore */ }
  };

  const handleStop = async () => {
    try {
      await stopRun();
    } catch { /* ignore */ }
  };

  const meta = STATUS_META[state.status] ?? STATUS_META.idle;
  const StatusIcon = meta.icon;

  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Exécution"
        description="Lancez une phase du pipeline et suivez la sortie en temps réel."
      />
      <Toast message={toast?.msg ?? null} type={toast?.type ?? 'success'} onDone={() => setToast(null)} />

      <div className="card">
        <h3>Phases</h3>
        <p className="field-hint">Chaque phase s'exécute dans un sous-processus dédié</p>
        <div className="btn-group" style={{ marginTop: 0 }}>
          {PHASES.map(p => (
            <button
              key={p.key}
              className={`btn ${p.key === 'all' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => handleStart(p.key)}
              disabled={state.status === 'running'}
            >
              <Play size={13} strokeWidth={2} />
              {p.label}
            </button>
          ))}
          <button
            className="btn btn-danger"
            onClick={handleStop}
            disabled={state.status !== 'running'}
          >
            <Square size={12} strokeWidth={2} />
            Stop
          </button>
        </div>
      </div>

      <div className="card">
        <div className="run-header">
          <StatusIcon
            size={16}
            strokeWidth={2}
            style={{
              color: meta.color,
              animation: state.status === 'running' ? 'spin 1s linear infinite' : undefined,
            }}
          />
          <h3 style={{ marginBottom: 0 }}>{meta.label}</h3>
          {state.connected && <span className="sse-dot" title="Flux SSE connecté" />}
        </div>

        {state.status !== 'idle' && (
          <>
            <p className="run-meta">
              Phase <strong>{state.phase}</strong>
              <span> · démarrée à {state.startedAt || '—'}</span>
              <span> · {state.logs.length} ligne{state.logs.length > 1 ? 's' : ''}</span>
            </p>

            <ProgressBar status={state.status} />

            <TerminalLog logs={state.logs} />
          </>
        )}
      </div>
    </motion.div>
  );
}
