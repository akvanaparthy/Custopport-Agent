import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { createSession, getCustomers, streamChat, verifySession } from "../api";
import { rid, useApp } from "../store";
import type { Customer } from "../types";
import { VerdictBadge } from "../components/VerdictBadge";

export default function ChatPage() {
  const sessionId = useApp((s) => s.sessionId);
  const verified = useApp((s) => s.verified);
  return sessionId && verified ? <Conversation /> : <StartPanel />;
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
      setSession({
        sessionId: s.session_id,
        identityMode: "authenticated",
        customerId: c.customer_id,
        customerName: c.name,
        verified: true,
        messages: [],
      });
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
      setSession({
        sessionId: s.session_id,
        identityMode: "in_chat",
        customerId: s.customer_id,
        customerName: name,
        verified: true,
        messages: [],
      });
    } catch {
      setErr("Verification failed — check the email and order id match an account.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl py-14">
      <div className="animate-rise rounded-2xl border border-line bg-panel/70 p-8 shadow-2xl shadow-black/40">
        <h1 className="font-display text-3xl font-bold tracking-tight text-ink">
          Refund support
        </h1>
        <p className="mt-2 text-sm text-ink-dim">
          The agent gathers the facts; a deterministic policy engine makes the call. Start by
          identifying yourself.
        </p>

        <div className="mt-6 inline-flex rounded-lg border border-line bg-canvas p-1 text-sm">
          {(["authenticated", "in_chat"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded-md px-3 py-1.5 font-medium transition-colors ${
                mode === m ? "bg-signal/15 text-signal" : "text-ink-dim hover:text-ink"
              }`}
            >
              {m === "authenticated" ? "Sign in as customer" : "Verify by email + order"}
            </button>
          ))}
        </div>

        {err && (
          <div className="mt-4 rounded-lg border border-deny/40 bg-deny/10 px-3 py-2 text-sm text-deny">
            {err}
          </div>
        )}

        {mode === "authenticated" ? (
          <div className="mt-5 grid max-h-[44vh] grid-cols-1 gap-2 overflow-auto pr-1 sm:grid-cols-2">
            {customers.isLoading && <div className="text-sm text-ink-faint">Loading customers…</div>}
            {customers.data?.map((c) => (
              <button
                key={c.customer_id}
                disabled={busy}
                onClick={() => pick(c)}
                className="group flex items-center justify-between rounded-lg border border-line bg-canvas px-3 py-2.5 text-left transition-colors hover:border-signal/50 hover:bg-signal/5 disabled:opacity-50"
              >
                <span>
                  <span className="block text-sm font-medium text-ink">{c.name}</span>
                  <span className="block font-mono text-xs text-ink-faint">{c.email}</span>
                </span>
                <span className="font-mono text-xs text-ink-faint group-hover:text-signal">→</span>
              </button>
            ))}
          </div>
        ) : (
          <div className="mt-5 space-y-3">
            <Field label="Email" value={email} onChange={setEmail} placeholder="sarah.chen@example.com" />
            <Field label="Order ID" value={orderId} onChange={setOrderId} placeholder="ord_clean" mono />
            <button
              disabled={busy || !email || !orderId}
              onClick={verify}
              className="w-full rounded-lg bg-signal px-4 py-2.5 text-sm font-semibold text-canvas transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              {busy ? "Verifying…" : "Verify & start"}
            </button>
            <p className="text-xs text-ink-faint">
              Tip: try <span className="font-mono text-ink-dim">sarah.chen@example.com</span> +{" "}
              <span className="font-mono text-ink-dim">ord_clean</span>.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  mono,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  mono?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs uppercase tracking-wider text-ink-faint">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`w-full rounded-lg border border-line bg-canvas px-3 py-2 text-sm text-ink outline-none transition-colors focus:border-signal/60 ${
          mono ? "font-mono" : ""
        }`}
      />
    </label>
  );
}

/* ---- conversation ------------------------------------------------------- */

function Conversation() {
  const { sessionId, customerName, messages, addMessage, updateMessage, resetSession } = useApp();
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const convId = useRef("conv_" + rid());
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || streaming || !sessionId) return;
    setInput("");
    addMessage({ id: rid(), role: "user", text });
    const aid = rid();
    addMessage({ id: aid, role: "agent", text: "", pending: true });
    setStreaming(true);
    try {
      await streamChat(sessionId, { message: text, conversation_id: convId.current }, (ev, data) => {
        if (ev === "verdict") updateMessage(aid, { verdict: data.decision, policyRefs: data.policy_refs });
        else if (ev === "final_message")
          updateMessage(aid, { text: data.message, outcome: data.outcome, runId: data.run_id, pending: false });
      });
    } catch (e: any) {
      updateMessage(aid, { text: `Sorry — something went wrong (${e.message}).`, pending: false, outcome: "ERROR" });
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col py-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm text-ink-dim">
          Chatting as <span className="font-medium text-ink">{customerName}</span>
        </div>
        <button
          onClick={resetSession}
          className="rounded-md border border-line px-2.5 py-1 text-xs text-ink-dim transition-colors hover:border-signal/40 hover:text-ink"
        >
          Switch customer
        </button>
      </div>

      <div className="flex-1 space-y-4 overflow-auto rounded-2xl border border-line bg-panel/40 p-5">
        {messages.length === 0 && (
          <div className="grid h-full place-items-center text-center">
            <div>
              <div className="font-display text-xl text-ink-dim">How can we help with your order?</div>
              <p className="mx-auto mt-2 max-w-sm text-sm text-ink-faint">
                Describe the issue and which item — e.g. “my wireless headphones arrived broken,
                I’d like a refund.”
              </p>
            </div>
          </div>
        )}
        {messages.map((m) => (
          <Bubble key={m.id} m={m} />
        ))}
        <div ref={endRef} />
      </div>

      <div className="mt-3 flex items-end gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          rows={1}
          placeholder="Describe your refund request…"
          className="max-h-40 flex-1 resize-none rounded-xl border border-line bg-canvas px-4 py-3 text-sm text-ink outline-none transition-colors focus:border-signal/60"
        />
        <button
          onClick={send}
          disabled={streaming || !input.trim()}
          className="rounded-xl bg-signal px-5 py-3 text-sm font-semibold text-canvas transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {streaming ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}

function Bubble({ m }: { m: ReturnType<typeof useApp.getState>["messages"][number] }) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] animate-rise rounded-2xl rounded-br-sm bg-signal/15 px-4 py-2.5 text-sm text-ink">
          {m.text}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="max-w-[82%] animate-rise rounded-2xl rounded-bl-sm border border-line bg-panel px-4 py-3 text-sm">
        {(m.verdict || m.outcome === "ESCALATE") && (
          <div className="mb-2 flex items-center gap-2">
            {m.verdict && <VerdictBadge decision={m.verdict} />}
            {m.policyRefs?.map((r) => (
              <span key={r} className="rounded bg-canvas px-1.5 py-0.5 font-mono text-[10px] text-ink-faint">
                {r}
              </span>
            ))}
          </div>
        )}
        {m.pending ? (
          <span className="inline-flex gap-1">
            <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-ink-dim" />
            <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-ink-dim [animation-delay:150ms]" />
            <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-ink-dim [animation-delay:300ms]" />
          </span>
        ) : (
          <div className="whitespace-pre-wrap leading-relaxed text-ink">{m.text}</div>
        )}
        {m.runId && (
          <div className="mt-2.5 border-t border-line pt-2">
            <Link
              to="/admin"
              className="font-mono text-[11px] text-ink-faint transition-colors hover:text-signal"
            >
              view reasoning trace →
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
