const BASE = (import.meta as any).env?.VITE_API_BASE || "";
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

export async function fetchEvents(daysBack: number): Promise<{ events: EventRow[]; days_back: number; count: number }> {
  const resp = await request(`/api/events?days_back=${encodeURIComponent(daysBack)}`);
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

// <img> can't carry an Authorization header, so fetch the bytes with auth and hand back an
// object URL. Callers should revoke it when the element unmounts.
export async function fetchMediaObjectUrl(path: string): Promise<string> {
  const resp = await request(path);
  if (!resp.ok) throw new Error(`media ${resp.status}`);
  const blob = await resp.blob();
  return URL.createObjectURL(blob);
}
