import { NavLink } from 'react-router-dom';
import {
  LayoutGrid, FileText, KeySquare, Briefcase, MessageSquareText,
  UserRound, Gauge, Play, Bot, Zap, Send, Ban, Globe, Filter, BookOpen, IdCard,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

type Link = { to: string; label: string; icon: LucideIcon };
type Section = { label: string; links: Link[] };

const SECTIONS: Section[] = [
  {
    label: 'Pilotage',
    links: [
      { to: '/', label: "Vue d'ensemble", icon: LayoutGrid },
      { to: '/offers', label: 'Offres', icon: FileText },
      { to: '/applications', label: 'Candidatures', icon: Send },
      { to: '/closed', label: 'Offres fermées', icon: Ban },
      { to: '/run', label: 'Exécution', icon: Play },
      { to: '/chat', label: 'Assistant', icon: Bot },
    ],
  },
  {
    label: 'Configuration',
    links: [
      { to: '/keywords', label: 'Mots-clés', icon: KeySquare },
      { to: '/job-types', label: 'Types de contrat', icon: Briefcase },
      { to: '/scrape-zones', label: 'Zones de scrape', icon: Globe },
      { to: '/prefilter', label: 'Pré-filtre', icon: Filter },
      { to: '/prompts', label: 'Prompts', icon: MessageSquareText },
      { to: '/profile-master', label: 'Mon CV', icon: IdCard },
      { to: '/criteria', label: 'Profil candidat', icon: UserRound },
      { to: '/quotas', label: 'Quotas LLM', icon: Gauge },
    ],
  },
  {
    label: 'Aide',
    links: [
      { to: '/documentation', label: 'Documentation', icon: BookOpen },
    ],
  },
];

export default function Sidebar() {
  return (
    <nav className="sidebar">
      <div className="brand">
        <div className="brand-mark"><Zap size={14} strokeWidth={2.5} /></div>
        <span className="brand-name">Auto Emploi</span>
      </div>
      {SECTIONS.map(section => (
        <div className="nav-section" key={section.label}>
          <div className="nav-section-label">{section.label}</div>
          {section.links.map(l => (
            <NavLink
              key={l.to}
              to={l.to}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              end={l.to === '/'}
            >
              <l.icon size={15} strokeWidth={1.8} />
              {l.label}
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  );
}
