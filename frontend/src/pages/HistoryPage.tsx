import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { getTickets } from "../api";
import { useApp } from "../store";
import { VerdictBadge } from "../components/VerdictBadge";

export default function HistoryPage() {
  const { sessionId, verified, customerName } = useApp();
  const tickets = useQuery({
    queryKey: ["tickets", sessionId],
    queryFn: () => getTickets(sessionId!),
    enabled: !!sessionId && verified,
  });

  if (!verified || !sessionId) {
    return (
      <div className="grid place-items-center py-24">
        <div className="glass rounded-3xl p-8 text-center">
          <p className="text-ink-dim">Sign in to view your support history.</p>
          <Link to="/" className="mt-3 inline-block rounded-full bg-ink px-4 py-2 text-sm font-medium text-canvas">
            Go to chat
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="py-6">
      <h1 className="font-display text-2xl font-bold tracking-tight text-ink">Support history</h1>
      <p className="mt-1 text-sm text-ink-dim">{customerName} · saved tickets from your conversations.</p>

      <div className="mt-5 space-y-3">
        {tickets.data?.map((t, i) => (
          <motion.div
            key={t.ticket_id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04 }}
            className="glass rounded-2xl p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="font-mono text-[10px] text-ink-faint">{t.created_at.slice(0, 19).replace("T", " ")}</div>
                <p className="mt-1 text-sm font-medium text-ink">“{t.customer_message}”</p>
              </div>
              {t.verdict ? (
                <VerdictBadge decision={t.verdict} />
              ) : (
                <span className="rounded-full bg-panel-2 px-2 py-0.5 text-xs text-ink-dim">{t.outcome}</span>
              )}
            </div>
            <p className="mt-2 line-clamp-2 text-sm text-ink-dim">{t.agent_reply}</p>
            {t.run_id && (
              <Link
                to={`/admin?run=${t.run_id}`}
                className="mt-2 inline-block font-mono text-[11px] text-ink-faint transition-colors hover:text-signal"
              >
                view reasoning trace →
              </Link>
            )}
          </motion.div>
        ))}
        {tickets.data?.length === 0 && (
          <div className="glass rounded-2xl p-8 text-center text-sm text-ink-faint">
            No tickets yet — your conversations will be saved here.
          </div>
        )}
      </div>
    </div>
  );
}
