import { useState } from 'react';
import { Sun, Moon } from 'lucide-react';
import { currentTheme, applyTheme } from '../theme';

export default function ThemeToggle() {
  const [theme, setTheme] = useState(currentTheme());
  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    setTheme(next);
  };

  return (
    <button
      className="theme-fab"
      onClick={toggle}
      aria-label={theme === 'dark' ? 'Passer en mode clair' : 'Passer en mode sombre'}
      title={theme === 'dark' ? 'Mode clair' : 'Mode sombre'}
    >
      {theme === 'dark'
        ? <Sun size={16} strokeWidth={1.9} />
        : <Moon size={16} strokeWidth={1.9} />}
    </button>
  );
}
