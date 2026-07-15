import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import type { SSELogLine } from '../api/useSSE';

interface Props {
  logs: SSELogLine[];
}

export default function TerminalLog({ logs }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs.length]);

  return (
    <div className="log-box">
      {logs.length === 0 && (
        <div className="log-line log-dim">Aucune sortie pour le moment...</div>
      )}
      {logs.map((line, i) => (
        <motion.div
          key={line.id}
          className="log-line"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.15 }}
        >
          {line.text}
        </motion.div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
