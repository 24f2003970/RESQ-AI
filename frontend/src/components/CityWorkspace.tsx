import {
  lazy,
  Suspense,
  useEffect,
  useState,
  type ComponentProps,
} from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowDownToLine,
  Bot,
  Building2,
  ChevronRight,
  Hospital,
  Layers3,
  RefreshCw,
  ServerOff,
  Settings2,
  ShieldCheck,
  Trees,
  Truck,
  Users,
  Waves,
  X,
} from "lucide-react";
import type { Layers } from "../scene/CityScene";
import { fetchBuilding, type Building, type CityState } from "../api/client";
import { Badge, Help, Panel, Row } from "./ui";
import Inspector from "./Inspector";

const LazyCityScene = lazy(() => import("../scene/CityScene"));
function CityScene(props: ComponentProps<typeof LazyCityScene>) {
  return (
    <Suspense
      fallback={
        <div className="city-scene scene-loading">Preparing city geometry…</div>
      }
    >
      <LazyCityScene {...props} />
    </Suspense>
  );
}

export default function CityWorkspace({
  city,
  studio,
  status,
  retry,
}: {
  city: CityState;
  studio: boolean;
  status: string;
  retry: () => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Building | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [layerOpen, setLayerOpen] = useState(false);
  const [lowGraphics, setLowGraphics] = useState(false);
  const [layers, setLayers] = useState<Layers>({
    buildings: true,
    greenery: true,
    facilities: true,
    districts: false,
    units: true,
  });
  useEffect(() => {
    setSelected(null);
    setDetailError("");
    if (!selectedId) {
      setDetailLoading(false);
      return;
    }
    const controller = new AbortController();
    setDetailLoading(true);
    fetchBuilding(selectedId, city, controller.signal)
      .then((building) => {
        if (!controller.signal.aborted) {
          setSelected(building);
          setDetailLoading(false);
        }
      })
      .catch((e: unknown) => {
        if (!controller.signal.aborted) {
          setDetailError(
            e instanceof Error ? e.message : "Cannot load building details.",
          );
          setDetailLoading(false);
        }
      });
    return () => controller.abort();
  }, [selectedId, city]);
  const totalOccupants = city.buildings.reduce(
    (total, b) => total + b.occupants,
    0,
  );
  function downloadSnapshot() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(city, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `${city.city.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <main className={`workspace ${studio ? "studio" : ""}`}>
      <div className="page-heading">
        <div>
          <div className="breadcrumb">
            WORKSPACE <ChevronRight size={12} />
            {studio ? "DIGITAL TWIN" : "OVERVIEW"}
          </div>
          <h1>
            {studio ? "Digital Twin Studio" : "Situation overview"}
            <span className="heading-dot" />
          </h1>
          <p>
            {studio
              ? "Explore the city. Inspect the details."
              : "A clear picture. A prepared response."}
          </p>
        </div>
        <button className="secondary-button" onClick={downloadSnapshot}>
          <ArrowDownToLine size={15} /> Export snapshot
        </button>
      </div>
      {status === "offline" && (
        <div className="connection-banner" role="alert">
          <ServerOff size={17} />
          <span>Backend offline. Showing the last loaded snapshot.</span>
          <button onClick={retry}>
            Reconnect <RefreshCw size={13} />
          </button>
        </div>
      )}
      {!studio && (
        <div className="stats-grid">
          {[
            {
              label: "City buildings",
              value: city.buildings.length,
              icon: Building2,
              note: `${city.districts.length} districts mapped`,
            },
            {
              label: "Seeded occupants",
              value: totalOccupants.toLocaleString(),
              icon: Users,
              note: "Fictional population inventory",
            },
            {
              label: "Emergency facilities",
              value: city.hospitals.length + city.shelters.length,
              icon: Hospital,
              note: `${city.hospitals.length} hospital · ${city.shelters.length} shelter`,
            },
            {
              label: "Response units",
              value: city.rescue_units.length,
              icon: Truck,
              note: "All units on standby",
            },
          ].map((s) => (
            <div className="stat-card" key={s.label}>
              <div>
                <span>{s.label}</span>
                <s.icon size={17} />
              </div>
              <strong>{s.value}</strong>
              <small>
                <i />
                {s.note}
              </small>
            </div>
          ))}
        </div>
      )}
      <div className="main-grid">
        <div className="main-column">
          <section className="viewport-panel">
            <div className="viewport-heading">
              <div>
                <span className="live-dot" />
                <h2>Riverside Digital Twin</h2>
                <Badge>3D CITY</Badge>
              </div>
              <div>
                <button
                  className={`secondary-button small ${lowGraphics ? "active" : ""}`}
                  aria-pressed={lowGraphics}
                  onClick={() => setLowGraphics(!lowGraphics)}
                  title="Cap pixel ratio and disable shadows for weaker GPUs"
                >
                  <Settings2 size={14} />
                  {lowGraphics ? "Low graphics" : "Standard"}
                </button>
                <button
                  className={`secondary-button small ${layerOpen ? "active" : ""}`}
                  aria-expanded={layerOpen}
                  onClick={() => setLayerOpen(!layerOpen)}
                >
                  <Layers3 size={14} /> Layers
                </button>
              </div>
            </div>
            <div className="viewport-wrap">
              <CityScene
                city={city}
                selected={selected}
                onSelect={setSelectedId}
                layers={layers}
                lowGraphics={lowGraphics}
              />
              <AnimatePresence>
                {layerOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="layer-menu"
                  >
                    <div>
                      <strong>Map layers</strong>
                      <button
                        aria-label="Close layers"
                        onClick={() => setLayerOpen(false)}
                      >
                        <X size={14} />
                      </button>
                    </div>
                    {(Object.keys(layers) as (keyof Layers)[]).map((key) => (
                      <label key={key}>
                        <span>{key}</span>
                        <input
                          type="checkbox"
                          checked={layers[key]}
                          onChange={() =>
                            setLayers((l) => ({ ...l, [key]: !l[key] }))
                          }
                        />
                      </label>
                    ))}
                    <p>
                      Flood, risk and rescue route layers arrive in later parts.
                    </p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
            <div className="viewport-footer">
              <span>
                <i className="legend-block" />
                Buildings
              </span>
              <span>
                <i className="legend-water" />
                Canal
              </span>
              <span>
                <i className="legend-facility" />
                Facilities
              </span>
              <span className="viewport-state">
                BASELINE · NO DISASTER ACTIVE
              </span>
            </div>
          </section>
          <div className="support-grid">
            <Panel
              title="Infrastructure"
              eyebrow="CITY NETWORK"
              action={<Waves size={17} />}
            >
              <div className="infrastructure-count">
                <strong>
                  {city.roads.length}
                  <small>roads</small>
                </strong>
                <span>+</span>
                <strong>
                  {city.bridges.length}
                  <small>bridges</small>
                </strong>
                <Badge>Baseline open</Badge>
              </div>
              <div className="infrastructure-track">
                {city.roads.map((r) => (
                  <span key={r.id} title={`${r.name} · ${r.status}`} />
                ))}
              </div>
              <p className="muted">
                Connected seed inventory. Closures and flood impacts are not
                active yet.
              </p>
            </Panel>
            <Panel
              title="Response readiness"
              eyebrow="LOCAL INVENTORY"
              action={<Truck size={17} />}
            >
              {(["ambulance", "boat", "rescue_team"] as const).map((type) => (
                <Row
                  key={type}
                  title={
                    {
                      ambulance: "Ambulances",
                      boat: "Rescue boats",
                      rescue_team: "Rescue teams",
                    }[type]
                  }
                  subtitle="Standby · no active mission"
                  value={
                    <span className="count-pill">
                      {city.rescue_units.filter((u) => u.type === type).length}
                    </span>
                  }
                />
              ))}
            </Panel>
          </div>
          <Panel
            title="Workspace activity"
            eyebrow="STATE RECORD"
            action={<Badge>Version {city.scenario.state_version}</Badge>}
          >
            <div className="timeline-entry">
              <span className="timeline-point" />
              <span className="mono">T+00:00</span>
              <div>
                <strong>Baseline city loaded</strong>
                <p>
                  {city.buildings.length} buildings, {city.roads.length} roads
                  and {city.rescue_units.length} response units from the local
                  service.
                </p>
              </div>
              <Badge>Seed {city.city.seed}</Badge>
            </div>
            <p className="activity-note">
              Scenario metadata only. A persistent disaster event timeline will
              be added with simulation.
            </p>
          </Panel>
        </div>
        <aside className="right-column">
          <Inspector
            selected={selected}
            city={city}
            loading={detailLoading}
            error={detailError}
            close={() => setSelectedId(null)}
            choose={setSelectedId}
          />
          <Panel
            title="Critical facilities"
            eyebrow="ESSENTIAL SERVICES"
            action={<Hospital size={17} />}
          >
            {city.hospitals.map((h) => (
              <Row
                key={h.id}
                title={h.name}
                subtitle={`${h.capacity} beds · seeded capacity`}
                value={
                  <span className="facility-icon">
                    <Hospital size={15} />
                  </span>
                }
                onClick={() => setSelectedId(h.building_id)}
              />
            ))}
            {city.shelters.map((s) => (
              <Row
                key={s.id}
                title={s.name}
                subtitle={`${s.capacity} places · ${s.occupancy} occupied`}
                value={
                  <span className="facility-icon">
                    <ShieldCheck size={15} />
                  </span>
                }
                onClick={() => setSelectedId(s.building_id)}
              />
            ))}
          </Panel>
          <section className="ai-card">
            <span className="ai-icon">
              <Bot size={19} />
            </span>
            <div>
              <h2>Intelligence, with evidence.</h2>
              <p>
                Agent recommendations will appear here once the risk and
                planning pipeline is implemented.
              </p>
              <Badge tone="amber">Not active in Part 2</Badge>
            </div>
          </section>
          <div className="provenance">
            <Trees size={15} />
            <p>
              Fictional city, real application state.
              <span>
                Generator {city.city.generator_version} · Local meters
              </span>
            </p>
            <Help text="City geometry, occupants, facilities and resource counts are generated deterministically by the Python backend. They do not represent a real city." />
          </div>
        </aside>
      </div>
    </main>
  );
}
