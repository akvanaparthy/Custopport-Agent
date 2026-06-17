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
  customerEmail: string | null;
  verified: boolean;
  messages: ChatMessage[];
  draft: string | null; // a prompt handed off from the Orders page to the chat
  setSession: (s: Partial<AppState>) => void;
  resetSession: () => void;
  addMessage: (m: ChatMessage) => void;
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void;
  setDraft: (v: string | null) => void;
}

export const useApp = create<AppState>()(
  persist(
    (set) => ({
      sessionId: null,
      identityMode: "authenticated",
      customerId: null,
      customerName: null,
      customerEmail: null,
      verified: false,
      messages: [],
      draft: null,
      setSession: (s) => set((st) => ({ ...st, ...s })),
      resetSession: () =>
        set({ sessionId: null, customerId: null, customerName: null, customerEmail: null, verified: false, messages: [], draft: null }),
      addMessage: (m) => set((st) => ({ messages: [...st.messages, m] })),
      updateMessage: (id, patch) =>
        set((st) => ({ messages: st.messages.map((m) => (m.id === id ? { ...m, ...patch } : m)) })),
      setDraft: (v) => set({ draft: v }),
    }),
    {
      name: "refund-agent-session",
      partialize: (s) => ({
        sessionId: s.sessionId,
        identityMode: s.identityMode,
        customerId: s.customerId,
        customerName: s.customerName,
        customerEmail: s.customerEmail,
        verified: s.verified,
      }),
    },
  ),
);

export const rid = () => Math.random().toString(36).slice(2, 10);
