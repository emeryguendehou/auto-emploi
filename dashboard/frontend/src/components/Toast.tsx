import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CircleCheck, CircleAlert } from 'lucide-react';

interface Props {
  message: string | null;
  type?: 'success' | 'error';
  onDone?: () => void;
}

export default function Toast({ message, type = 'success', onDone }: Props) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (message) {
      setVisible(true);
      const t = setTimeout(() => {
        setVisible(false);
        onDone?.();
      }, 2500);
      return () => clearTimeout(t);
    }
  }, [message, onDone]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className={`toast toast-${type}`}
          initial={{ opacity: 0, y: 12, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 12, scale: 0.97 }}
          transition={{ duration: 0.18 }}
        >
          {type === 'success'
            ? <CircleCheck size={16} strokeWidth={2} />
            : <CircleAlert size={16} strokeWidth={2} />}
          {message}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
