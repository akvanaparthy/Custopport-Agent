import { useState } from "react";
import { useSearchParams } from "react-router-dom";
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

      <div className="mb-5 mt-4 inline-flex rounded-lg border border-line bg-panel/60 p-1 text-sm">
        {TABS.map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`rounded-md px-3 py-1.5 font-medium transition-colors ${
              tab === k ? "bg-signal/15 text-signal" : "text-ink-dim hover:text-ink"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "runs" && <RunsTab selectedRun={runParam} onSelect={selectRun} />}
      {tab === "settings" && <SettingsTab />}
      {tab === "data" && <DataTab />}
    </div>
  );
}
