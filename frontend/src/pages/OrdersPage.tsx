import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { getMyOrders } from "../api";
import { useApp } from "../store";
import type { CustomerOrder } from "../types";

const TONE: Record<string, { chip: string; dot: string }> = {
  eligible: { chip: "text-approve bg-approve/10 border-approve/25", dot: "bg-approve" },
  review: { chip: "text-escalate bg-escalate/10 border-escalate/25", dot: "bg-escalate" },
  blocked: { chip: "text-deny bg-deny/10 border-deny/25", dot: "bg-deny" },
  refunded: { chip: "text-ink-dim bg-panel-2 border-line", dot: "bg-ink-faint" },
};

const money = (n: number, c = "USD") => `${c === "USD" ? "$" : ""}${n.toFixed(2)}`;

export default function OrdersPage() {
  const { sessionId, verified, customerName, setDraft } = useApp();
  const navigate = useNavigate();
  const [sel, setSel] = useState<CustomerOrder | null>(null);
  const orders = useQuery({
    queryKey: ["my-orders", sessionId],
    queryFn: () => getMyOrders(sessionId!),
    enabled: !!sessionId && verified,
  });

  if (!verified || !sessionId) {
    return (
      <div className="grid place-items-center py-24">
        <div className="glass rounded-3xl p-8 text-center">
          <p className="text-ink-dim">Sign in to view your orders.</p>
          <Link to="/" className="mt-3 inline-block rounded-full bg-ink px-4 py-2 text-sm font-medium text-canvas">
            Go to chat
          </Link>
        </div>
      </div>
    );
  }

  const requestRefund = (o: CustomerOrder) => {
    setDraft(`I'd like a refund for my ${o.item_name} (order ${o.order_id}).`);
    navigate("/");
  };

  return (
    <div className="py-6">
      <h1 className="font-display text-2xl font-bold tracking-tight text-ink">Your orders</h1>
      <p className="mt-1 text-sm text-ink-dim">
        {customerName} · eligibility is a quick preview — the agent makes the real call.
      </p>

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {orders.data?.map((o, i) => {
          const tone = TONE[o.hint.tone] ?? TONE.refunded;
          return (
            <motion.button
              key={o.order_id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              whileHover={{ y: -3 }}
              whileTap={{ scale: 0.99 }}
              onClick={() => setSel(o)}
              className="glass flex flex-col rounded-3xl p-4 text-left"
            >
              <div className="flex items-center justify-between">
                <span className="rounded-full bg-panel-2 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-dim">
                  {o.category}
                </span>
                <span className="font-mono text-[11px] text-ink-faint">{o.status}</span>
              </div>
              <div className="mt-3 font-display text-lg font-semibold leading-tight text-ink">{o.item_name}</div>
              <div className="mt-1 font-mono text-sm text-ink-dim">{money(o.order_total, o.currency)}</div>
              <div className={`mt-3 inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${tone.chip}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
                {o.hint.label}
              </div>
            </motion.button>
          );
        })}
        {orders.isLoading && <div className="text-sm text-ink-faint">Loading…</div>}
      </div>

      <AnimatePresence>
        {sel && <OrderDetail o={sel} onClose={() => setSel(null)} onRefund={requestRefund} />}
      </AnimatePresence>
    </div>
  );
}

function OrderDetail({ o, onClose, onRefund }: { o: CustomerOrder; onClose: () => void; onRefund: (o: CustomerOrder) => void }) {
  const tone = TONE[o.hint.tone] ?? TONE.refunded;
  const canRefund = o.hint.tone === "eligible" || o.hint.tone === "review";
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
      className="fixed inset-0 z-50 grid place-items-center bg-ink/30 p-4 backdrop-blur-sm"
    >
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 12, scale: 0.98 }}
        transition={{ type: "spring", stiffness: 320, damping: 30 }}
        onClick={(e) => e.stopPropagation()}
        className="glass w-full max-w-md rounded-3xl p-6"
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="font-mono text-[11px] text-ink-faint">{o.order_id}</div>
            <h2 className="mt-1 font-display text-xl font-bold text-ink">{o.item_name}</h2>
          </div>
          <button onClick={onClose} className="rounded-full p-1 text-ink-faint hover:text-ink">✕</button>
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <Detail k="Category" v={o.category} />
          <Detail k="Total" v={money(o.order_total, o.currency)} />
          <Detail k="Status" v={o.status} />
          <Detail k="Condition" v={o.item_condition} />
          <Detail k="Delivered" v={o.delivered_date ?? "—"} />
          <Detail k="Final sale" v={o.is_final_sale ? "yes" : "no"} />
        </dl>

        <div className={`mt-4 flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium ${tone.chip}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
          {o.hint.label}
        </div>

        {canRefund ? (
          <button
            onClick={() => onRefund(o)}
            className="mt-5 w-full rounded-2xl bg-lime px-4 py-3 text-sm font-semibold text-ink shadow-sm transition-opacity hover:opacity-90"
          >
            Request a refund →
          </button>
        ) : (
          <p className="mt-5 text-center text-xs text-ink-faint">
            {o.already_refunded ? "This order has already been refunded." : "This order isn't eligible for a refund."}
          </p>
        )}
      </motion.div>
    </motion.div>
  );
}

function Detail({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wider text-ink-faint">{k}</dt>
      <dd className="mt-0.5 text-ink">{v}</dd>
    </div>
  );
}
