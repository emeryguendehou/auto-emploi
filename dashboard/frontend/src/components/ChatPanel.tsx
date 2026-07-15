import { motion } from 'framer-motion';
import { Sparkles, SendHorizonal } from 'lucide-react';

export default function ChatPanel() {
  const mockMessages = [
    { role: 'bot', text: 'Bienvenue ! Ici vous pourrez bientôt poser des questions sur les offres, les candidatures, et bien plus.' },
    { role: 'bot', text: 'Cette fonctionnalité sera disponible dans une prochaine version.' },
  ];

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {mockMessages.map((m, i) => (
          <motion.div
            key={i}
            className={`chat-msg chat-${m.role}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.25 }}
          >
            {m.text}
          </motion.div>
        ))}
      </div>
      <div className="chat-input-bar">
        <input
          type="text"
          placeholder="Bientôt disponible…"
          disabled
          className="chat-input"
        />
        <button className="btn btn-secondary" disabled>
          <SendHorizonal size={14} strokeWidth={1.8} />
          Envoyer
        </button>
      </div>
      <div className="chat-badge">
        <Sparkles size={13} strokeWidth={1.8} />
        Assistant IA — bientôt disponible
      </div>
    </div>
  );
}
