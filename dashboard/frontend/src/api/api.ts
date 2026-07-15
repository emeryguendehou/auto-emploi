const BASE = '/api';

export interface Stats {
  total: number;
  excluded: number;
  prioritaires: number;
  a_etudier: number;
  ignores: number;
  postule: number;
  closed: number;
  in_notion: number;
  unprocessed: number;
}

export interface QuotaProvider {
  model: string;
  daily_limit: number;
  tpm_limit?: number;
  delay_seconds: number;
  pause_every?: number;
  pause_duration?: number;
  api_key_env?: string;
}

export interface QuotaUsage {
  used: number;
  success: number;
  fail: number;
}

export interface QuotasData {
  quotas: Record<string, QuotaProvider>;
  today_usage: Record<string, QuotaUsage>;
}

export interface RunState {
  phase: string | null;
  started_at: string | null;
  status: 'idle' | 'running' | 'completed' | 'failed' | 'stopped';
  logs: string[];
}

export interface Offer {
  id: string;
  cv_genere: boolean;
  titre: string;
  entreprise: string;
  localisation: string;
  source: string;
  type_contrat: string;
  categorie: string;
  orientation: string;
  score: number | null;
  score_global: number | null;
  salaire: string;
  statut: string;
  lien: string;
  in_notion: boolean;
  postule: boolean;
  date_postule: string;
  closed: boolean;
  date_closed: string;
  resume_ia: string;
  raisons_score: string;
  tags: string[];
  note_remuneration: number | null;
  note_entreprise: number | null;
  note_flexibilite: number | null;
  note_evolution: number | null;
}

export interface OffersData {
  offers: Offer[];
  total: number;
}

async function jsonGet<T>(url: string): Promise<T> {
  const res = await fetch(BASE + url);
  if (!res.ok) throw new Error(`GET ${url} failed: ${res.status}`);
  return res.json();
}

async function jsonPost(url: string, body?: Record<string, unknown> | FormData): Promise<unknown> {
  const opts: RequestInit = { method: 'POST' };
  if (body instanceof FormData) {
    opts.body = body;
  } else if (body) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(BASE + url, opts);
  if (!res.ok) throw new Error(`POST ${url} failed: ${res.status}`);
  return res.json();
}

export async function fetchStats(): Promise<Stats> {
  return jsonGet<Stats>('/stats');
}

export async function fetchOffers(): Promise<OffersData> {
  return jsonGet<OffersData>('/offers');
}

export async function fetchQuotas(): Promise<QuotasData> {
  return jsonGet<QuotasData>('/quotas');
}

export async function fetchKeywords(): Promise<{ keywords: string[]; wttj_keywords: string[]; exclusion: string[]; title_exclusion: string[] }> {
  return jsonGet('/keywords');
}

export async function fetchJobTypes(): Promise<{ job_types: string[]; preview: { linkedin: string; wttj: string; indeed: string } }> {
  return jsonGet('/job-types');
}

export async function fetchPrompts(): Promise<{ system_prompt: string; score_prompt: string }> {
  return jsonGet('/prompts');
}

export async function fetchCriteria(): Promise<{ content: string }> {
  return jsonGet('/criteria');
}

export async function fetchRunStatus(): Promise<RunState> {
  return jsonGet<RunState>('/run/status');
}

export function saveKeywords(keywords: string[], wttj: string[], exclusion: string[], titleExclusion: string[]) {
  return jsonPost('/keywords/save', { keywords, wttj_keywords: wttj, exclusion, title_exclusion: titleExclusion });
}

export function saveJobTypes(types: string[]) {
  return jsonPost('/job-types/save', { types });
}

export interface ScrapeZone {
  label: string;
  enabled: boolean;
  remote_only: boolean;
  indeed: boolean;
}

export async function fetchScrapeZones(): Promise<{ zones: ScrapeZone[] }> {
  return jsonGet('/scrape-zones');
}

export function saveScrapeZones(zones: Record<string, boolean>) {
  return jsonPost('/scrape-zones/save', { zones });
}

export interface Prefilter {
  enabled: boolean;
  max_exp_years: number;
  foreign_require_global_remote: boolean;
  contract_terms: string[];
  global_remote_terms: string[];
}

export async function fetchPrefilter(): Promise<Prefilter> {
  return jsonGet<Prefilter>('/prefilter');
}

export function savePrefilter(p: Partial<Prefilter>) {
  return jsonPost('/prefilter/save', p as Record<string, unknown>);
}

export function setOfferScore(
  id: string, score: number,
  notes?: { remuneration?: number; entreprise?: number; flexibilite?: number; evolution?: number },
): Promise<{ ok: boolean; score: number; score_global: number }> {
  return jsonPost('/offers/score', { id, score, notes }) as Promise<{ ok: boolean; score: number; score_global: number }>;
}

export function savePrompts(system: string, score: string) {
  return jsonPost('/prompts/save', { system_prompt: system, score_prompt: score });
}

export function saveCriteria(content: string) {
  return jsonPost('/criteria/save', { content });
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ProfileMaster = Record<string, any>;

export function fetchProfileMaster(): Promise<{ profile: ProfileMaster }> {
  return jsonGet('/profile-master');
}

export function saveProfileMaster(profile: ProfileMaster) {
  return jsonPost('/profile-master/save', { profile }) as Promise<{ ok: boolean; error?: string }>;
}

export function saveQuotas(form: Record<string, unknown>) {
  return jsonPost('/quotas/save', form);
}

export function resetQuotas() {
  return jsonPost('/quotas/reset');
}

export function startPhase(phase: string) {
  return jsonPost(`/run/${phase}`);
}

export function stopRun() {
  return jsonPost('/run/stop');
}

export function generateCv(id: string): Promise<{ ok: boolean; cv: string; lm: string }> {
  return jsonPost('/generate-cv', { id }) as Promise<{ ok: boolean; cv: string; lm: string }>;
}

export function setPostule(id: string, value: boolean) {
  return jsonPost('/offers/postule', { id, value });
}

export function setClosed(id: string, value: boolean) {
  return jsonPost('/offers/closed', { id, value });
}

export function cvUrl(id: string): string {
  return `${BASE}/cv/${encodeURIComponent(id)}`;
}
