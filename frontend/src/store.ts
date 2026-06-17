import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Decision, IdentityMode } from "./types";

export interface ChatMessage {
  id: string;
  role: "user" | "agent";
  text: string;
  verdict?: Decision | null;
  policyRefs?: string[];
  outcome?: string;
  runId?: string;
  pending?: boolean;
}

interface AppState {
  sessionId: string | null;
  identityMode: IdentityMode;
  customerId: string | null;
  customerName: string | null;
  verified: boolean;
  messages: ChatMessage[];
  setSession: (s: Partial<AppState>) => void;
  resetSession: () => void;
  addMessage: (m: ChatMessage) => void;
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void;
}

export const useApp = create<AppState>()(
  persist(
    (set) => ({
      sessionId: null,
      identityMode: "authenticated",
      customerId: null,
      customerName: null,
      verified: false,
      messages: [],
      setSession: (s) => set((st) => ({ ...st, ...s })),
      resetSession: () =>
        set({ sessionId: null, customerId: null, customerName: null, verified: false, messages: [] }),
      addMessage: (m) => set((st) => ({ messages: [...st.messages, m] })),
      updateMessage: (id, patch) =>
        set((st) => ({ messages: st.messages.map((m) => (m.id === id ? { ...m, ...patch } : m)) })),
    }),
    {
      name: "refund-agent-session",
      partialize: (s) => ({
        sessionId: s.sessionId,
        identityMode: s.identityMode,
        customerId: s.customerId,
        customerName: s.customerName,
        verified: s.verified,
      }),
    },
  ),
);

export const rid = () => Math.random().toString(36).slice(2, 10);
