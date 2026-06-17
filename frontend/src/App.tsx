import { NavLink, Route, Routes } from "react-router-dom";
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
          "relative px-3 py-1.5 text-sm font-medium transition-colors",
          isActive ? "text-ink" : "text-ink-dim hover:text-ink",
        ].join(" ")
      }
    >
      {({ isActive }) => (
        <>
          {label}
          {isActive && (
            <span className="absolute -bottom-[7px] left-0 right-0 h-[2px] bg-signal" />
          )}
        </>
      )}
    </NavLink>
  );
}

export default function App() {
  const { customerName, verified, identityMode } = useApp();
  return (
    <div className="relative z-10 flex min-h-full flex-col">
      <header className="sticky top-0 z-20 border-b border-line bg-canvas/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5">
          <div className="flex items-center gap-7">
            <div className="flex items-center gap-2.5">
              <span className="grid h-7 w-7 place-items-center rounded-md border border-signal/40 bg-signal/10 font-mono text-signal">
                ⟳
              </span>
              <div className="leading-none">
                <div className="font-display text-[15px] font-bold tracking-tight text-ink">
                  Refund<span className="text-signal">Agent</span>
                </div>
                <div className="text-[10px] uppercase tracking-[0.18em] text-ink-faint">
                  policy-enforced support
                </div>
              </div>
            </div>
            <nav className="flex items-center gap-1">
              <NavTab to="/" label="Chat" />
              <NavTab to="/admin" label="Console" />
            </nav>
          </div>
          {verified && customerName && (
            <div className="flex items-center gap-2 font-mono text-xs text-ink-dim">
              <span className="h-1.5 w-1.5 rounded-full bg-approve" />
              {customerName}
              <span className="text-ink-faint">/ {identityMode}</span>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-5">
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </main>
    </div>
  );
}
