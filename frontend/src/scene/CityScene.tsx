import {
  Component,
  Suspense,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Canvas, type ThreeEvent, useThree } from "@react-three/fiber";
import { Edges, Line, OrbitControls } from "@react-three/drei";
import {
  BoxGeometry,
  Color,
  InstancedMesh,
  Matrix4,
  MeshStandardMaterial,
  PCFShadowMap,
  Vector3,
} from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { Compass, Focus, Minus, Plus, RotateCcw, View } from "lucide-react";
import type { Building, CityState } from "../api/client";
import { toScene } from "./coordinates";

export type Layers = {
  buildings: boolean;
  greenery: boolean;
  facilities: boolean;
  districts: boolean;
  units: boolean;
};
type Instance = {
  position: [number, number, number];
  scale: [number, number, number];
  color: string;
  id?: string;
};
const box = new BoxGeometry(1, 1, 1);
const surface = new MeshStandardMaterial({ roughness: 0.82, metalness: 0.05 });

function Batch({
  items,
  onSelect,
  shadows = false,
}: {
  items: Instance[];
  onSelect?: (id: string) => void;
  shadows?: boolean;
}) {
  const ref = useRef<InstancedMesh>(null);
  useLayoutEffect(() => {
    const mesh = ref.current;
    if (!mesh) return;
    items.forEach((item, index) => {
      mesh.setMatrixAt(
        index,
        new Matrix4().makeScale(...item.scale).setPosition(...item.position),
      );
      mesh.setColorAt(index, new Color(item.color));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.computeBoundingSphere();
  }, [items]);
  if (!items.length) return null;
  return (
    <instancedMesh
      ref={ref}
      args={[box, surface, items.length]}
      dispose={null}
      castShadow={shadows}
      receiveShadow
      onClick={
        onSelect
          ? (event: ThreeEvent<MouseEvent>) => {
              if (event.delta > 4) return;
              event.stopPropagation();
              const id = items[event.instanceId ?? -1]?.id;
              if (id) onSelect(id);
            }
          : undefined
      }
    />
  );
}

function BuildingBlocks({
  city,
  onSelect,
  selected,
}: {
  city: CityState;
  onSelect: (id: string) => void;
  selected: Building | null;
}) {
  const batches = useMemo(() => {
    const walls: Instance[] = [],
      roofs: Instance[] = [],
      windows: Instance[] = [],
      equipment: Instance[] = [];
    for (const b of city.buildings) {
      const [x, y, z] = toScene(b.position);
      const color =
        b.use === "hospital"
          ? "#d3dfd7"
          : b.use === "shelter"
            ? "#aac5b4"
            : b.material_color;
      walls.push({
        position: [x, y + b.height_m / 2, z],
        scale: [b.width_m, b.height_m, b.depth_m],
        color,
        id: b.id,
      });
      roofs.push({
        position: [x, y + b.height_m + 0.7, z],
        scale: [b.width_m + 1.1, 1.4, b.depth_m + 1.1],
        color: "#69787b",
        id: b.id,
      });
      equipment.push({
        position: [x - b.width_m * 0.18, y + b.height_m + 2.1, z],
        scale: [b.width_m * 0.3, 2, b.depth_m * 0.3],
        color: "#9aa6a7",
        id: b.id,
      });
      for (let floor = 0; floor < b.floors; floor++) {
        const wy = y + floor * 3.6 + 2;
        for (let column = -1; column <= 1; column++) {
          const tint = (floor + column) % 3 === 0 ? "#b6c2b3" : "#475f69";
          windows.push({
            position: [
              x + column * b.width_m * 0.27,
              wy,
              z + b.depth_m / 2 + 0.08,
            ],
            scale: [b.width_m * 0.16, 1.5, 0.2],
            color: tint,
            id: b.id,
          });
          windows.push({
            position: [
              x + b.width_m / 2 + 0.08,
              wy,
              z + column * b.depth_m * 0.27,
            ],
            scale: [0.2, 1.5, b.depth_m * 0.16],
            color: tint,
            id: b.id,
          });
          windows.push({
            position: [
              x + column * b.width_m * 0.27,
              wy,
              z - b.depth_m / 2 - 0.08,
            ],
            scale: [b.width_m * 0.16, 1.5, 0.2],
            color: tint,
            id: b.id,
          });
          windows.push({
            position: [
              x - b.width_m / 2 - 0.08,
              wy,
              z + column * b.depth_m * 0.27,
            ],
            scale: [0.2, 1.5, b.depth_m * 0.16],
            color: tint,
            id: b.id,
          });
        }
      }
    }
    return { walls, roofs, windows, equipment };
  }, [city]);
  return (
    <>
      <Batch items={batches.walls} onSelect={onSelect} shadows />
      <Batch items={batches.roofs} onSelect={onSelect} />
      <Batch items={batches.equipment} onSelect={onSelect} shadows />
      <Batch items={batches.windows} onSelect={onSelect} />
      {selected && (
        <mesh
          position={[
            selected.position.x_m,
            selected.height_m / 2 + 0.2,
            -selected.position.y_m,
          ]}
        >
          <boxGeometry
            args={[
              selected.width_m + 2,
              selected.height_m + 2,
              selected.depth_m + 2,
            ]}
          />
          <meshBasicMaterial
            color="#75ead6"
            transparent
            opacity={0.06}
            depthWrite={false}
          />
          <Edges color="#75ead6" threshold={15} />
        </mesh>
      )}
    </>
  );
}

function Ground({ city, layers }: { city: CityState; layers: Layers }) {
  const streetItems = useMemo(
    () =>
      city.roads.map((r) => ({
        position: [
          (r.start.x_m + r.end.x_m) / 2,
          0.15,
          -(r.start.y_m + r.end.y_m) / 2,
        ] as [number, number, number],
        scale: [
          r.start.x_m === r.end.x_m ? r.width_m : r.length_m,
          0.35,
          r.start.x_m === r.end.x_m ? r.length_m : r.width_m,
        ] as [number, number, number],
        color: "#4d5b5c",
      })),
    [city],
  );
  const markings = useMemo(() => {
    const result: Instance[] = [];
    for (const r of city.roads)
      for (let d = 12; d < r.length_m - 12; d += 18) {
        const t = d / r.length_m;
        const x = r.start.x_m + (r.end.x_m - r.start.x_m) * t,
          y = r.start.y_m + (r.end.y_m - r.start.y_m) * t;
        result.push({
          position: [x, 0.37, -y],
          scale: r.start.x_m === r.end.x_m ? [0.6, 0.04, 6] : [6, 0.04, 0.6],
          color: "#afbbb2",
        });
      }
    return result;
  }, [city]);
  return (
    <>
      <mesh position={[0, -9, 0]} receiveShadow>
        <boxGeometry
          args={[city.city.width_m + 8, 14, city.city.depth_m + 8]}
        />
        <meshStandardMaterial color="#394b49" roughness={0.9} />
      </mesh>
      {[-1, 1].map((side) => (
        <mesh
          key={side}
          position={[0, -0.5, (side * (city.city.depth_m + 34)) / 4]}
          receiveShadow
        >
          <boxGeometry
            args={[city.city.width_m, 1, (city.city.depth_m - 34) / 2]}
          />
          <meshStandardMaterial color="#88958a" roughness={1} />
        </mesh>
      ))}
      {city.rivers.map((r) => (
        <group key={r.id}>
          <mesh position={[0, r.surface_elevation_m, -r.start.y_m]}>
            <boxGeometry args={[r.end.x_m - r.start.x_m, 0.3, r.width_m]} />
            <meshStandardMaterial
              color="#326977"
              roughness={0.29}
              metalness={0.25}
            />
          </mesh>
          {[-1, 1].map((s) => (
            <mesh
              key={s}
              position={[0, 0.1, s * (r.width_m / 2 + 2)]}
              receiveShadow
            >
              <boxGeometry args={[660, 2, 3]} />
              <meshStandardMaterial color="#b0b7ab" />
            </mesh>
          ))}
        </group>
      ))}
      <Batch items={streetItems} />
      <Batch items={markings} />
      {city.bridges.map((b) => (
        <group key={b.id} position={toScene(b.position)}>
          <mesh receiveShadow>
            <boxGeometry args={[b.width_m + 1, 0.4, b.length_m]} />
            <meshStandardMaterial color="#879391" />
          </mesh>
          {[-1, 1].map((s) => (
            <mesh key={s} position={[s * (b.width_m / 2), 1.2, 0]}>
              <boxGeometry args={[0.7, 1.8, b.length_m]} />
              <meshStandardMaterial color="#b4c5bd" />
            </mesh>
          ))}
        </group>
      ))}
      {layers.greenery &&
        city.green_areas.map((park) => (
          <group key={park.id}>
            <mesh
              position={[park.position.x_m, 0.12, -park.position.y_m]}
              receiveShadow
            >
              <boxGeometry args={[park.width_m, 0.3, park.depth_m]} />
              <meshStandardMaterial color="#6d896b" />
            </mesh>
            {park.trees.map((p, i) => (
              <group key={i} position={toScene(p)}>
                <mesh position={[0, 2.5, 0]} castShadow>
                  <cylinderGeometry args={[0.6, 1, 5, 5]} />
                  <meshStandardMaterial color="#656b52" />
                </mesh>
                <mesh position={[0, 7, 0]} castShadow>
                  <icosahedronGeometry args={[4.8, 1]} />
                  <meshStandardMaterial
                    color={i % 2 ? "#41685b" : "#52775e"}
                    roughness={1}
                  />
                </mesh>
              </group>
            ))}
          </group>
        ))}
      {layers.districts &&
        city.districts.map((d) => {
          const x = d.center.x_m,
            z = -d.center.y_m,
            w = d.width_m / 2,
            h = d.depth_m / 2;
          return (
            <Line
              key={d.id}
              points={[
                [x - w, 1, z - h],
                [x + w, 1, z - h],
                [x + w, 1, z + h],
                [x - w, 1, z + h],
                [x - w, 1, z - h],
              ]}
              color="#b7ded0"
              transparent
              opacity={0.6}
              lineWidth={1}
              dashed
              dashSize={5}
              gapSize={5}
            />
          );
        })}
      {layers.facilities &&
        city.buildings
          .filter((b) => b.use === "hospital" || b.use === "shelter")
          .map((b) => (
            <group
              key={b.id}
              position={[b.position.x_m, b.height_m + 3.5, -b.position.y_m]}
            >
              <mesh>
                <boxGeometry args={[12, 0.3, 4]} />
                <meshBasicMaterial
                  color={b.use === "hospital" ? "#eddfd2" : "#82e3c9"}
                />
              </mesh>
              <mesh>
                <boxGeometry args={[4, 0.3, 12]} />
                <meshBasicMaterial
                  color={b.use === "hospital" ? "#eddfd2" : "#82e3c9"}
                />
              </mesh>
            </group>
          ))}
      {layers.units &&
        city.rescue_units.map((unit) => (
          <group key={unit.id} position={toScene(unit.position)}>
            <mesh position={[0, 1.8, 0]} castShadow>
              <boxGeometry
                args={[
                  unit.type === "boat" ? 4 : 3.8,
                  3.2,
                  unit.type === "boat" ? 9 : 7,
                ]}
              />
              <meshStandardMaterial
                color={unit.type === "ambulance" ? "#e1e0cc" : "#d2a765"}
              />
            </mesh>
            <mesh position={[0, 3.8, 0]}>
              <boxGeometry args={[2.6, 0.5, 1.2]} />
              <meshBasicMaterial color="#69d9cb" />
            </mesh>
          </group>
        ))}
    </>
  );
}

function Camera({
  target,
  action,
}: {
  target: Building | null;
  action: { type: string; key: number };
}) {
  const controls = useRef<OrbitControlsImpl>(null);
  const { camera, invalidate, size, gl } = useThree();
  const lastCommand = useRef("");
  useEffect(() => {
    const control = controls.current;
    if (!control) return;
    gl.domElement.tabIndex = 0;
    gl.domElement.setAttribute(
      "aria-label",
      "Interactive city. Drag to orbit, scroll to zoom, arrow keys or right-drag to pan. Building inventory provides keyboard selection.",
    );
    control.listenToKeyEvents(gl.domElement);
    return () => control.stopListenToKeyEvents();
  }, [gl]);
  useLayoutEffect(() => {
    if (!controls.current) return;
    const commandKey = `${action.key}:${size.width}:${size.height}`;
    if (lastCommand.current === commandKey) return;
    lastCommand.current = commandKey;
    if (action.type === "focus" && target) {
      const center = new Vector3(
        target.position.x_m,
        target.height_m / 2,
        -target.position.y_m,
      );
      controls.current.target.copy(center);
      camera.position.copy(center.clone().add(new Vector3(220, 220, 240)));
      camera.zoom = 2;
    } else if (action.type === "zoom-in")
      camera.zoom = Math.min(4, camera.zoom * 1.2);
    else if (action.type === "zoom-out")
      camera.zoom = Math.max(0.4, camera.zoom / 1.2);
    else if (action.type === "reset") {
      camera.position.set(600, 600, 680);
      camera.zoom = Math.min(size.width / 880, size.height / 620) * 0.95;
      controls.current.target.set(0, 0, 0);
    }
    camera.updateProjectionMatrix();
    controls.current.update();
    invalidate();
  }, [action, camera, target, invalidate, size]);
  return (
    <OrbitControls
      ref={controls}
      makeDefault
      minZoom={0.4}
      maxZoom={4}
      maxPolarAngle={Math.PI / 2.2}
      minPolarAngle={0.15}
      enableDamping={false}
    />
  );
}

class SceneBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

export default function CityScene({
  city,
  selected,
  onSelect,
  layers,
  lowGraphics,
}: {
  city: CityState;
  selected: Building | null;
  onSelect: (id: string) => void;
  layers: Layers;
  lowGraphics: boolean;
}) {
  const [action, setAction] = useState({ type: "reset", key: 0 });
  const [mapMode, setMapMode] = useState(false);
  const command = (type: string) =>
    setAction((a) => ({ type, key: a.key + 1 }));
  const fallback = (
    <div className="map-fallback">
      <View size={30} />
      <h3>City inventory view</h3>
      <p>
        Choose a building to inspect its backend state. Switch to 3D when WebGL
        is available.
      </p>
      <div className="building-list">
        {city.buildings.map((b) => (
          <button
            key={b.id}
            onClick={() => onSelect(b.id)}
            aria-pressed={selected?.id === b.id}
          >
            {b.name}
            <span>
              {b.floors} floors · {b.use}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
  return (
    <div className="city-scene" data-testid="city-viewport">
      {mapMode ? (
        fallback
      ) : (
        <SceneBoundary fallback={fallback}>
          <Suspense
            fallback={
              <div className="scene-loading">Preparing city geometry…</div>
            }
          >
            <Canvas
              orthographic
              camera={{
                position: [600, 600, 680],
                zoom: 0.9,
                near: 1,
                far: 3000,
              }}
              frameloop="demand"
              shadows={lowGraphics ? false : { type: PCFShadowMap }}
              dpr={lowGraphics ? 1 : [1, 1.5]}
              gl={{ antialias: true, powerPreference: "high-performance" }}
            >
              <color attach="background" args={["#243633"]} />
              <ambientLight intensity={1.2} color="#c8e0db" />
              <directionalLight
                position={[-180, 380, -220]}
                intensity={3}
                castShadow={!lowGraphics}
                shadow-mapSize={[2048, 2048]}
                shadow-camera-left={-450}
                shadow-camera-right={450}
                shadow-camera-top={450}
                shadow-camera-bottom={-450}
                shadow-camera-far={1200}
                shadow-bias={-0.001}
              />
              <Ground city={city} layers={layers} />
              {layers.buildings && (
                <BuildingBlocks
                  city={city}
                  selected={selected}
                  onSelect={onSelect}
                />
              )}
              <Camera target={selected} action={action} />
            </Canvas>
          </Suspense>
        </SceneBoundary>
      )}
      <div className="map-location">
        <span className="live-dot" /> RIVERSIDE <span>/ FICTIONAL CITY</span>
      </div>
      <div className="map-coordinate">
        LOCAL GRID · METERS
        <span>
          SEED {city.city.seed} / V{city.scenario.state_version}
        </span>
      </div>
      <div className="scene-tools" aria-label="Camera controls">
        <button
          title="Reset isometric camera"
          aria-label="Reset camera"
          onClick={() => command("reset")}
          disabled={mapMode}
        >
          <RotateCcw size={16} />
        </button>
        <button
          title="Zoom in"
          aria-label="Zoom in"
          onClick={() => command("zoom-in")}
          disabled={mapMode}
        >
          <Plus size={17} />
        </button>
        <button
          title="Zoom out"
          aria-label="Zoom out"
          onClick={() => command("zoom-out")}
          disabled={mapMode}
        >
          <Minus size={17} />
        </button>
        <button
          title="Focus selected building"
          aria-label="Focus selected building"
          onClick={() => command("focus")}
          disabled={!selected || mapMode}
        >
          <Focus size={17} />
        </button>
        <button
          title="Switch between 3D and accessible building inventory"
          aria-label={mapMode ? "Show 3D city" : "Show building inventory"}
          aria-pressed={mapMode}
          onClick={() => setMapMode(!mapMode)}
        >
          <View size={17} />
        </button>
      </div>
      <div className="map-compass">
        <Compass size={28} />
        <span>N</span>
      </div>
      <div className="scene-hint">
        {mapMode
          ? "Select a building from the inventory"
          : "Drag to orbit · Scroll to zoom · Right-drag to pan"}
      </div>
      <div className="map-scale">
        <i /> 100 m
      </div>
    </div>
  );
}
