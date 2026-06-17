import type { Decision } from "../types";

const MAP: Record<Decision, { label: string; cls: string }> = {
  APPROVE: { label: "Approved", cls: "text-approve border-approve/40 bg-approve/10" },
  DENY: { label: "Denied", cls: "text-deny border-deny/40 bg-deny/10" },
  ESCALATE: { label: "Escalated", cls: "text-escalate border-escalate/40 bg-escalate/10" },
};

export function VerdictBadge({ decision }: { decision: Decision }) {
  const v = MAP[decision];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${v.cls}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {v.label}
    </span>
  );
}
