import { useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Save, Plus, Trash2, UploadCloud, FileText } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import Toast from '../components/Toast';
import { fetchProfileMaster, saveProfileMaster, type ProfileMaster as PM } from '../api/api';

/* ── petits composants réutilisables ── */

function Text({ value, onChange, mono, placeholder }: {
  value: unknown; onChange: (v: string) => void; mono?: boolean; placeholder?: string;
}) {
  return (
    <input
      className={`pm-input${mono ? ' mono' : ''}`}
      value={(value as string) ?? ''}
      placeholder={placeholder}
      onChange={e => onChange(e.target.value)}
    />
  );
}

function Area({ value, onChange, rows }: { value: unknown; onChange: (v: string) => void; rows?: number }) {
  return (
    <textarea
      className="pm-input pm-area"
      rows={rows ?? 3}
      value={(value as string) ?? ''}
      onChange={e => onChange(e.target.value)}
    />
  );
}

type Pair = { fr?: string; en?: string } | undefined;

function Bi({ value, onChange, area, rows }: {
  value: Pair; onChange: (v: { fr: string; en: string }) => void; area?: boolean; rows?: number;
}) {
  const fr = value?.fr ?? '';
  const en = value?.en ?? '';
  const C = area ? Area : Text;
  return (
    <div className="pm-grid">
      <div><span className="pm-sublabel">FR</span><C value={fr} rows={rows} onChange={v => onChange({ fr: v, en })} /></div>
      <div><span className="pm-sublabel">EN</span><C value={en} rows={rows} onChange={v => onChange({ fr, en: v })} /></div>
    </div>
  );
}

