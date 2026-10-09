// API origin: build-time VITE_API_BASE by default. On localhost only, a ?api=<origin> query
// param overrides it — used by the Playwright acceptance suite to point one dev server at
// either the "full" or "empty" fixture backend. Never honoured off localhost.
function resolveBase(): string {
  const buildBase = (import.meta as any).env?.VITE_API_BASE || "";
  try {
    const host = location.hostname;
    if (host === "localhost" || host === "127.0.0.1") {
      const override = new URLSearchParams(location.search).get("api");
      if (override) return override;
    }
  } catch {
    /* non-browser */
  }
  return buildBase;
}
const BASE = resolveBase();
const TOKEN_KEY = "denidin_ledger_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}
export function setToken(t: string) {
  try {
    localStorage.setItem(TOKEN_KEY, t);
  } catch {
    /* private mode — session lives only in memory for this tab */
  }
}
export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export class AuthError extends Error {}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = { ...(init.headers as any) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(`${BASE}${path}`, { ...init, headers });
  if (resp.status === 401) {
    clearToken();
    throw new AuthError("session expired");
  }
  return resp;
}

export async function login(password: string): Promise<{ ok: boolean; error?: string }> {
  const resp = await fetch(`${BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (resp.ok) {
    const body = await resp.json();
    setToken(body.token);
    return { ok: true };
  }
  const body = await resp.json().catch(() => ({}));
  return { ok: false, error: body.error || "login_failed" };
}

export async function logout() {
  try {
    await request("/api/auth/logout", { method: "POST" });
  } catch {
    /* ignore */
  }
  clearToken();
}

export interface EventRow {
  event_id: string;
  date: string | null;
  source_type: string | null;
  event_subtype: string | null;
  client_name: string | null;
  amount: number | null;
  description: string | null;
  search_blob?: string; // full-record lowercased text, for the free-text filter
}

// refresh=true is a hard reload: the backend re-reads event files and drops its cached
// conversations. Without it the backend answers from memory.
export async function fetchEvents(
  daysBack: number,
  refresh = false
): Promise<{ events: EventRow[]; days_back: number; count: number }> {
  const resp = await request(
    `/api/events?days_back=${encodeURIComponent(daysBack)}${refresh ? "&refresh=1" : ""}`
  );
  return resp.json();
}

export async function fetchEventDetail(id: string): Promise<Record<string, any>> {
  const resp = await request(`/api/events/${encodeURIComponent(id)}`);
  return resp.json();
}

export interface ContextMessage {
  message_id: string;
  role: string;
  side: "left" | "right";
  content: string;
  timestamp: string | null;
  sender_name: string | null;
  media_url?: string;
}
export async function fetchContext(
  id: string,
  lookbackMinutes: number
): Promise<{ messages?: ContextMessage[]; error?: string; message?: string; lookback_minutes_used?: number }> {
  const resp = await request(
    `/api/events/${encodeURIComponent(id)}/context?lookback_minutes=${encodeURIComponent(lookbackMinutes)}`
  );
  return resp.json();
}

export async function searchClients(prefix: string): Promise<string[]> {
  if (prefix.trim().length < 2) return [];
  const resp = await request(`/api/clients/search?prefix=${encodeURIComponent(prefix)}`);
  const body = await resp.json();
  return body.clients || [];
}

export interface ClientEvent {
  date: string;
  amount: number;
  type: string;
  subtype: string;
  desc: string;
}
export interface ClientRow {
  official_name: string;
  raw_names: string[];
  agreements_total: number;
  deposits_total: number;
  invoices_net: number;
  manual_agreement_amount: number | null;
  agreed_status: "WHITE" | "YELLOW" | "GRAY";
  paid_status: "WHITE" | "YELLOW" | "GRAY";
  display_agreed: number;
  display_paid: number;
  status: "active" | "settled" | "debt" | "missing_agreement" | "check" | "past";
  is_manually_settled: boolean;
  latest_activity: string | null;
  comment: string;
  events: ClientEvent[];
  // Feature 092: the persisted line status (null = routed by the numbers), and the subset of
  // raw_names that are explicit mappings of this client (the only ones that can be unlinked).
  line_status: "closed" | "check" | "active" | null;
  mapped_aliases: string[];
}
export type LineAction = "close" | "reopen" | "check" | "active";
export interface SuggestedMatch {
  name: string;
  reasons: string[];
}
export interface UnmatchedEntry {
  raw_name: string;
  suggested_matches: SuggestedMatch[];
  event_count: number;
  raw_text: string[];
  note: string;
}
// refresh=true re-fetches Morning's client list and recomputes; otherwise served from memory.
export async function fetchClients(
  refresh = false
): Promise<{ clients: ClientRow[]; unmatched: UnmatchedEntry[] }> {
  const resp = await request(refresh ? "/api/clients?refresh=1" : "/api/clients");
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.message || "clients_fetch_failed");
  }
  return resp.json();
}
export async function saveClientComment(clientId: string, comment: string): Promise<void> {
  await request(`/api/clients/${encodeURIComponent(clientId)}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ comment }),
  });
}
export async function saveClientMapping(
  rawName: string,
  officialName?: string,
  note?: string
): Promise<void> {
  const body: Record<string, string> = { raw_name: rawName };
  if (officialName !== undefined) body.official_name = officialName;
  if (note !== undefined) body.note = note;
  await request("/api/clients/mapping", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function postJson(path: string, body: Record<string, unknown>): Promise<any> {
  const resp = await request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.message || `request_failed_${resp.status}`);
  return data;
}
// Feature 092: the לסגור / לפתוח / לבדוק / לקוח פעיל line buttons.
export async function setClientLineStatus(clientId: string, action: LineAction): Promise<void> {
  await postJson(`/api/clients/${encodeURIComponent(clientId)}/status`, { action });
}
// Feature 092: undo an explicit name mapping; the name returns to the resolve list.
export async function unlinkClientMapping(rawName: string): Promise<void> {
  await postJson("/api/clients/mapping/unlink", { raw_name: rawName });
}
// Feature 092: "הסר מהרשימה" - permanently drop a name from the resolve list.
export async function hideUnmatched(rawName: string): Promise<void> {
  await postJson("/api/clients/unmatched/hide", { raw_name: rawName });
}

// <img> can't carry an Authorization header, so fetch the bytes with auth and hand back an
// object URL. Callers should revoke it when the element unmounts.
export async function fetchMediaObjectUrl(path: string): Promise<string> {
  const resp = await request(path);
  if (!resp.ok) throw new Error(`media ${resp.status}`);
  const blob = await resp.blob();
  return URL.createObjectURL(blob);
}

// ---- Feature 089: Agreements (proxied by the webapp backend to denidin-app's Agreements API) ----
export type ComponentStatus = "Pending" | "Active" | "Completed" | "Cancelled";
export type AgreementStatus = "Active" | "Completed" | "Cancelled";
export interface AgreementComponent {
  component_key: string;
  component_id: string;
  label: string;
  description: string | null;
  amount: number | null;
  percent: number | null;
  percent_base: string | null;
  trigger_condition: string | null;
  vat_status: string | null;
  txn_date: string | null;
  status: ComponentStatus;
  locked: boolean;
}
export interface Agreement {
  agreement_id: string;
  client_name: string;
  title: string;
  payer_name: string | null;
  partner_name: string | null;
  partner_percent: number | null;
  status: AgreementStatus;
  components: AgreementComponent[];
}
export interface AgreementRevision {
  revision_id: number;
  created_at: string;
  actor: "webapp" | "whatsapp";
  action: string;
  component_key: string | null;
  snapshot: Record<string, any>;
  changed: Record<string, any>;
}
export class AgreementsApiError extends Error {
  code: string;
  fields: Record<string, string>;
  constructor(code: string, message: string, fields: Record<string, string> = {}) {
    super(message);
    this.code = code;
    this.fields = fields;
  }
}

async function agreementsCall(method: string, path: string, body?: Record<string, unknown>): Promise<any> {
  const resp = await request(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const err = data.error || {};
    throw new AgreementsApiError(err.code || `request_failed_${resp.status}`, err.message || "הפעולה נכשלה.", err.fields || {});
  }
  return data;
}

export async function fetchClientAgreements(clientId: string): Promise<Agreement[]> {
  return (await agreementsCall("GET", `/api/clients/${encodeURIComponent(clientId)}/agreements`)).agreements;
}
export async function fetchAgreementRevisions(agreementId: string): Promise<AgreementRevision[]> {
  return (await agreementsCall("GET", `/api/agreements/${encodeURIComponent(agreementId)}/revisions`)).revisions;
}
export async function createAgreement(body: Record<string, unknown>): Promise<Agreement> {
  return (await agreementsCall("POST", "/api/agreements", body)).agreement;
}
export async function editAgreement(agreementId: string, fields: Record<string, unknown>): Promise<Agreement> {
  return (await agreementsCall("PATCH", `/api/agreements/${encodeURIComponent(agreementId)}`, fields)).agreement;
}
export async function setAgreementStatus(agreementId: string, action: "complete" | "cancel" | "reopen"): Promise<Agreement> {
  return (await agreementsCall("POST", `/api/agreements/${encodeURIComponent(agreementId)}/status`, { action })).agreement;
}
export async function addComponent(agreementId: string, fields: Record<string, unknown>): Promise<Agreement> {
  return (await agreementsCall("POST", `/api/agreements/${encodeURIComponent(agreementId)}/components`, fields)).agreement;
}
export async function editComponent(agreementId: string, key: string, fields: Record<string, unknown>): Promise<Agreement> {
  return (await agreementsCall("PATCH", `/api/agreements/${encodeURIComponent(agreementId)}/components/${encodeURIComponent(key)}`, fields)).agreement;
}
export async function setComponentStatus(
  agreementId: string, key: string, action: "activate" | "complete" | "cancel" | "reopen"
): Promise<Agreement> {
  return (await agreementsCall("POST", `/api/agreements/${encodeURIComponent(agreementId)}/components/${encodeURIComponent(key)}/status`, { action })).agreement;
}
export async function deleteComponent(agreementId: string, key: string): Promise<Agreement> {
  return (await agreementsCall("DELETE", `/api/agreements/${encodeURIComponent(agreementId)}/components/${encodeURIComponent(key)}`)).agreement;
}
