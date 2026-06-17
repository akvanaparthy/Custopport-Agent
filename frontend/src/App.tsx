import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import ChatPage from "./pages/ChatPage";
import AdminPage from "./pages/AdminPage";
import { useApp } from "./store";

function NavTab({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        [
          "relative rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
          isActive ? "text-ink" : "text-ink-dim hover:text-ink",
        ].join(" ")
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
  const { customerName, verified, resetSession } = useApp();
  if (!verified || !customerName) return null;
  const initial = customerName.charAt(0).toUpperCase();
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex items-center gap-2 rounded-full border border-line bg-panel/70 py-1 pl-1 pr-3 shadow-sm backdrop-blur">
        <span className="grid h-6 w-6 place-items-center rounded-full bg-ink text-[11px] font-semibold text-canvas">
          {initial}
        </span>
        <span className="text-sm font-medium text-ink">{customerName}</span>
      </div>
      <button
        onClick={resetSession}
        className="text-xs text-ink-faint transition-colors hover:text-ink"
        title="Sign out / switch customer"
      >
        switch
      </button>
    </div>
  );
}

export default function App() {
  const location = useLocation();
  return (
    <div className="relative z-10 flex min-h-full flex-col">
      <header className="sticky top-0 z-30 border-b border-line/70 bg-canvas/70 backdrop-blur-xl">
        <div className="mx-auto flex h-15 max-w-6xl items-center justify-between px-5 py-2.5">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2.5">
              <span className="grid h-8 w-8 place-items-center rounded-xl bg-ink font-mono text-lime shadow-sm">
                ⟳
              </span>
              <div className="font-display text-[16px] font-bold leading-none tracking-tight text-ink">
                Refund<span className="text-signal">Agent</span>
              </div>
            </div>
            <nav className="flex items-center gap-1 rounded-full border border-line/70 bg-panel/50 p-1 backdrop-blur">
              <NavTab to="/" label="Chat" />
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
              <Route path="/admin" element={<AdminPage />} />
            </Routes>
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
