import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { RunsTab } from "../components/RunsTab";
import { SettingsTab } from "../components/SettingsTab";
import { DataTab } from "../components/DataTab";

type Tab = "runs" | "settings" | "data";
const TABS: [Tab, string][] = [
  ["runs", "Runs & Traces"],
  ["settings", "Settings"],
  ["data", "Data"],
];

export default function AdminPage() {
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState<Tab>("runs");
  const runParam = params.get("run");

  const selectRun = (id: string | null) => {
    const p = new URLSearchParams(params);
    if (id) p.set("run", id);
    else p.delete("run");
    setParams(p, { replace: true });
  };

  return (
    <div className="py-6">
      <h1 className="font-display text-2xl font-bold tracking-tight text-ink">Operator console</h1>
      <p className="mt-1 text-sm text-ink-dim">Every agent run, fully traced — plus live settings and order controls.</p>

      <div className="mb-5 mt-4 inline-flex rounded-full border border-line bg-panel/60 p-1 backdrop-blur">
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)} className="relative rounded-full px-4 py-1.5 text-sm font-medium">
            {tab === k && (
              <motion.span
                layoutId="admin-pill"
                className="absolute inset-0 rounded-full bg-lime/35"
                transition={{ type: "spring", stiffness: 400, damping: 32 }}
              />
            )}
            <span className={`relative transition-colors ${tab === k ? "text-ink" : "text-ink-dim"}`}>{label}</span>
          </button>
        ))}
      </div>

      <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22 }}>
        {tab === "runs" && <RunsTab selectedRun={runParam} onSelect={selectRun} />}
        {tab === "settings" && <SettingsTab />}
        {tab === "data" && <DataTab />}
      </motion.div>
    </div>
  );
}
