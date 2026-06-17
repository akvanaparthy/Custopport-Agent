import { useState } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import ChatPage from "./pages/ChatPage";
import OrdersPage from "./pages/OrdersPage";
import HistoryPage from "./pages/HistoryPage";
import AdminPage from "./pages/AdminPage";
import { useApp } from "./store";

function NavTab({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        ["relative rounded-full px-4 py-1.5 text-sm font-medium transition-colors", isActive ? "text-ink" : "text-ink-dim hover:text-ink"].join(" ")
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <motion.span
              layoutId="nav-pill"
              className="absolute inset-0 rounded-full bg-lime/35"
              transition={{ type: "spring", stiffness: 400, damping: 32 }}
            />
          )}
          <span className="relative">{label}</span>
        </>
      )}
    </NavLink>
  );
}

function AccountChip() {
  const { customerName, customerEmail, customerId, identityMode, verified, resetSession } = useApp();
  const [open, setOpen] = useState(false);
  if (!verified || !customerName) return null;
  const initial = customerName.charAt(0).toUpperCase();
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-full border border-line bg-panel/70 py-1 pl-1 pr-3 shadow-sm backdrop-blur transition-colors hover:border-signal/40"
      >
        <span className="grid h-6 w-6 place-items-center rounded-full bg-ink text-[11px] font-semibold text-canvas">{initial}</span>
        <span className="text-sm font-medium text-ink">{customerName}</span>
      </button>
      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, y: -8, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.97 }}
              transition={{ type: "spring", stiffness: 360, damping: 28 }}
              className="glass absolute right-0 z-40 mt-2 w-64 rounded-2xl p-4"
            >
              <div className="flex items-center gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-full bg-lime-soft text-sm font-semibold text-signal">{initial}</span>
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-ink">{customerName}</div>
                  <div className="truncate font-mono text-[11px] text-ink-faint">{customerEmail ?? customerId}</div>
                </div>
              </div>
              <div className="mt-3 rounded-xl bg-panel-2 px-3 py-2 text-[11px] text-ink-dim">
                Signed in via <span className="font-mono text-ink">{identityMode}</span>
              </div>
              <Link
                to="/orders"
                onClick={() => setOpen(false)}
                className="mt-2 block rounded-xl px-3 py-2 text-sm text-ink transition-colors hover:bg-panel-2"
              >
                Your orders →
              </Link>
              <Link
                to="/history"
                onClick={() => setOpen(false)}
                className="block rounded-xl px-3 py-2 text-sm text-ink transition-colors hover:bg-panel-2"
              >
                Support history →
              </Link>
              <button
                onClick={() => {
                  setOpen(false);
                  resetSession();
                }}
                className="mt-1 w-full rounded-xl px-3 py-2 text-left text-sm text-deny transition-colors hover:bg-deny/5"
              >
                Sign out
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function App() {
  const location = useLocation();
  return (
    <div className="relative z-10 flex min-h-full flex-col">
      <header className="sticky top-0 z-30 border-b border-line/70 bg-canvas/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-2.5">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2.5">
              <span className="grid h-8 w-8 place-items-center rounded-xl bg-ink font-mono text-lime shadow-sm">⟳</span>
              <span className="font-display text-[16px] font-bold leading-none tracking-tight text-ink">
                Refund<span className="text-signal">Agent</span>
              </span>
            </Link>
            <nav className="flex items-center gap-1 rounded-full border border-line/70 bg-panel/50 p-1 backdrop-blur">
              <NavTab to="/" label="Chat" />
              <NavTab to="/orders" label="Orders" />
              <NavTab to="/admin" label="Console" />
            </nav>
          </div>
          <AccountChip />
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-5">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.28, ease: [0.2, 0.7, 0.2, 1] }}
            className="h-full"
          >
            <Routes location={location}>
              <Route path="/" element={<ChatPage />} />
              <Route path="/orders" element={<OrdersPage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/admin" element={<AdminPage />} />
            </Routes>
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
