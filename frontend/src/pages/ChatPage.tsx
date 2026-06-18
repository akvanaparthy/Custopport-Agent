import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { createSession, getCustomers, streamChat, verifySession } from "../api";
import { rid, useApp, type ChatMessage } from "../store";
import type { Customer } from "../types";
import { VerdictBadge } from "../components/VerdictBadge";

const PROMPTS = [
  "My item arrived broken — I'd like a refund.",
  "Is my recent order eligible for a refund?",
  "I received the wrong item.",
  "I changed my mind — can I return it?",
];

export default function ChatPage() {
  const sessionId = useApp((s) => s.sessionId);
  const verified = useApp((s) => s.verified);
  return sessionId && verified ? <Conversation /> : <StartPanel />;
}

/* ---- orb ---------------------------------------------------------------- */

function Orb({ size = 88 }: { size?: number }) {
  return (
    <div className="relative animate-orb" style={{ width: size, height: size }}>
      <div
        className="absolute inset-0 rounded-full blur-md"
        style={{ background: "conic-gradient(from 210deg, #c2f000, #34d399, #2dd4bf, #c2f000)" }}
      />
      <div
        className="absolute inset-[3px] rounded-full"
        style={{ background: "radial-gradient(circle at 32% 28%, #f0ffb0, #9be870 35%, #0f9d6b 90%)" }}
      />
      <div className="absolute inset-0 animate-spin-slow rounded-full border border-white/40" />
    </div>
  );
}

/* ---- start / identity --------------------------------------------------- */

