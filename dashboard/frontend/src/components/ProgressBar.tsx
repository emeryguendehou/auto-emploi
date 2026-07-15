import { motion } from 'framer-motion';

interface Props {
  status: 'idle' | 'running' | 'completed' | 'failed' | 'stopped';
  label?: string;
}

const colorMap: Record<string, string> = {
  idle: '#26282c',
  running: '#5e6ad2',
  completed: '#3dd68c',
  failed: '#e5484d',
  stopped: '#d9a326',
};

export default function ProgressBar({ status, label }: Props) {
  const fill = status === 'idle' ? 0 : status === 'running' ? 60 : 100;
  const bg = colorMap[status] || colorMap.idle;

  return (
    <div className="progress-container">
      <div className="progress-track">
        <motion.div
          className="progress-fill"
          initial={false}
          animate={{ width: `${fill}%`, backgroundColor: bg }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
      {label && (
        <span className="progress-label" style={{ color: bg }}>
          {label}
        </span>
      )}
    </div>
  );
}
