import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getRun, getRuns } from "../api";
import type { StepView } from "../types";
import { VerdictBadge } from "./VerdictBadge";

export function RunsTab({
  selectedRun,
  onSelect,
}: {
  selectedRun: string | null;
  onSelect: (id: string | null) => void;
}) {
  const runs = useQuery({ queryKey: ["runs"], queryFn: getRuns, refetchInterval: 3000 });

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(300px,380px)_1fr]">
      <div className="overflow-hidden rounded-xl border border-line">
        <div className="border-b border-line bg-panel px-3 py-2 text-[11px] uppercase tracking-wider text-ink-faint">
          Runs {runs.data ? `· ${runs.data.total}` : ""}
        </div>
        <div className="max-h-[70vh] divide-y divide-line overflow-auto">
          {runs.data?.runs.map((r) => (
            <button
              key={r.run_id}
              onClick={() => onSelect(r.run_id)}
              className={`flex w-full items-center justify-between px-3 py-2.5 text-left transition-colors hover:bg-panel/60 ${
                selectedRun === r.run_id ? "bg-signal/10" : ""
              }`}
            >
              <span className="min-w-0">
                <span className="block truncate font-mono text-xs text-ink-dim">{r.run_id}</span>
                <span className="block text-xs text-ink-faint">
                  {r.customer_id ?? "—"} · {r.started_at.slice(11, 19)}
                </span>
              </span>
              {r.final_verdict ? (
                <VerdictBadge decision={r.final_verdict} />
              ) : (
                <span className="text-xs text-ink-faint">{r.status}</span>
              )}
            </button>
          ))}
          {runs.data?.runs.length === 0 && (
            <div className="p-6 text-center text-sm text-ink-faint">No runs yet.</div>
          )}
        </div>
      </div>

      <div className="min-h-[40vh] rounded-xl border border-line bg-panel/30">
        {selectedRun ? (
          <TraceView runId={selectedRun} />
        ) : (
          <div className="grid h-full place-items-center p-10 text-center text-sm text-ink-faint">
            Select a run to inspect its reasoning trace.
          </div>
        )}
      </div>
    </div>
  );
}

function TraceView({ runId }: { runId: string }) {
  const run = useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRun(runId),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 1500 : false),
  });

  if (run.isLoading) return <div className="p-6 text-sm text-ink-faint">Loading trace…</div>;
  if (run.isError || !run.data) return <div className="p-6 text-sm text-deny">Run not found.</div>;
  const r = run.data;

  return (
    <div className="p-4">
      <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-line pb-3">
        {r.final_verdict ? <VerdictBadge decision={r.final_verdict} /> : <span className="text-sm text-ink-faint">{r.status}</span>}
        <Stat label="customer" value={r.customer_id ?? "—"} />
        <Stat label="model" value={r.model} mono />
        <Stat label="tokens" value={`${r.total_input_tokens}/${r.total_output_tokens}`} mono />
        <Stat label="cost" value={`$${r.total_cost_usd.toFixed(5)}`} mono />
        <Stat label="latency" value={`${r.total_latency_ms}ms`} mono />
      </div>
      <div className="space-y-2">
        {r.steps.map((s) => (
          <StepCard key={s.step_index} step={s} />
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="leading-tight">
      <div className="text-[10px] uppercase tracking-wider text-ink-faint">{label}</div>
      <div className={`text-sm text-ink ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}

function StepCard({ step }: { step: StepView }) {
  const [open, setOpen] = useState(step.retry_count > 0 || step.status === "error");
  const accent =
    step.status === "error"
      ? "border-deny/50"
      : step.retry_count > 0
        ? "border-escalate/50"
        : "border-line";

  return (
    <div className={`rounded-lg border ${accent} bg-panel/60`}>
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-3 px-3 py-2 text-left">
        <span className="w-4 font-mono text-xs text-ink-faint">{step.step_index}</span>
        <span className="rounded bg-canvas px-1.5 py-0.5 font-mono text-[10px] text-ink-dim">{step.step_type}</span>
        <span className="text-sm text-ink">{step.name}</span>
        {step.retry_count > 0 && (
          <span className="rounded-full bg-escalate/15 px-2 py-0.5 text-[10px] font-semibold text-escalate">
            retried {step.retry_count}×
          </span>
        )}
        {step.status === "error" && (
          <span className="rounded-full bg-deny/15 px-2 py-0.5 text-[10px] font-semibold text-deny">error</span>
        )}
        <span className="ml-auto flex items-center gap-3 font-mono text-[11px] text-ink-faint">
          {(step.input_tokens > 0 || step.output_tokens > 0) && <span>{step.input_tokens}/{step.output_tokens} tok</span>}
          {step.cost_usd > 0 && <span>${step.cost_usd.toFixed(5)}</span>}
          <span>{step.latency_ms}ms</span>
          <span className="w-3 text-center text-ink-dim">{open ? "−" : "+"}</span>
        </span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-line px-3 py-2.5">
          {step.input != null && <JsonBlock label="input" value={step.input} />}
          {step.output != null && <JsonBlock label="output" value={step.output} />}
          {step.attempts != null && <JsonBlock label="attempts" value={step.attempts} />}
          {step.error != null && <JsonBlock label="error" value={step.error} />}
          {step.input == null && step.output == null && step.error == null && (
            <div className="text-xs text-ink-faint">no payload</div>
          )}
        </div>
      )}
    </div>
  );
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <div>
      <div className="mb-1 text-[10px] uppercase tracking-wider text-ink-faint">{label}</div>
      <pre className="max-h-60 overflow-auto rounded bg-canvas p-2 font-mono text-[11px] leading-relaxed text-ink-dim">
        {text}
      </pre>
    </div>
  );
}
