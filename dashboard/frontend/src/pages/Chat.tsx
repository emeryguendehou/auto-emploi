import { motion } from 'framer-motion';
import PageHeader from '../components/PageHeader';
import ChatPanel from '../components/ChatPanel';

export default function Chat() {
  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Assistant"
        description="Posez des questions sur vos offres et candidatures."
      />
      <div className="card">
        <ChatPanel />
      </div>
    </motion.div>
  );
}
