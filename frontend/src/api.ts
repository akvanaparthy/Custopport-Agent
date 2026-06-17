// The ONLY module that touches the network. Components consume these via hooks.
import type {
  Customer,
  OrderView,
  RunDetail,
  RunSummary,
  Session,
  SettingsView,
} from "./types";

const API_BASE = window.__API_BASE__ || "/api";

async function http<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const authed = (sessionId: string) => ({ "X-Session-Id": sessionId });

// --- sessions / chat ------------------------------------------------------ //

export const getCustomers = () => http<Customer[]>("/customers");

export const createSession = (body: { identity_mode?: string; customer_id?: string }) =>
  http<Session>("/session", { method: "POST", body: JSON.stringify(body) });

export const getSession = (sessionId: string) =>
  http<Session>("/session", { headers: authed(sessionId) });

export const verifySession = (sessionId: string, email: string, order_id: string) =>
  http<Session>("/session/verify", {
    method: "POST",
    headers: authed(sessionId),
    body: JSON.stringify({ email, order_id }),
  });

/** POST /api/chat and parse the coarse SSE status stream. */
export async function streamChat(
  sessionId: string,
  body: { message: string; conversation_id?: string },
  onEvent: (event: string, data: any) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authed(sessionId) },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      let ev = "message";
      let data = "";
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event:")) ev = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (data) {
        try {
          onEvent(ev, JSON.parse(data));
        } catch {
          onEvent(ev, data);
        }
      }
    }
  }
}

// --- admin ---------------------------------------------------------------- //

export const getRuns = () =>
  http<{ runs: RunSummary[]; total: number }>("/admin/runs");

export const getRun = (runId: string) => http<RunDetail>(`/admin/runs/${runId}`);

export const getSettings = () => http<SettingsView>("/admin/settings");

export const putSettings = (patch: Partial<SettingsView>) =>
  http<SettingsView>("/admin/settings", { method: "PUT", body: JSON.stringify(patch) });

export const getOrders = () => http<OrderView[]>("/admin/orders");

export const updateOrderStatus = (orderId: string, status: string) =>
  http<OrderView>(`/admin/orders/${orderId}`, {
    method: "PUT",
    body: JSON.stringify({ status }),
  });

export const resetOrder = (orderId: string) =>
  http<OrderView>(`/admin/orders/${orderId}/reset`, { method: "POST" });

export const resetSeed = () =>
  http<{ ok: boolean; customers: number; orders: number }>("/admin/reset-seed", {
    method: "POST",
  });
