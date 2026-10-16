import { useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { motion, useReducedMotion } from "motion/react";
import {
  Activity,
  Box,
  ChevronRight,
  Cpu,
  LayoutDashboard,
  Menu,
  Radio,
  RefreshCw,
  ServerOff,
  ShieldCheck,
  Siren,
  SlidersHorizontal,
} from "lucide-react";
import { useCity } from "./api/useCity";
import { useScenario } from "./api/useScenario";
import { Badge } from "./components/ui";
import CityWorkspace from "./components/CityWorkspace";
import AgentExplorer from "./components/AgentExplorer";
import ScenarioLab from "./components/ScenarioLab";
import DemoMode from "./components/DemoMode";
import ModelLab from "./components/ModelLab";
import { useRisk } from "./api/useRisk";

const nav = [
  { path: "/", name: "Command Center", icon: LayoutDashboard },
  { path: "/digital-twin", name: "Digital Twin Studio", icon: Box },
  { path: "/scenarios", name: "Scenario Lab", icon: SlidersHorizontal },
  { path: "/decisions", name: "AI Decision Explorer", icon: Activity },
  { path: "/model", name: "Model Intelligence Lab", icon: Cpu },
  { path: "/demo", name: "Guided Demo", icon: Siren },
];

export default function App() {
  const location = useLocation();
  const { city, status, error, retry } = useCity();
  const simulation = useScenario(location.pathname);
  const risk = useRisk(simulation.scenario);
  const [menuOpen, setMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(
    () => window.matchMedia("(max-width: 550px)").matches,
  );
  const reducedMotion = useReducedMotion();
  useEffect(() => {
    setMenuOpen(false);
    document.title = `${nav.find((n) => n.path === location.pathname)?.name ?? "Page not found"} · RESQ-AI`;
    document.getElementById("main-content")?.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }, [location.pathname]);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 550px)");
    const update = (event: MediaQueryListEvent) => setIsMobile(event.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return (
    <div className="app">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside
        className={`sidebar ${menuOpen ? "mobile-open" : ""}`}
        inert={isMobile && !menuOpen}
        aria-hidden={isMobile && !menuOpen}
        onKeyDown={(event) => {
          if (event.key === "Escape") setMenuOpen(false);
        }}
      >
        <Link to="/" className="brand" aria-label="RESQ-AI Command Center">
          <span className="brand-mark">
            <ShieldCheck size={25} />
          </span>
          <span>
            RESQ<span className="brand-ai">-AI</span>
            <small>DISASTER INTELLIGENCE</small>
          </span>
        </Link>
        <div className="workspace-label">
          <span className="workspace-symbol">R</span>
          <div>
            Riverside workspace<small>Local environment</small>
          </div>
          <ChevronRight size={14} />
        </div>
        <div className="nav-label">OPERATIONS</div>
        <nav aria-label="Main navigation">
          {nav.map((n) => (
            <NavLink
              key={n.path}
              to={n.path}
              end={n.path === "/"}
              aria-label={n.name}
              title={n.name}
            >
              <n.icon size={18} />
              <span>{n.name}</span>
              {n.path === "/" && <i />}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-note">
          <div>
            <Radio size={16} />
            <span>Built to stay local.</span>
          </div>
          <p>Your city data and operations remain on this machine.</p>
          <span className="mono">OFFLINE-FIRST ARCHITECTURE</span>
        </div>
        <div className="sidebar-bottom">
          <span className="avatar">RC</span>
          <div>
            Rescue Command<small>Development workspace</small>
          </div>
          <Badge>02</Badge>
        </div>
      </aside>
      {menuOpen && (
        <button
          className="mobile-scrim"
          aria-label="Close navigation"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <div className="app-content">
        <header className="topbar">
          <div>
            <button
              className="mobile-menu icon-button"
              aria-label="Toggle navigation"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(!menuOpen)}
            >
              <Menu size={20} />
            </button>
            <span className="header-icon">
              <Siren size={17} />
            </span>
            <span>Emergency operations</span>
            <span className="header-divider" />
            <span className="header-scenario">
              {simulation.scenario?.name ?? city?.scenario.name ?? "Riverside / Baseline"}
            </span>
          </div>
          <div className="header-right">
            <span className={`connection ${status}`} role="status">
              <i />
              {status === "online"
                ? "Local service connected"
                : status === "loading"
                  ? "Connecting to local service"
                  : "Local service offline"}
            </span>
            <button
              className="icon-button"
              aria-label="Refresh city state"
              title="Reload city snapshot and check backend connectivity"
              onClick={retry}
            >
              <RefreshCw size={16} />
            </button>
            <span className="part-label">PART 08</span>
          </div>
        </header>
        <div id="main-content" tabIndex={-1}>
          {status === "loading" && !city ? (
            <div className="loading-layout" role="status">
              <span className="eyebrow">CONNECTING TO RIVERSIDE</span>
              <h1>Preparing your workspace.</h1>
              <div className="skeleton-stats">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} />
                ))}
              </div>
              <div className="skeleton-map" />
              <p>Loading the city from the local Python service…</p>
            </div>
          ) : !city ? (
            <div className="error-page" role="alert">
              <ServerOff size={42} />
              <Badge tone="amber">Local connection unavailable</Badge>
              <h1>Let’s reconnect your command center.</h1>
              <p>{error}</p>
              <code>
                python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
              </code>
              <small>
                Run this from the backend folder after activating its
                environment.
              </small>
              <button className="primary-button" onClick={retry}>
                <RefreshCw size={16} /> Retry connection
              </button>
            </div>
          ) : (
            <motion.div
              key={location.pathname}
              initial={reducedMotion ? false : { opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
            >
              <Routes>
                <Route
                  path="/"
                  element={
                    <CityWorkspace
                      city={city}
                      scenario={simulation.scenario}
                      events={simulation.envelope?.events ?? []}
                      studio={false}
                      status={status}
                      retry={retry}
                      model={risk.model}
                      predictions={risk.predictions}
                    />
                  }
                />
                <Route
                  path="/digital-twin"
                  element={
                    <CityWorkspace
                      city={city}
                      scenario={simulation.scenario}
                      events={simulation.envelope?.events ?? []}
                      studio
                      status={status}
                      retry={retry}
                      model={risk.model}
                      predictions={risk.predictions}
                    />
                  }
                />
                <Route
                  path="/scenarios"
                  element={<ScenarioLab city={city} envelope={simulation.envelope} scenario={simulation.scenario} error={simulation.error} onChange={simulation.accept} onRetry={simulation.retry} />}
                />
                <Route
                  path="/decisions"
                  element={<AgentExplorer scenario={simulation.scenario} />}
                />
                <Route path="/model" element={<ModelLab scenario={simulation.scenario} />} />
                <Route path="/demo" element={<DemoMode city={city} scenario={simulation.scenario} onChange={simulation.accept} />} />
                <Route
                  path="*"
                  element={
                    <div className="error-page">
                      <h1>Page not found</h1>
                      <Link to="/" className="primary-button">
                        Return to Command Center
                      </Link>
                    </div>
                  }
                />
              </Routes>
            </motion.div>
          )}
        </div>
        <footer className="app-footer">
          <span>
            RESQ-AI <i /> Predict. Simulate. Prioritize. Respond. Replan.
          </span>
          <span>FICTIONAL SCENARIO · LOCAL PROTOTYPE</span>
        </footer>
      </div>
    </div>
  );
}
