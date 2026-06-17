import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getOrders, resetOrder, resetSeed, updateOrderStatus } from "../api";

const STATUSES = ["delivered", "shipped", "processing", "pending", "cancelled"];

export function DataTab() {
  const qc = useQueryClient();
  const { data: orders } = useQuery({ queryKey: ["orders"], queryFn: getOrders });
  const inval = () => {
    qc.invalidateQueries({ queryKey: ["orders"] });
    qc.invalidateQueries({ queryKey: ["runs"] });
  };
  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateOrderStatus(id, status),
    onSuccess: inval,
  });
  const resetMut = useMutation({ mutationFn: (id: string) => resetOrder(id), onSuccess: inval });
  const seedMut = useMutation({ mutationFn: resetSeed, onSuccess: () => qc.invalidateQueries() });

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm text-ink-dim">
          Operator data — edit status or reset an order to re-test. This is outside the agent's tools.
        </p>
        <button
          onClick={() => window.confirm("Reset all demo data to the seed state?") && seedMut.mutate()}
          className="rounded-md border border-line px-3 py-1.5 text-xs font-medium text-ink-dim transition-colors hover:border-signal/40 hover:text-ink"
        >
          {seedMut.isPending ? "Resetting…" : "Reset all to seed"}
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border border-line">
        <table className="w-full text-sm">
          <thead className="bg-panel text-left text-[11px] uppercase tracking-wider text-ink-faint">
            <tr>
              {["Order", "Customer", "Item", "Category", "Total", "Status", "Refunded", ""].map((h) => (
                <th key={h} className="px-3 py-2.5 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {orders?.map((o) => (
              <tr key={o.order_id} className="border-t border-line">
                <td className="px-3 py-2 font-mono text-xs text-ink-dim">
                  {o.order_id}
                  {o.is_final_sale && (
                    <span className="ml-1.5 rounded bg-deny/15 px-1 py-0.5 text-[9px] text-deny">final</span>
                  )}
                </td>
                <td className="px-3 py-2 text-ink-dim">{o.customer_id}</td>
                <td className="px-3 py-2 text-ink">{o.item_name}</td>
                <td className="px-3 py-2 font-mono text-xs text-ink-faint">{o.category}</td>
                <td className="px-3 py-2 font-mono text-ink-dim">${o.order_total.toFixed(2)}</td>
                <td className="px-3 py-2">
                  <select
                    value={o.status}
                    onChange={(e) => statusMut.mutate({ id: o.order_id, status: e.target.value })}
                    className="rounded border border-line bg-canvas px-1.5 py-1 font-mono text-xs text-ink outline-none focus:border-signal/60"
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-3 py-2">
                  {o.already_refunded ? (
                    <span className="font-mono text-xs text-escalate">${o.refunded_amount.toFixed(2)}</span>
                  ) : (
                    <span className="text-ink-faint">—</span>
                  )}
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    onClick={() => resetMut.mutate(o.order_id)}
                    className="rounded border border-line px-2 py-1 text-[11px] text-ink-dim transition-colors hover:border-signal/40 hover:text-ink"
                  >
                    reset
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
