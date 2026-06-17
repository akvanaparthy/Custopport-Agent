import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getSettings, putSettings } from "../api";
import type { SettingsView } from "../types";

const MODELS = ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5"];
const EFFORTS = ["low", "medium", "high", "max"];
const MODES = ["authenticated", "in_chat"];

export function SettingsTab() {
  const qc = useQueryClient();
  const { data: s } = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const mut = useMutation({
    mutationFn: putSettings,
    onSuccess: (d) => qc.setQueryData(["settings"], d),
  });
  const [persona, setPersona] = useState<string | null>(null);

  if (!s) return <div className="p-6 text-sm text-ink-faint">Loading settings…</div>;
  const set = (patch: Partial<SettingsView>) => mut.mutate(patch);
  const badge = (k: string) => <SourceBadge override={s.source_map[k] === "override"} />;

  return (
    <div className="glass max-w-2xl space-y-1 rounded-2xl p-2">
      <Row label="Model" hint={badge("model")}>
        <Select value={s.model} options={MODELS} onChange={(v) => set({ model: v })} />
      </Row>
      <Row label="Effort" hint={badge("effort")}>
        <Select value={s.effort} options={EFFORTS} onChange={(v) => set({ effort: v as SettingsView["effort"] })} />
      </Row>
      <Row label="Adaptive thinking" hint={badge("adaptive_thinking")}>
        <Toggle on={s.adaptive_thinking} onChange={(v) => set({ adaptive_thinking: v })} />
      </Row>
      <Row label="Max output tokens" hint={badge("max_tokens")}>
        <input
          type="number"
          min={1}
          max={16000}
          defaultValue={s.max_tokens}
          onBlur={(e) => set({ max_tokens: Math.min(16000, Math.max(1, Number(e.target.value) || s.max_tokens)) })}
          className="w-28 rounded-md border border-line bg-canvas px-2 py-1 font-mono text-sm text-ink outline-none focus:border-signal/60"
        />
      </Row>
      <Row label="Input guard" hint={badge("input_guard_enabled")}>
        <Toggle on={s.input_guard_enabled} onChange={(v) => set({ input_guard_enabled: v })} />
      </Row>
      <Row label="Output validation" hint={badge("output_validation_enabled")}>
        <Toggle on={s.output_validation_enabled} onChange={(v) => set({ output_validation_enabled: v })} />
      </Row>
      <Row label="Identity mode" hint={badge("identity_mode")}>
        <Select value={s.identity_mode} options={MODES} onChange={(v) => set({ identity_mode: v as SettingsView["identity_mode"] })} />
      </Row>
      <div className="px-3 py-3">
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-sm text-ink">Persona</span>
          {badge("persona")}
        </div>
        <textarea
          value={persona ?? s.persona}
          onChange={(e) => setPersona(e.target.value)}
          onBlur={() => persona != null && persona !== s.persona && set({ persona })}
          rows={4}
          className="w-full resize-none rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-signal/60"
        />
      </div>
      <p className="px-3 pb-2 text-xs text-ink-faint">
        No temperature / top-p — <span className="text-ink-dim">effort</span> is the reasoning dial (sampling params
        400 on Opus 4.8). Changes apply on the next chat message.
      </p>
    </div>
  );
}

function Row({ label, hint, children }: { label: string; hint: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line/60 px-3 py-2.5 last:border-0">
      <div className="flex items-center gap-2">
        <span className="text-sm text-ink">{label}</span>
        {hint}
      </div>
      {children}
    </div>
  );
}

function Select({ value, options, onChange }: { value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-md border border-line bg-canvas px-2 py-1 font-mono text-sm text-ink outline-none focus:border-signal/60"
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!on)}
      className={`relative h-6 w-11 rounded-full transition-colors ${on ? "bg-signal" : "bg-line-bright"}`}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-canvas transition-transform ${
          on ? "translate-x-[22px]" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

function SourceBadge({ override }: { override?: boolean }) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider ${
        override ? "bg-signal/15 text-signal" : "bg-canvas text-ink-faint"
      }`}
    >
      {override ? "override" : "env"}
    </span>
  );
}