function StartPanel() {
  const setSession = useApp((s) => s.setSession);
  const [mode, setMode] = useState<"authenticated" | "in_chat">("authenticated");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [orderId, setOrderId] = useState("");
  const customers = useQuery({ queryKey: ["customers"], queryFn: getCustomers });

  const pick = async (c: Customer) => {
    setBusy(true);
    setErr(null);
    try {
      const s = await createSession({ customer_id: c.customer_id });
      setSession({ sessionId: s.session_id, identityMode: "authenticated", customerId: c.customer_id, customerName: c.name, customerEmail: c.email, verified: true, messages: [] });
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    setBusy(true);
    setErr(null);
    try {
      const created = await createSession({ identity_mode: "in_chat" });
      const s = await verifySession(created.session_id, email, orderId);
      const name = customers.data?.find((c) => c.customer_id === s.customer_id)?.name ?? s.customer_id ?? "";
      setSession({ sessionId: s.session_id, identityMode: "in_chat", customerId: s.customer_id, customerName: name, customerEmail: email, verified: true, messages: [] });
    } catch {
      setErr("Verification failed — the email and order id must match an account.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl py-12">
      <motion.div
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.2, 0.7, 0.2, 1] }}
        className="glass rounded-[28px] p-8"
      >
        <div className="flex items-center gap-4">
          <Orb size={56} />
          <div>
            <h1 className="font-display text-3xl font-bold tracking-tight text-ink">Refund support</h1>
            <p className="mt-1 text-sm text-ink-dim">Tell us what's wrong — a policy engine makes the call, fairly.</p>
          </div>
        </div>

        <div className="mt-6 inline-flex rounded-full border border-line bg-canvas/70 p-1 text-sm">
          {(["authenticated", "in_chat"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-full px-4 py-1.5 font-medium transition-colors ${
                mode === m ? "bg-ink text-canvas" : "text-ink-dim hover:text-ink"
              }`}
            >
              {m === "authenticated" ? "Sign in" : "Verify by order"}
            </button>
          ))}
        </div>

        {err && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 rounded-xl border border-deny/30 bg-deny/5 px-3 py-2 text-sm text-deny">
            {err}
          </motion.div>
        )}

        {mode === "authenticated" ? (
          <div className="mt-5 grid max-h-[42vh] grid-cols-1 gap-2 overflow-auto pr-1 sm:grid-cols-2">
            {customers.isLoading && <div className="text-sm text-ink-faint">Loading…</div>}
            {customers.data?.map((c, i) => (
              <motion.button
                key={c.customer_id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.025 }}
                whileHover={{ y: -2 }}
                whileTap={{ scale: 0.98 }}
                disabled={busy}
                onClick={() => pick(c)}
                className="flex items-center gap-3 rounded-2xl border border-line bg-panel px-3 py-2.5 text-left shadow-sm transition-colors hover:border-signal/40 disabled:opacity-50"
              >
                <span className="grid h-8 w-8 place-items-center rounded-full bg-lime-soft text-xs font-semibold text-signal">
                  {c.name.charAt(0)}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-ink">{c.name}</span>
                  <span className="block truncate font-mono text-[11px] text-ink-faint">{c.email}</span>
                </span>
              </motion.button>
            ))}
          </div>
        ) : (
          <div className="mt-5 space-y-3">
            <Field label="Email" value={email} onChange={setEmail} placeholder="sarah.chen@example.com" />
            <Field label="Order ID" value={orderId} onChange={setOrderId} placeholder="ord_clean" mono />
            <motion.button
              whileTap={{ scale: 0.98 }}
              disabled={busy || !email || !orderId}
              onClick={verify}
              className="w-full rounded-2xl bg-lime px-4 py-3 text-sm font-semibold text-ink shadow-sm transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              {busy ? "Verifying…" : "Verify & start"}
            </motion.button>
            <p className="text-xs text-ink-faint">
              Try <span className="font-mono text-ink-dim">sarah.chen@example.com</span> +{" "}
              <span className="font-mono text-ink-dim">ord_clean</span>.
            </p>
          </div>
        )}
      </motion.div>
    </div>
  );
}

function Field({ label, value, onChange, placeholder, mono }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; mono?: boolean }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs uppercase tracking-wider text-ink-faint">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`w-full rounded-xl border border-line bg-panel px-3 py-2.5 text-sm text-ink shadow-sm outline-none transition-colors focus:border-signal/60 ${mono ? "font-mono" : ""}`}
      />
    </label>
  );
}

/* ---- conversation ------------------------------------------------------- */

function Conversation() {
  const { sessionId, messages, addMessage, updateMessage, draft, setDraft } = useApp();
  const setSession = useApp((s) => s.setSession);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [resolved, setResolved] = useState(false); // closed after a settled (approve) or escalated request
  const convId = useRef("conv_" + rid());
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // a prompt handed off from the Orders page
  useEffect(() => {
    if (draft) {
      setInput(draft);
      setDraft(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sendText = async (text: string) => {
    if (!text.trim() || streaming || !sessionId || resolved) return;
    setInput("");
    addMessage({ id: rid(), role: "user", text });
    let aid = rid();
    addMessage({ id: aid, role: "agent", text: "", pending: true });
    setStreaming(true);
    try {
      await streamChat(sessionId, { message: text, conversation_id: convId.current }, (ev, data) => {
        if (ev === "assistant_note") {
          // the agent's "let me check…" preamble: settle this bubble, open a fresh one for the answer
          updateMessage(aid, { text: data.message, pending: false });
          aid = rid();
          addMessage({ id: aid, role: "agent", text: "", pending: true });
        } else if (ev === "verdict") {
          updateMessage(aid, { verdict: data.decision, policyRefs: data.policy_refs });
        } else if (ev === "final_message") {
          updateMessage(aid, { text: data.message, outcome: data.outcome, runId: data.run_id, pending: false });
          // a settled refund (approved) or a hand-off to a human (escalated) closes the
          // request; a denial stays open so the customer can add context
          if (data.outcome === "APPROVE" || data.outcome === "ESCALATE") setResolved(true);
        } else if (ev === "error") {
          updateMessage(aid, {
            text: data?.message || "Something went wrong on our end. Please try again.",
            pending: false,
            outcome: "ERROR",
          });
        }
      });
    } catch (e: any) {
      updateMessage(aid, { text: `Sorry — something went wrong (${e.message}).`, pending: false, outcome: "ERROR" });
    } finally {
      setStreaming(false);
    }
  };

  const newChat = () => {
    convId.current = "conv_" + rid();
    setResolved(false);
    setSession({ messages: [] });
  };

  const empty = messages.length === 0;

  return (
    <div className="flex h-[calc(100vh-3.75rem)] flex-col py-5">
      <div className="mb-3 flex items-center justify-end">
        {!empty && (
          <button onClick={newChat} className="rounded-full border border-line bg-panel/70 px-3 py-1 text-xs text-ink-dim shadow-sm backdrop-blur transition-colors hover:text-ink">
            + New chat
          </button>
        )}
      </div>

      <div className="flex-1 overflow-auto">
        {empty ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <Orb />
            <motion.h2
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="mt-6 font-display text-[28px] font-bold tracking-tight text-ink"
            >
              How can we help with your order?
            </motion.h2>
            <p className="mt-2 max-w-md text-sm text-ink-dim">
              Describe the issue and the item. I'll check it against the policy and either process, decline, or escalate it.
            </p>
            <div className="mt-7 grid w-full max-w-xl grid-cols-1 gap-2.5 sm:grid-cols-2">
              {PROMPTS.map((p, i) => (
                <motion.button
                  key={p}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.15 + i * 0.06 }}
                  whileHover={{ y: -2 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => sendText(p)}
                  className="glass rounded-2xl px-4 py-3 text-left text-sm text-ink transition-colors hover:border-signal/40"
                >
                  {p}
                </motion.button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-4 px-1">
            <AnimatePresence initial={false}>
              {messages.map((m) => (
                <Bubble key={m.id} m={m} />
              ))}
            </AnimatePresence>
            <div ref={endRef} />
          </div>
        )}
      </div>

      <div className="mx-auto mt-4 w-full max-w-3xl">
        {resolved ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass flex items-center justify-between gap-3 rounded-[22px] px-4 py-3"
          >
            <span className="text-sm text-ink-dim">This request has been resolved. Start a new chat for anything else.</span>
            <button
              onClick={newChat}
              className="shrink-0 rounded-full bg-ink px-4 py-1.5 text-xs font-medium text-lime shadow-sm transition-opacity hover:opacity-90"
            >
              New chat
            </button>
          </motion.div>
        ) : (
          <div className="glass flex items-end gap-2 rounded-[22px] p-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendText(input);
                }
              }}
              rows={1}
              placeholder="Describe your refund request…"
              className="max-h-40 flex-1 resize-none bg-transparent px-3 py-2.5 text-sm text-ink outline-none placeholder:text-ink-faint"
            />
            <motion.button
              whileTap={{ scale: 0.9 }}
              onClick={() => sendText(input)}
              disabled={streaming || !input.trim()}
              className="grid h-10 w-10 place-items-center rounded-full bg-ink text-lime transition-opacity hover:opacity-90 disabled:opacity-30"
              aria-label="Send"
            >
              {streaming ? <span className="h-2 w-2 animate-pulse-dot rounded-full bg-lime" /> : "↑"}
            </motion.button>
          </div>
        )}
        <p className="mt-2 text-center text-[11px] text-ink-faint">
          The agent gathers facts; a deterministic policy engine makes the final call.
        </p>
      </div>
    </div>
  );
}

function Bubble({ m }: { m: ChatMessage }) {
  if (m.role === "user") {
    return (
      <motion.div layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex justify-end">
        <div className="max-w-[78%] rounded-[20px] rounded-br-md bg-ink px-4 py-2.5 text-sm text-canvas">{m.text}</div>
      </motion.div>
    );
  }
  return (
    <motion.div layout initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex justify-start">
      <div className="glass max-w-[82%] rounded-[20px] rounded-bl-md px-4 py-3 text-sm">
        {(m.verdict || m.outcome === "ESCALATE") && (
          <div className="mb-2 flex flex-wrap items-center gap-2">
            {m.verdict && <VerdictBadge decision={m.verdict} />}
            {m.policyRefs?.map((r) => (
              <span key={r} className="rounded-md bg-canvas px-1.5 py-0.5 font-mono text-[10px] text-ink-faint">
                {r}
              </span>
            ))}
          </div>
        )}
        {m.pending ? (
          <span className="inline-flex gap-1 py-1">
            <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-signal" />
            <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-signal [animation-delay:150ms]" />
            <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-signal [animation-delay:300ms]" />
          </span>
        ) : (
          <div className="whitespace-pre-wrap leading-relaxed text-ink">{m.text}</div>
        )}
        {m.runId && (
          <div className="mt-2.5 border-t border-line pt-2">
            <Link to={`/admin?run=${m.runId}`} className="font-mono text-[11px] text-ink-faint transition-colors hover:text-signal">
              view reasoning trace →
            </Link>
          </div>
        )}
      </div>
    </motion.div>
  );
}