function Tags({ value, onChange }: { value: unknown; onChange: (v: string[]) => void }) {
  const arr = Array.isArray(value) ? value : [];
  return (
    <input
      className="pm-input mono"
      value={arr.join(', ')}
      placeholder="tag1, tag2, …"
      onChange={e => onChange(e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
    />
  );
}

function F({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="pm-field">
      <label className="pm-label">{label}{hint && <span className="pm-hint"> · {hint}</span>}</label>
      {children}
    </div>
  );
}

function Section({ title, desc, onAdd, addLabel, children }: {
  title: string; desc?: string; onAdd?: () => void; addLabel?: string; children: ReactNode;
}) {
  return (
    <div className="card">
      <div className="pm-section-head">
        <div>
          <h3>{title}</h3>
          {desc && <p className="field-hint" style={{ marginBottom: 0 }}>{desc}</p>}
        </div>
        {onAdd && (
          <button className="btn btn-secondary btn-sm" onClick={onAdd}>
            <Plus size={13} strokeWidth={2} /> {addLabel ?? 'Ajouter'}
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

function ItemHead({ title, onRemove }: { title: string; onRemove: () => void }) {
  return (
    <div className="pm-item-head">
      <span className="pm-item-title">{title || '—'}</span>
      <button className="pm-remove" onClick={onRemove}><Trash2 size={12} strokeWidth={1.8} /> Supprimer</button>
    </div>
  );
}

/* ── templates ── */
const T = {
  variant: () => ({ id: '', tags: [], fr: '', en: '' }),
  exp: () => ({ id: '', include: 'scored', start: '', org: { fr: '', en: '' }, role: { fr: '', en: '' }, location: { fr: '', en: '' }, dates: { fr: '', en: '' }, tags: [], bullets: [] }),
  bullet: () => ({ id: '', tags: [], fr: '', en: '' }),
  project: () => ({ id: '', name: { fr: '', en: '' }, desc: { fr: '', en: '' }, tech: '', tags: [], bullets: [{ fr: '', en: '' }] }),
  pbullet: () => ({ fr: '', en: '' }),
  edu: () => ({ degree: { fr: '', en: '' }, school: '', location: { fr: '', en: '' }, dates: { fr: '', en: '' } }),
  skill: () => ({ id: '', label: { fr: '', en: '' }, tags: [], content: { fr: '', en: '' } }),
  soft: () => ({ id: '', tags: [], fr: '', en: '' }),
};

export default function ProfileMaster() {
  const [p, setP] = useState<PM | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [toastType, setToastType] = useState<'success' | 'error'>('success');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchProfileMaster().then(d => setP(d.profile)).catch(() => {
      setToastType('error'); setToast('Impossible de charger le profil maître');
    });
  }, []);

  // Mutation immuable : on clone, on modifie, on remplace.
  const set = useCallback((fn: (draft: PM) => void) => {
    setP(prev => {
      if (!prev) return prev;
      const c = structuredClone(prev);
      fn(c);
      return c;
    });
  }, []);

  const onSave = useCallback(async () => {
    if (!p) return;
    setSaving(true);
    try {
      const r = await saveProfileMaster(p);
      if (r.ok) { setToastType('success'); setToast('Profil maître enregistré'); }
      else { setToastType('error'); setToast(r.error || 'Échec de l\'enregistrement'); }
    } catch (e) {
      setToastType('error'); setToast(String(e));
    } finally {
      setSaving(false);
    }
  }, [p]);

  if (!p) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <PageHeader title="Profil maître" description="Les informations qui alimentent vos CV ciblés." />
        <p className="empty-note">Chargement…</p>
      </motion.div>
    );
  }

  const id = p.identity ?? {};

  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
      <PageHeader
        title="Mon CV"
        description="Tout ce qui apparaît sur vos CV générés vient d'ici. Le générateur SÉLECTIONNE les éléments qui collent à chaque offre — il n'invente rien. Renseignez tout en français ET en anglais."
      />
      <Toast message={toast} type={toastType} onDone={() => setToast(null)} />

      <div className="doc-note" style={{ marginBottom: 18, display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <FileText size={16} strokeWidth={1.8} style={{ marginTop: 1, flexShrink: 0 }} />
        <span>
          <strong>C'est votre CV dans l'application.</strong> Perdu(e) avec les champs ou les tags&nbsp;?
          Le guide détaillé est dans la <Link to="/documentation#doc-moncv">documentation « Mon CV »</Link>.
        </span>
      </div>

      {/* Option 2 — à venir */}
      <div className="card">
        <div className="pm-section-head" style={{ marginBottom: 12 }}>
          <div><h3>Importer depuis un CV</h3><p className="field-hint" style={{ marginBottom: 0 }}>Remplissage automatique par IA</p></div>
          <span className="badge badge-amber">À venir</span>
        </div>
        <div className="pm-soon">
          <UploadCloud size={22} strokeWidth={1.5} style={{ marginBottom: 8, opacity: 0.7 }} />
          <div>Bientôt : collez ou déposez votre CV, un LLM remplira les champs ci-dessous automatiquement (les champs manquants resteront vides).</div>
        </div>
      </div>

      {/* Identité */}
      <Section title="Identité">
        <div className="pm-grid">
          <F label="Nom complet"><Text value={id.name} onChange={v => set(d => { d.identity.name = v; })} /></F>
          <F label="E-mail"><Text value={id.email} onChange={v => set(d => { d.identity.email = v; })} /></F>
        </div>
        <div className="pm-grid">
          <F label="Téléphone FR"><Text value={id.phones?.fr} onChange={v => set(d => { d.identity.phones = { ...d.identity.phones, fr: v }; })} /></F>
          <F label="Téléphone CA"><Text value={id.phones?.ca} onChange={v => set(d => { d.identity.phones = { ...d.identity.phones, ca: v }; })} /></F>
        </div>
        <F label="Adresse FR"><Text value={id.addresses?.fr} onChange={v => set(d => { d.identity.addresses = { ...d.identity.addresses, fr: v }; })} /></F>
        <F label="Adresse CA"><Text value={id.addresses?.ca} onChange={v => set(d => { d.identity.addresses = { ...d.identity.addresses, ca: v }; })} /></F>
        <div className="pm-grid">
          <F label="LinkedIn"><Text mono value={id.linkedin} onChange={v => set(d => { d.identity.linkedin = v; })} /></F>
          <F label="GitHub"><Text mono value={id.github} onChange={v => set(d => { d.identity.github = v; })} /></F>
        </div>
        <F label="YouTube"><Text mono value={id.youtube} onChange={v => set(d => { d.identity.youtube = v; })} /></F>
      </Section>

      {/* Profil de base + disponibilité */}
      <Section title="Profil (résumé)" desc="Repli si aucune variante ne correspond ; la disponibilité est toujours ajoutée en fin de profil.">
        <F label="Profil de base"><Bi area rows={4} value={p.profile_base} onChange={v => set(d => { d.profile_base = v; })} /></F>
        <F label="Disponibilité (phrase finale)"><Bi value={p.availability} onChange={v => set(d => { d.availability = v; })} /></F>
      </Section>

      {/* Variantes de profil */}
      <Section title="Variantes de profil" desc="Une variante est choisie selon les tags de l'offre." onAdd={() => set(d => { (d.profile_variants ||= []).push(T.variant()); })} addLabel="Variante">
        {(p.profile_variants ?? []).map((v: PM, i: number) => (
          <div className="pm-item" key={i}>
            <ItemHead title={v.id || `Variante ${i + 1}`} onRemove={() => set(d => { d.profile_variants.splice(i, 1); })} />
            <div className="pm-grid">
              <F label="ID"><Text mono value={v.id} onChange={val => set(d => { d.profile_variants[i].id = val; })} /></F>
              <F label="Tags"><Tags value={v.tags} onChange={val => set(d => { d.profile_variants[i].tags = val; })} /></F>
            </div>
            <F label="Texte"><Bi area rows={3} value={v} onChange={val => set(d => { d.profile_variants[i].fr = val.fr; d.profile_variants[i].en = val.en; })} /></F>
          </div>
        ))}
      </Section>

      {/* Administratif */}
      <Section title="Administratif" desc="Faits stables pour auto-remplir les formulaires (droit au travail, salaire, mobilité…).">
        <F label="Autorisation de travail"><Bi area rows={2} value={p.administrative?.work_authorization} onChange={v => set(d => { (d.administrative ||= {}).work_authorization = v; })} /></F>
        <div className="pm-grid">
          <F label="Prétentions salariales"><Bi value={p.administrative?.salary_expectation} onChange={v => set(d => { (d.administrative ||= {}).salary_expectation = v; })} /></F>
          <F label="Mode de travail"><Bi value={p.administrative?.work_mode} onChange={v => set(d => { (d.administrative ||= {}).work_mode = v; })} /></F>
        </div>
        <F label="Mobilité"><Bi value={p.administrative?.mobility} onChange={v => set(d => { (d.administrative ||= {}).mobility = v; })} /></F>
        <div className="pm-grid">
          <F label="Disponible à partir de"><Bi value={p.administrative?.available_from} onChange={v => set(d => { (d.administrative ||= {}).available_from = v; })} /></F>
          <F label="Permis de conduire"><Text value={p.administrative?.driving_license} onChange={v => set(d => { (d.administrative ||= {}).driving_license = v; })} /></F>
        </div>
      </Section>

      {/* Expériences */}
      <Section title="Expériences" desc="always = toujours · scored = si les tags matchent · never = réserve." onAdd={() => set(d => { (d.experiences ||= []).push(T.exp()); })} addLabel="Expérience">
        {(p.experiences ?? []).map((exp: PM, i: number) => (
          <div className="pm-item" key={i}>
            <ItemHead title={exp.id || exp.org?.fr || `Expérience ${i + 1}`} onRemove={() => set(d => { d.experiences.splice(i, 1); })} />
            <div className="pm-grid">
              <F label="ID"><Text mono value={exp.id} onChange={v => set(d => { d.experiences[i].id = v; })} /></F>
              <F label="Inclusion">
                <select className="pm-input" value={exp.include ?? 'scored'} onChange={e => set(d => { d.experiences[i].include = e.target.value; })}>
                  <option value="always">Toujours</option>
                  <option value="scored">Selon le score</option>
                  <option value="never">Jamais (réserve)</option>
                </select>
              </F>
            </div>
            <div className="pm-grid">
              <F label="Début (tri, AAAA-MM)"><Text mono value={exp.start} onChange={v => set(d => { d.experiences[i].start = v; })} /></F>
              <F label="Tags"><Tags value={exp.tags} onChange={v => set(d => { d.experiences[i].tags = v; })} /></F>
            </div>
            <F label="Organisation"><Bi value={exp.org} onChange={v => set(d => { d.experiences[i].org = v; })} /></F>
            <F label="Poste"><Bi value={exp.role} onChange={v => set(d => { d.experiences[i].role = v; })} /></F>
            <div className="pm-grid">
              <F label="Lieu"><Bi value={exp.location} onChange={v => set(d => { d.experiences[i].location = v; })} /></F>
              <F label="Dates"><Bi value={exp.dates} onChange={v => set(d => { d.experiences[i].dates = v; })} /></F>
            </div>
            <div className="pm-sub">
              <div className="pm-sub-head">
                <span>Réalisations (bullets)</span>
                <button className="pm-add-sm" onClick={() => set(d => { (d.experiences[i].bullets ||= []).push(T.bullet()); })}>+ ajouter</button>
              </div>
              {(exp.bullets ?? []).map((b: PM, j: number) => (
                <div className="pm-bullet" key={j}>
                  <div className="pm-item-head" style={{ marginBottom: 8 }}>
                    <span className="pm-sublabel" style={{ margin: 0 }}>{b.id || `bullet ${j + 1}`}</span>
                    <button className="pm-remove" onClick={() => set(d => { d.experiences[i].bullets.splice(j, 1); })}><Trash2 size={11} strokeWidth={1.8} /></button>
                  </div>
                  <div className="pm-grid">
                    <F label="ID"><Text mono value={b.id} onChange={v => set(d => { d.experiences[i].bullets[j].id = v; })} /></F>
                    <F label="Tags"><Tags value={b.tags} onChange={v => set(d => { d.experiences[i].bullets[j].tags = v; })} /></F>
                  </div>
                  <Bi area rows={2} value={b} onChange={v => set(d => { d.experiences[i].bullets[j].fr = v.fr; d.experiences[i].bullets[j].en = v.en; })} />
                </div>
              ))}
            </div>
          </div>
        ))}
      </Section>

      {/* Projets */}
      <Section title="Projets" desc="Sélectionnés par tags (2 à 3 par CV)." onAdd={() => set(d => { (d.projects ||= []).push(T.project()); })} addLabel="Projet">
        {(p.projects ?? []).map((pr: PM, i: number) => (
          <div className="pm-item" key={i}>
            <ItemHead title={pr.id || (typeof pr.name === 'string' ? pr.name : pr.name?.fr) || `Projet ${i + 1}`} onRemove={() => set(d => { d.projects.splice(i, 1); })} />
            <div className="pm-grid">
              <F label="ID"><Text mono value={pr.id} onChange={v => set(d => { d.projects[i].id = v; })} /></F>
              <F label="Tags"><Tags value={pr.tags} onChange={v => set(d => { d.projects[i].tags = v; })} /></F>
            </div>
            {typeof pr.name === 'string'
              ? <F label="Nom"><Text value={pr.name} onChange={v => set(d => { d.projects[i].name = v; })} /></F>
              : <F label="Nom (FR/EN)"><Bi value={pr.name} onChange={v => set(d => { d.projects[i].name = v; })} /></F>}
            <F label="Description"><Bi value={pr.desc} onChange={v => set(d => { d.projects[i].desc = v; })} /></F>
            <F label="Technologies"><Text value={pr.tech} onChange={v => set(d => { d.projects[i].tech = v; })} /></F>
            <div className="pm-sub">
              <div className="pm-sub-head">
                <span>Description détaillée (bullets)</span>
                <button className="pm-add-sm" onClick={() => set(d => { (d.projects[i].bullets ||= []).push(T.pbullet()); })}>+ ajouter</button>
              </div>
              {(pr.bullets ?? []).map((b: PM, j: number) => (
                <div className="pm-bullet" key={j}>
                  <div className="pm-item-head" style={{ marginBottom: 8 }}>
                    <span className="pm-sublabel" style={{ margin: 0 }}>bullet {j + 1}</span>
                    <button className="pm-remove" onClick={() => set(d => { d.projects[i].bullets.splice(j, 1); })}><Trash2 size={11} strokeWidth={1.8} /></button>
                  </div>
                  <Bi area rows={2} value={b} onChange={v => set(d => { d.projects[i].bullets[j].fr = v.fr; d.projects[i].bullets[j].en = v.en; })} />
                </div>
              ))}
            </div>
          </div>
        ))}
      </Section>

      {/* Formation */}
      <Section title="Formation" onAdd={() => set(d => { (d.education ||= []).push(T.edu()); })} addLabel="Formation">
        {(p.education ?? []).map((ed: PM, i: number) => (
          <div className="pm-item" key={i}>
            <ItemHead title={ed.school || ed.degree?.fr || `Formation ${i + 1}`} onRemove={() => set(d => { d.education.splice(i, 1); })} />
            <F label="Diplôme"><Bi value={ed.degree} onChange={v => set(d => { d.education[i].degree = v; })} /></F>
            <div className="pm-grid">
              <F label="École"><Text value={ed.school} onChange={v => set(d => { d.education[i].school = v; })} /></F>
              <F label="Dates"><Bi value={ed.dates} onChange={v => set(d => { d.education[i].dates = v; })} /></F>
            </div>
            <F label="Lieu"><Bi value={ed.location} onChange={v => set(d => { d.education[i].location = v; })} /></F>
            <label className="pm-check">
              <input type="checkbox" checked={!!ed.optional} onChange={e => set(d => { d.education[i].optional = e.target.checked; })} />
              Optionnel (retiré si la place manque)
            </label>
          </div>
        ))}
      </Section>

      {/* Compétences */}
      <Section title="Compétences" desc="Groupes réordonnés selon l'offre." onAdd={() => set(d => { (d.skills ||= []).push(T.skill()); })} addLabel="Groupe">
        {(p.skills ?? []).map((sk: PM, i: number) => (
          <div className="pm-item" key={i}>
            <ItemHead title={sk.id || sk.label?.fr || `Groupe ${i + 1}`} onRemove={() => set(d => { d.skills.splice(i, 1); })} />
            <div className="pm-grid">
              <F label="ID"><Text mono value={sk.id} onChange={v => set(d => { d.skills[i].id = v; })} /></F>
              <F label="Tags"><Tags value={sk.tags} onChange={v => set(d => { d.skills[i].tags = v; })} /></F>
            </div>
            <F label="Intitulé du groupe"><Bi value={sk.label} onChange={v => set(d => { d.skills[i].label = v; })} /></F>
            <F label="Contenu"><Bi area rows={2} value={sk.content} onChange={v => set(d => { d.skills[i].content = v; })} /></F>
          </div>
        ))}
      </Section>

      {/* Soft skills */}
      <Section title="Soft skills" desc="5 à 6 sélectionnés par offre selon les tags." onAdd={() => set(d => { (d.soft_skills ||= []).push(T.soft()); })} addLabel="Soft skill">
        {(p.soft_skills ?? []).map((ss: PM, i: number) => (
          <div className="pm-item" key={i}>
            <ItemHead title={ss.id || ss.fr || `Soft skill ${i + 1}`} onRemove={() => set(d => { d.soft_skills.splice(i, 1); })} />
            <div className="pm-grid">
              <F label="ID"><Text mono value={ss.id} onChange={v => set(d => { d.soft_skills[i].id = v; })} /></F>
              <F label="Tags"><Tags value={ss.tags} onChange={v => set(d => { d.soft_skills[i].tags = v; })} /></F>
            </div>
            <Bi value={ss} onChange={v => set(d => { d.soft_skills[i].fr = v.fr; d.soft_skills[i].en = v.en; })} />
          </div>
        ))}
      </Section>

      {/* Divers */}
      <Section title="Certifications, langues, centres d'intérêt">
        <F label="Certifications" hint="séparées par des •"><Area rows={2} value={p.certifications} onChange={v => set(d => { d.certifications = v; })} /></F>
        <F label="Langues"><Bi value={p.languages} onChange={v => set(d => { d.languages = v; })} /></F>
        <F label="Centres d'intérêt" hint="affichés selon le pays"><Bi value={p.interests} onChange={v => set(d => { d.interests = v; })} /></F>
      </Section>

      <button className="btn btn-primary" onClick={onSave} disabled={saving}>
        <Save size={14} strokeWidth={1.8} /> {saving ? 'Enregistrement…' : 'Sauvegarder le profil maître'}
      </button>
      <p className="field-hint" style={{ marginTop: 10 }}>
        Une sauvegarde de sécurité (<code className="dc">profile_master.yaml.bak</code>) est créée avant chaque écrasement.
      </p>
    </motion.div>
  );
}
