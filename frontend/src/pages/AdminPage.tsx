import { useQuery } from "@tanstack/react-query";
import { getRuns } from "../api";
import { VerdictBadge } from "../components/VerdictBadge";

export default function AdminPage() {
  const runs = useQuery({ queryKey: ["runs"], queryFn: getRuns, refetchInterval: 4000 });

  return (
    <div className="py-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink">Operator console</h1>
          <p className="mt-1 text-sm text-ink-dim">
            Runs &amp; Traces · Settings · Data — per-step trace drill-in and the Settings/Data tabs land next.
          </p>
        </div>
        <span className="font-mono text-xs text-ink-faint">
          {runs.data ? `${runs.data.total} run(s)` : "…"}
        </span>
      </div>

      <div className="mt-5 overflow-hidden rounded-xl border border-line">
        <table className="w-full text-sm">
          <thead className="bg-panel text-left text-[11px] uppercase tracking-wider text-ink-faint">
            <tr>
              {["Run", "Customer", "Model", "Verdict", "Steps", "Cost", "Latency", "Started"].map((h) => (
                <th key={h} className="px-3 py-2.5 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {runs.data?.runs.map((r) => (
              <tr key={r.run_id} className="border-t border-line transition-colors hover:bg-panel/50">
                <td className="px-3 py-2 font-mono text-xs text-ink-dim">{r.run_id}</td>
                <td className="px-3 py-2 text-ink">{r.customer_id ?? "—"}</td>
                <td className="px-3 py-2 font-mono text-xs text-ink-faint">{r.model}</td>
                <td className="px-3 py-2">
                  {r.final_verdict ? <VerdictBadge decision={r.final_verdict} /> : <span className="text-ink-faint">—</span>}
                </td>
                <td className="px-3 py-2 font-mono text-ink-dim">{r.step_count}</td>
                <td className="px-3 py-2 font-mono text-ink-dim">${r.total_cost_usd.toFixed(4)}</td>
                <td className="px-3 py-2 font-mono text-ink-dim">{r.total_latency_ms}ms</td>
                <td className="px-3 py-2 font-mono text-[11px] text-ink-faint">{r.started_at.slice(0, 19)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {runs.data?.runs.length === 0 && (
          <div className="p-8 text-center text-sm text-ink-faint">No runs yet — send a chat message first.</div>
        )}
        {runs.isLoading && <div className="p-8 text-center text-sm text-ink-faint">Loading…</div>}
      </div>
    </div>
  );
}
