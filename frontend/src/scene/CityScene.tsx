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
import { Canvas, type ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import { Edges, Line, OrbitControls } from "@react-three/drei";
import { useReducedMotion } from "motion/react";
import {
  BoxGeometry,
  BufferGeometry,
  Color,
  ConeGeometry,
  CylinderGeometry,
  DoubleSide,
  Float32BufferAttribute,
  InstancedMesh,
  Matrix4,
  MeshStandardMaterial,
  PCFShadowMap,
  type Group,
  Vector3,
} from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { Compass, Focus, Minus, Plus, RotateCcw, View } from "lucide-react";
import type { Building, CityState, ScenarioState } from "../api/client";
import type { ScenarioPredictionSet } from "../api/client";
import type { Mission, MissionUnitResource } from "../api/client";
import { toScene } from "./coordinates";
import { sampleMissionRoute, type MissionRouteGeometry } from "./missionPath";
import { buildingVisualProfile, floodSurfaceColor, floodSurfaceOpacity, terrainSampleGrid } from "./visualData";

export type Layers = {
  buildings: boolean;
  greenery: boolean;
  facilities: boolean;
  districts: boolean;
  units: boolean;
  flood: boolean;
  infrastructure: boolean;
  predictedRisk: boolean;
};
export type HypotheticalRoute = { id: string; points: number[][]; color: string; pointsAreXYZ?:boolean };

type ScenePerformanceSnapshot = {
  capturedAt: string;
  graphicsMode: "standard" | "low";
  sampleCount: number;
  frameIntervalMs: { median: number; p95: number; p99: number };
  estimatedFps: number;
  drawCalls: number;
  triangles: number;
  geometries: number;
  textures: number;
  canvas: { width: number; height: number; devicePixelRatio: number };
  webgl: { version: string; vendor: string | null; renderer: string | null };
};

declare global {
  interface Window { __RESQ_SCENE_METRICS__?: ScenePerformanceSnapshot }
}

function ScenePerformanceProbe({ enabled, lowGraphics }: { enabled: boolean; lowGraphics: boolean }) {
  const { gl } = useThree();
  const frameIntervals = useRef<number[]>([]);
  const lastSample = useRef(0);
  const metricsElement = useRef<HTMLOutputElement | null>(null);
  const webgl = useMemo(() => {
    const context = gl.getContext();
    const extension = context.getExtension("WEBGL_debug_renderer_info") as ({
      UNMASKED_VENDOR_WEBGL: number;
      UNMASKED_RENDERER_WEBGL: number;
    } | null);
    return {
      version: context.getParameter(context.VERSION) as string,
      vendor: extension ? context.getParameter(extension.UNMASKED_VENDOR_WEBGL) as string : null,
      renderer: extension ? context.getParameter(extension.UNMASKED_RENDERER_WEBGL) as string : null,
    };
  }, [gl]);

  useEffect(() => {
    if (!enabled) return;
    const output = document.createElement("output");
    output.id = "resq-scene-performance-metrics";
    output.hidden = true;
    output.dataset.testid = "resq-scene-performance-metrics";
    document.body.append(output);
    metricsElement.current = output;
    return () => {
      output.remove();
      metricsElement.current = null;
      delete window.__RESQ_SCENE_METRICS__;
    };
  }, [enabled]);

  useFrame((_state, delta) => {
    if (!enabled) return;
    const now = performance.now();
    frameIntervals.current.push(delta * 1000);
    if (lastSample.current === 0) lastSample.current = now;
    if (now - lastSample.current < 5000) return;
    const values = frameIntervals.current.slice().sort((a, b) => a - b);
    const percentile = (fraction: number) => values[Math.min(values.length - 1, Math.ceil(values.length * fraction) - 1)] ?? 0;
    const median = percentile(0.5);
    const canvas = gl.domElement;
    const snapshot: ScenePerformanceSnapshot = {
      capturedAt: new Date().toISOString(),
      graphicsMode: lowGraphics ? "low" : "standard",
      sampleCount: values.length,
      frameIntervalMs: { median: Number(median.toFixed(2)), p95: Number(percentile(0.95).toFixed(2)), p99: Number(percentile(0.99).toFixed(2)) },
      estimatedFps: median > 0 ? Number((1000 / median).toFixed(1)) : 0,
      drawCalls: gl.info.render.calls,
      triangles: gl.info.render.triangles,
      geometries: gl.info.memory.geometries,
      textures: gl.info.memory.textures,
      canvas: { width: canvas.width, height: canvas.height, devicePixelRatio: window.devicePixelRatio },
      webgl,
    };
    window.__RESQ_SCENE_METRICS__ = snapshot;
    if (metricsElement.current) metricsElement.current.textContent = JSON.stringify(snapshot);
    frameIntervals.current = [];
    lastSample.current = now;
  });
  return null;
}

function routePointToScene(city: CityState, point: number[]): [number,number,number] {
  const [x,y]=point;
  const ix=city.terrain.x_centers_m.reduce((best,value,index)=>Math.abs(value-x)<Math.abs(city.terrain.x_centers_m[best]-x)?index:best,0);
  const iy=city.terrain.y_centers_m.reduce((best,value,index)=>Math.abs(value-y)<Math.abs(city.terrain.y_centers_m[best]-y)?index:best,0);
  return [x,city.terrain.elevation_m[iy][ix]+1.5,-y];
}
function missionRoutePoints(city:CityState,mission:Mission):[number,number,number][] {
  const xyz=mission.route.polyline_xyz;
  if(Array.isArray(xyz)&&xyz.every(point=>Array.isArray(point)&&point.length>=3&&point.slice(0,3).every(Number.isFinite)))
    return (xyz as number[][]).map(([x,y,z])=>[x,z+1.4,-y]);
  const xy=mission.route.polyline;
  return Array.isArray(xy)?(xy as number[][]).map(point=>routePointToScene(city,point)):[];
}

function MissionVehicle({mission,resource,selected,onSelect,reducedMotion}:{mission:Mission;resource:MissionUnitResource;selected:boolean;onSelect:()=>void;reducedMotion:boolean}) {
  const group=useRef<Group>(null);
  const position=resource.position;
  const displayedDistance=useRef(mission.traversed_distance_m);
  const startDistance=useRef(mission.traversed_distance_m);
  const targetDistance=useRef(mission.traversed_distance_m);
  const elapsed=useRef(1);
  const routeRevision=useRef(mission.route_revision);
  const status=resource.status==="available"?"standby":resource.status==="reserved"?"reserved":resource.status==="blocked"||mission.status==="blocked"?"blocked":resource.status==="at_destination"||mission.status==="arrived"?"arrived":resource.status==="unavailable"&&mission.status==="completed"?"awaiting-return":resource.status;
  const statusColor=status==="blocked"?"#df655b":status==="arrived"?"#65bd93":status==="awaiting-return"?"#d4a959":status==="reserved"?"#69b9ac":"#8aa89b";
  const color=status==="blocked"?"#c95955":status==="arrived"||status==="awaiting-return"?"#78c4a3":mission.unit_type==="ambulance"?"#e5e2d3":"#bd9b69";
  useEffect(()=>{
    const target=mission.traversed_distance_m;
    const revised=routeRevision.current!==mission.route_revision;
    routeRevision.current=mission.route_revision;
    if(mission.status!=="en_route"||revised||reducedMotion){
      displayedDistance.current=target;startDistance.current=target;targetDistance.current=target;elapsed.current=1;
    }else{
      startDistance.current=displayedDistance.current;targetDistance.current=Math.max(displayedDistance.current,target);elapsed.current=0;
    }
  },[mission.traversed_distance_m,mission.status,mission.route_revision,reducedMotion]);
  useFrame((_,delta)=>{
    if(!group.current)return;
    if(mission.status==="en_route"){
      elapsed.current=Math.min(1,elapsed.current+delta/.62);
      const eased=elapsed.current*elapsed.current*(3-2*elapsed.current);
      displayedDistance.current=startDistance.current+(targetDistance.current-startDistance.current)*eased;
    }else displayedDistance.current=mission.traversed_distance_m;
    const sample=sampleMissionRoute(mission.route as unknown as MissionRouteGeometry,displayedDistance.current);
    if(sample){
      group.current.position.set(sample.position[0],sample.position[1]+.4,sample.position[2]);
      group.current.rotation.y=sample.yaw;
    }else group.current.position.set(position.x_m,(position.elevation_m??0)+.4,-position.y_m);
  });
  return <group ref={group} position={[position.x_m,(position.elevation_m??0)+.4,-position.y_m]}
    onClick={event=>{event.stopPropagation();onSelect();}}>
    <mesh position={[0,.04,0]} rotation={[-Math.PI/2,0,0]}>
      <torusGeometry args={[selected?4.2:3.4,.12,6,28]}/>
      <meshBasicMaterial color={selected?"#91e3d1":statusColor} transparent opacity={selected ? .88 : .52}/>
    </mesh>
    <group position={[0,.35,0]}>
      <mesh castShadow position={[0,.5,0]}><boxGeometry args={[2.15,1.25,4.8]}/><meshStandardMaterial color={color} roughness={.55} metalness={.16}/></mesh>
      <mesh position={[0,1.13,-.05]}><boxGeometry args={[1.72,.58,2.25]}/><meshStandardMaterial color={mission.unit_type==="ambulance"?"#d9e2df":"#35434a"} roughness={.35} metalness={.2}/></mesh>
      {mission.unit_type==="ambulance"&&<mesh position={[0,.64,-.65]}><boxGeometry args={[2.19,.24,.32]}/><meshStandardMaterial color="#bc5b55" roughness={.62}/></mesh>}
      {[-1,1].map(side=>[-1.45,1.45].map(z=><mesh key={`${side}:${z}`} position={[side*1.1,.32,z]} rotation={[0,0,Math.PI/2]}><cylinderGeometry args={[.39,.39,.2,12]}/><meshStandardMaterial color="#252b2c" roughness={.9}/></mesh>))}
      {(mission.status==="en_route"||mission.status==="blocked")&&<group position={[0,1.52,-.18]}>
        <mesh><boxGeometry args={[.78,.16,.32]}/><meshStandardMaterial color="#d8615c" emissive="#6f211e" emissiveIntensity={.32}/></mesh>
        <mesh position={[.28,.02,0]}><boxGeometry args={[.14,.09,.34]}/><meshStandardMaterial color="#7aabcf" emissive="#315b7b" emissiveIntensity={.18}/></mesh>
      </group>}
      <mesh position={[0,1.82,0]}><sphereGeometry args={[status==="blocked"?.25:.18,10,8]}/><meshBasicMaterial color={statusColor}/></mesh>
    </group>
  </group>;
}
type Instance = {
  position: [number, number, number];
  scale: [number, number, number];
  color: string;
  id?: string;
};
const box = new BoxGeometry(1, 1, 1);
const surface = new MeshStandardMaterial({ roughness: 0.82, metalness: 0.05 });
const facadeSurface = new MeshStandardMaterial({ roughness: 0.88, metalness: 0.02 });
const windowSurface = new MeshStandardMaterial({ roughness: 0.3, metalness: 0.12 });
const gableRoof = (() => {
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute([
    -0.5,0,-0.5, 0.5,0,-0.5, 0,1,-0.5,
    -0.5,0,0.5, 0.5,0,0.5, 0,1,0.5,
  ], 3));
  geometry.setIndex([0,2,1, 0,3,5,0,5,2, 2,5,4,2,4,1, 0,1,4,0,4,3, 3,4,5]);
  geometry.computeVertexNormals();
  return geometry;
})();
const gableSurface = new MeshStandardMaterial({ roughness: 0.9, side: DoubleSide });
const trunkGeometry = new CylinderGeometry(0.42,0.72,4.8,6);
const canopyGeometry = new ConeGeometry(4.2,8.2,7,1);
const foliageSurface = new MeshStandardMaterial({ roughness: 1 });
const trunkSurface = new MeshStandardMaterial({ roughness: 0.95 });

function Batch({
  items,
  onSelect,
  shadows = false,
  geometry = box,
  material = surface,
}: {
  items: Instance[];
  onSelect?: (id: string) => void;
  shadows?: boolean;
  geometry?: BufferGeometry;
  material?: MeshStandardMaterial;
}) {
  const ref = useRef<InstancedMesh>(null);
  useLayoutEffect(() => {
    const mesh = ref.current;
    if (!mesh) return;
    const transform = new Matrix4();
    const tint = new Color();
    items.forEach((item, index) => {
      transform.makeScale(...item.scale).setPosition(...item.position);
      mesh.setMatrixAt(index, transform);
      mesh.setColorAt(index, tint.set(item.color));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.computeBoundingSphere();
  }, [items]);
  if (!items.length) return null;
  return (
    <instancedMesh
      ref={ref}
      args={[geometry, material, items.length]}
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
  scenario,
  onSelect,
  selected,
  predictions,
  showPredictions,
  lowGraphics,
}: {
  city: CityState;
  scenario: ScenarioState | null;
  onSelect: (id: string) => void;
  selected: Building | null;
  predictions: ScenarioPredictionSet | null;
  showPredictions: boolean;
  lowGraphics: boolean;
}) {
  const batches = useMemo(() => {
    const walls: Instance[] = [], plinths: Instance[] = [], flatRoofs: Instance[] = [],
      gableRoofs: Instance[] = [], parapets: Instance[] = [], windows: Instance[] = [],
      equipment: Instance[] = [], doors: Instance[] = [], awnings: Instance[] = [],
      facadeTrim: Instance[] = [], hospitalMarks: Instance[] = [], shelterMarks: Instance[] = [];
    const exposureById = new Map((scenario?.impacts.buildings ?? []).map((item) => [item.entity_id, item]));
    const predictedIds = new Set(showPredictions ? (predictions?.predictions ?? []).filter((p) => p.predicted_future_exposed).map((p) => p.building_id) : []);
    for (const b of city.buildings) {
      const [x, y, z] = toScene(b.position);
      const profile = buildingVisualProfile(b);
      const exposure = exposureById.get(b.id);
      const predicted = predictedIds.has(b.id);
      const color = predicted
        ? "#ef8a58"
        : exposure?.category === "severe"
          ? "#b48b72"
          : exposure?.category === "moderate"
            ? "#b1a084"
            : profile.wall;
      const buildingId = b.id;
      plinths.push({ position:[x,y+0.28,z],scale:[b.width_m+1.1,.56,b.depth_m+1.1],color:profile.trim,id:buildingId });
      walls.push({
        position: [x, y + b.height_m / 2, z],
        scale: [b.width_m, b.height_m, b.depth_m],
        color,
        id: buildingId,
      });
      const pitchedHome=profile.form==="home"&&b.floors<=2;
      if(pitchedHome){
        gableRoofs.push({position:[x,y+b.height_m,z],scale:[b.width_m+1.2,Math.min(4.2,2.2+b.width_m*.04),b.depth_m+1.2],color:profile.roof,id:buildingId});
      }else{
        flatRoofs.push({position:[x,y+b.height_m+.65,z],scale:[b.width_m+1.1,1.3,b.depth_m+1.1],color:profile.roof,id:buildingId});
        if(!lowGraphics){
          const parapetY=y+b.height_m+1.65;
          parapets.push({position:[x,parapetY,z-(b.depth_m+1.1)/2],scale:[b.width_m+1.1,.52,.26],color:profile.trim,id:buildingId});
          parapets.push({position:[x,parapetY,z+(b.depth_m+1.1)/2],scale:[b.width_m+1.1,.52,.26],color:profile.trim,id:buildingId});
          parapets.push({position:[x-(b.width_m+1.1)/2,parapetY,z],scale:[.26,.52,b.depth_m+1.1],color:profile.trim,id:buildingId});
          parapets.push({position:[x+(b.width_m+1.1)/2,parapetY,z],scale:[.26,.52,b.depth_m+1.1],color:profile.trim,id:buildingId});
        }
      }
      equipment.push({
        position: [x - b.width_m * 0.2, y + b.height_m + (pitchedHome?2.5:2.25), z],
        scale: [Math.max(1.4,b.width_m * (profile.form==="commercial"?.22:.18)), profile.form==="home"?2.4:1.6, Math.max(1.6,b.depth_m * .2)],
        color: profile.form==="home"?"#756d60":"#8d9a96",
        id: buildingId,
      });
      if(!lowGraphics){
        const doorW=Math.min(2,b.width_m*.24), doorH=Math.min(3.1,b.height_m*.16);
        doors.push({position:[x,y+doorH/2,z-b.depth_m/2-.05],scale:[doorW,doorH,.16],color:profile.entrance,id:buildingId});
        awnings.push({position:[x,y+doorH+.2,z-b.depth_m/2-.34],scale:[doorW+1,.35,.8],color:profile.trim,id:buildingId});
        for(const sx of [-1,1]) for(const sz of [-1,1])
          facadeTrim.push({position:[x+sx*(b.width_m/2-.2),y+b.height_m/2,z+sz*(b.depth_m/2-.2)],scale:[.32,b.height_m,.32],color:profile.trim,id:buildingId});
      }
      if(b.use==="hospital"){
        hospitalMarks.push({position:[x,y+b.height_m+3.1,z],scale:[4,.4,1.05],color:"#f4eee0",id:buildingId});
        hospitalMarks.push({position:[x,y+b.height_m+3.1,z],scale:[1.05,.4,4],color:"#f4eee0",id:buildingId});
        hospitalMarks.push({position:[x,y+b.height_m+3.38,z],scale:[1.5,.18,1.5],color:profile.trim,id:buildingId});
      }
      if(b.use==="shelter"){
        shelterMarks.push({position:[x,y+b.height_m+2.5,z],scale:[4,.3,4],color:"#e4eee3",id:buildingId});
        shelterMarks.push({position:[x,y+b.height_m+2.76,z],scale:[2.6,.3,.6],color:profile.trim,id:buildingId});
        shelterMarks.push({position:[x,y+b.height_m+2.76,z],scale:[.6,.3,2.6],color:profile.trim,id:buildingId});
      }
      for (let floor = 0; floor < b.floors; floor++) {
        const wy = y + floor * 3.6 + 2;
        for (let column = -1; column <= 1; column += lowGraphics?2:1) {
          const tint = (floor + column) % 3 === 0 ? "#b9cbc2" : profile.window;
          windows.push({
            position: [
              x + column * b.width_m * 0.27,
              wy,
              z + b.depth_m / 2 + 0.08,
            ],
            scale: [b.width_m * 0.16, 1.5, 0.2],
            color: tint,
            id: buildingId,
          });
          windows.push({
            position: [
              x + b.width_m / 2 + 0.08,
              wy,
              z + column * b.depth_m * 0.27,
            ],
            scale: [0.2, 1.5, b.depth_m * 0.16],
            color: tint,
            id: buildingId,
          });
          windows.push({
            position: [
              x + column * b.width_m * 0.27,
              wy,
              z - b.depth_m / 2 - 0.08,
            ],
            scale: [b.width_m * 0.16, 1.5, 0.2],
            color: tint,
            id: buildingId,
          });
          windows.push({
            position: [
              x - b.width_m / 2 - 0.08,
              wy,
              z + column * b.depth_m * 0.27,
            ],
            scale: [0.2, 1.5, b.depth_m * 0.16],
            color: tint,
            id: buildingId,
          });
        }
      }
    }
    return { walls, plinths, flatRoofs, gableRoofs, parapets, windows, equipment, doors, awnings, facadeTrim, hospitalMarks, shelterMarks };
  }, [city, scenario, predictions, showPredictions, lowGraphics]);
  return (
    <>
      <Batch items={batches.walls} onSelect={onSelect} shadows />
      <Batch items={batches.plinths} material={facadeSurface} />
      <Batch items={batches.flatRoofs} />
      <Batch items={batches.gableRoofs} geometry={gableRoof} material={gableSurface} />
      <Batch items={batches.parapets} material={facadeSurface} />
      <Batch items={batches.equipment} onSelect={onSelect} shadows />
      <Batch items={batches.windows} material={windowSurface} />
      <Batch items={batches.doors} material={facadeSurface} />
      <Batch items={batches.awnings} material={facadeSurface} />
      <Batch items={batches.facadeTrim} material={facadeSurface} />
      <Batch items={batches.hospitalMarks} material={facadeSurface} />
      <Batch items={batches.shelterMarks} material={facadeSurface} />
      {selected && (
        <mesh
          position={[
            selected.position.x_m,
            selected.position.elevation_m + selected.height_m / 2 + 0.2,
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

function sampleGrid(grid: number[][], x: number, y: number) { return terrainSampleGrid(grid,x,y); }

function terrainGeometry(grid: number[][], lowGraphics: boolean) {
  const geometry = new BufferGeometry();
  const rows = grid.length, columns = grid[0]?.length ?? 0;
  const positions: number[] = [], colors: number[] = [], indices: number[] = [];
  const subdivisions=lowGraphics?1:2;
  const rowCount=rows*subdivisions, columnCount=columns*subdivisions;
  const elevations=grid.flat();
  const minimum=Math.min(...elevations), maximum=Math.max(...elevations);
  const low=new Color("#687b65"), high=new Color("#898775"), tint=new Color();
  for (let row = 0; row <= rowCount; row++) {
    const northing = 250 - row * (20/subdivisions);
    for (let column = 0; column <= columnCount; column++) {
      const east = -330 + column * (20/subdivisions);
      positions.push(east, sampleGrid(grid, east, northing), -northing);
      const ratio=(sampleGrid(grid,east,northing)-minimum)/Math.max(maximum-minimum,.001);
      tint.copy(low).lerp(high,Math.min(.82,Math.max(.04,ratio)));
      colors.push(tint.r,tint.g,tint.b);
      if (row < rowCount && column < columnCount) {
        const a = row * (columnCount + 1) + column;
        const b = a + 1, c = a + columnCount + 1, d = c + 1;
        indices.push(a, c, b, b, c, d);
      }
    }
  }
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color",new Float32BufferAttribute(colors,3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

function floodGeometry(terrain: number[][], depth: number[][]) {
  const geometry = new BufferGeometry();
  const positions: number[] = [], colors: number[] = [], indices: number[] = [];
  const tint=new Color();
  for (let row = 0; row < depth.length; row++) {
    for (let column = 0; column < depth[row].length; column++) {
      const level = depth[row][column];
      if (level < 0.025) continue;
      const x = -320 + column * 20, north = -240 + row * 20;
      const points: [number, number][] = [[x - 10, north - 10], [x + 10, north - 10], [x + 10, north + 10], [x - 10, north + 10]];
      tint.set(floodSurfaceColor(level));
      const first = positions.length / 3;
      for (const [east, northing] of points) {
        const base = sampleGrid(terrain, east, northing);
        const water = Math.min(level,Math.max(0,sampleGrid(depth,east,northing)));
        positions.push(east, base + water + 0.025, -northing);
        colors.push(tint.r,tint.g,tint.b,floodSurfaceOpacity(level));
      }
      indices.push(first, first + 1, first + 2, first, first + 2, first + 3);
    }
  }
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new Float32BufferAttribute(colors, 4));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

function Terrain({ grid,lowGraphics }: { grid: number[][]; lowGraphics:boolean }) {
  const geometry = useMemo(() => terrainGeometry(grid,lowGraphics), [grid,lowGraphics]);
  useEffect(() => () => geometry?.dispose(), [geometry]);
  if (!geometry) return null;
  return <mesh geometry={geometry} receiveShadow><meshStandardMaterial vertexColors roughness={0.96}/></mesh>;
}

function Floodwater({ scenario,lowGraphics }: { scenario: ScenarioState | null; lowGraphics:boolean }) {
  const terrain = scenario?.terrain_m;
  const depth = scenario?.depth_m;
  const geometry = useMemo(() => terrain && depth ? floodGeometry(terrain, depth) : null,
    [terrain, depth]);
  useEffect(() => () => geometry?.dispose(), [geometry]);
  if (!geometry || geometry.getAttribute("position").count === 0) return null;
  return <mesh geometry={geometry} renderOrder={2}><meshPhysicalMaterial vertexColors transparent roughness={lowGraphics?.42:.24} metalness={lowGraphics?.08:.18} clearcoat={lowGraphics?.12:.55} clearcoatRoughness={0.22} depthWrite={false}/></mesh>;
}

function Ground({ city, layers, scenario, manualClosureIds, lowGraphics }: { city: CityState; layers: Layers; scenario: ScenarioState | null; manualClosureIds:string[]; lowGraphics:boolean }) {
  const terrain = scenario?.terrain_m ?? city.terrain.elevation_m;
  const roadImpacts = scenario?.impacts.roads;
  const roadsById = useMemo(() => new Map((roadImpacts ?? []).map((impact) => [impact.entity_id, impact])), [roadImpacts]);
  const bridgesById = new Map((scenario?.impacts.bridges ?? []).map((bridge) => [bridge.entity_id, bridge]));
  const streetItems = useMemo(
    () => city.roads.flatMap((road) => {
      const count = Math.ceil(road.length_m / 20);
      const bridge = city.bridges.find((item) => item.road_id === road.id);
      return Array.from({ length: count }, (_, index) => {
        const t0 = index / count, t1 = (index + 1) / count, t = (t0 + t1) / 2;
        const x = road.start.x_m + (road.end.x_m - road.start.x_m) * t;
        const y = road.start.y_m + (road.end.y_m - road.start.y_m) * t;
        if (bridge && Math.abs(y - bridge.position.y_m) <= bridge.length_m / 2) return null;
        const endX = road.start.x_m + (road.end.x_m - road.start.x_m) * t1;
        const endY = road.start.y_m + (road.end.y_m - road.start.y_m) * t1;
        const length = Math.hypot(endX - x, endY - y) + 0.8;
        const elevation = sampleGrid(terrain, x, y) + 0.19;
        const condition = manualClosureIds.includes(road.id) ? "manually_blocked" : roadsById.get(road.id)?.status;
        return {
          position: [x, elevation, -y] as [number, number, number],
          scale: [road.start.x_m === road.end.x_m ? road.width_m : length, 0.3, road.start.x_m === road.end.x_m ? length : road.width_m] as [number, number, number],
          color: condition === "manually_blocked" ? "#d15f52" : condition === "flooded" ? "#28678f" : condition === "caution" ? "#91764e" : "#4d5b5c",
        };
      }).filter((item): item is NonNullable<typeof item> => item !== null);
    }),
    [city, terrain, roadsById, manualClosureIds],
  );
  const markings = useMemo(() => {
    const result: Instance[] = [];
    for (const r of city.roads)
      for (let d = 12; d < r.length_m - 12; d += 18) {
        const t = d / r.length_m;
        const x = r.start.x_m + (r.end.x_m - r.start.x_m) * t,
          y = r.start.y_m + (r.end.y_m - r.start.y_m) * t;
        const bridge = city.bridges.find((item) => item.road_id === r.id);
        if (bridge && Math.abs(y - bridge.position.y_m) <= bridge.length_m / 2) continue;
        const elevation = sampleGrid(terrain, x, y) + 0.37;
        result.push({
          position: [x, elevation, -y],
          scale: r.start.x_m === r.end.x_m ? [0.6, 0.04, 6] : [6, 0.04, 0.6],
          color: "#afbbb2",
        });
      }
    return result;
  }, [city, terrain]);
  const streetFurniture=useMemo(()=>{
    const sidewalks:Instance[]=[],curbs:Instance[]=[],poles:Instance[]=[],lampHeads:Instance[]=[],barriers:Instance[]=[];
    for(const road of city.roads){
      const horizontal=Math.abs(road.end.x_m-road.start.x_m)>=Math.abs(road.end.y_m-road.start.y_m);
      const ux=(road.end.x_m-road.start.x_m)/Math.max(road.length_m,1),uy=(road.end.y_m-road.start.y_m)/Math.max(road.length_m,1);
      const px=-uy,py=ux;
      const bridge=city.bridges.find((item)=>item.road_id===road.id);
      const impact=roadsById.get(road.id);
      const closed=manualClosureIds.includes(road.id)||impact?.status==="closed";
      const step=30,count=Math.ceil(road.length_m/step);
      for(let index=0;index<count;index++){
        const t=(index+.5)/count,x=road.start.x_m+(road.end.x_m-road.start.x_m)*t,y=road.start.y_m+(road.end.y_m-road.start.y_m)*t;
        if(bridge&&Math.abs(y-bridge.position.y_m)<=bridge.length_m/2+step/2)continue;
        const length=road.length_m/count+.3;
        for(const side of [-1,1]){
          const sx=x+px*side*(road.width_m/2+1.5),sy=y+py*side*(road.width_m/2+1.5),elevation=sampleGrid(terrain,sx,sy)+.12;
          sidewalks.push({position:[sx,elevation,-sy],scale:horizontal?[length,.22,2.4]:[2.4,.22,length],color:"#898f86"});
          const cx=x+px*side*(road.width_m/2+.12),cy=y+py*side*(road.width_m/2+.12),curbY=sampleGrid(terrain,cx,cy)+.24;
          curbs.push({position:[cx,curbY,-cy],scale:horizontal?[length,.34,.28]:[.28,.34,length],color:"#b6b4a6"});
        }
      }
      if(!lowGraphics) for(let d=55;d<road.length_m-35;d+=120){
        const t=d/road.length_m,x=road.start.x_m+(road.end.x_m-road.start.x_m)*t,y=road.start.y_m+(road.end.y_m-road.start.y_m)*t;
        if(bridge&&Math.abs(y-bridge.position.y_m)<=bridge.length_m/2+12)continue;
        const side=d%240<120?1:-1,lx=x+px*side*(road.width_m/2+3.7),ly=y+py*side*(road.width_m/2+3.7),base=sampleGrid(terrain,lx,ly);
        poles.push({position:[lx,base+3.2,-ly],scale:[.28,6.4,.28],color:"#374441"});
        lampHeads.push({position:[lx+px*side*.65,base+6.45,-(ly+py*side*.65)],scale:[1.5,.24,.38],color:"#d7d0a7"});
      }
      if(closed){
        const x=(road.start.x_m+road.end.x_m)/2,y=(road.start.y_m+road.end.y_m)/2,elevation=sampleGrid(terrain,x,y)+1.1;
        barriers.push({position:[x,elevation,-y],scale:horizontal?[.38,.34,road.width_m*.76]:[road.width_m*.76,.34,.38],color:"#eee0c7"});
        for(const side of [-1,1]) barriers.push({position:horizontal?[x,elevation,-y+side*road.width_m*.34]:[x+side*road.width_m*.34,elevation,-y],scale:[.32,1.3,.32],color:"#c85c4f"});
      }
    }
    return {sidewalks,curbs,poles,lampHeads,barriers};
  },[city,terrain,roadsById,manualClosureIds,lowGraphics]);
  const treeInstances=useMemo(()=>{
    const trunks:Instance[]=[],canopies:Instance[]=[];
    for(const park of city.green_areas) for(let index=0;index<park.trees.length;index++){
      if(lowGraphics&&index%2)continue;
      const [x,y,z]=toScene(park.trees[index]);
      trunks.push({position:[x,y+2.4,z],scale:[1,1,1],color:index%3===0?"#726652":"#625d4e"});
      canopies.push({position:[x,y+7.4,z],scale:[1+(index%3)*.06,1,1+(index%2)*.08],color:index%3===0?"#486d59":index%3===1?"#5c795b":"#3f6658"});
    }
    return {trunks,canopies};
  },[city,lowGraphics]);
  const bridgeSupports=useMemo(()=>city.bridges.flatMap((bridge)=>[-1,1].map((side)=>{
    const y=bridge.position.y_m+side*bridge.length_m*.34;
    const ground=sampleGrid(terrain,bridge.position.x_m,y),height=Math.max(.8,bridge.position.elevation_m-ground-.35);
    return {position:[bridge.position.x_m,(ground+bridge.position.elevation_m)/2,-y] as [number,number,number],scale:[bridge.width_m*.62,height,bridge.width_m*.62] as [number,number,number],color:"#6d7774"};
  })),[city.bridges,terrain]);
  return (
    <>
      <mesh position={[0, -9, 0]} receiveShadow>
        <boxGeometry
          args={[city.city.width_m + 8, 14, city.city.depth_m + 8]}
        />
        <meshStandardMaterial color="#394b49" roughness={0.9} />
      </mesh>
      <Terrain grid={terrain} lowGraphics={lowGraphics}/>
      {city.rivers.map((r) => (
        <group key={r.id} position={[(r.start.x_m+r.end.x_m)/2,0,-(r.start.y_m+r.end.y_m)/2]} rotation={[0,Math.atan2(r.end.y_m-r.start.y_m,r.end.x_m-r.start.x_m),0]}>
          <mesh position={[0,scenario?.parameters.river_level_m??r.surface_elevation_m,0]}>
            <boxGeometry args={[Math.hypot(r.end.x_m-r.start.x_m,r.end.y_m-r.start.y_m),0.24,r.width_m]} />
            <meshPhysicalMaterial color="#356f7a" roughness={0.28} metalness={0.12} clearcoat={lowGraphics?.08:.3}/>
          </mesh>
          {[-1,1].map((side)=>{
            const offset=r.width_m/2+2.1,dx=r.end.x_m-r.start.x_m,dy=r.end.y_m-r.start.y_m,length=Math.max(Math.hypot(dx,dy),1);
            const bankX=(r.start.x_m+r.end.x_m)/2+dy/length*side*offset;
            const bankY=(r.start.y_m+r.end.y_m)/2-dx/length*side*offset;
            return <mesh key={side} position={[0,sampleGrid(terrain,bankX,bankY)+.72,side*offset]} receiveShadow>
              <boxGeometry args={[length,1.35,2.2]}/>
              <meshStandardMaterial color="#a9a99b" roughness={.86}/>
            </mesh>;
          })}
        </group>
      ))}
      {layers.infrastructure && <Batch items={streetItems} />}
      {layers.infrastructure && <Batch items={markings} />}
      {layers.infrastructure&&<Batch items={streetFurniture.sidewalks} material={facadeSurface}/>}
      {layers.infrastructure&&<Batch items={streetFurniture.curbs} material={facadeSurface}/>}
      {layers.infrastructure&&!lowGraphics&&<Batch items={streetFurniture.poles} material={facadeSurface}/>}
      {layers.infrastructure&&!lowGraphics&&<Batch items={streetFurniture.lampHeads} material={facadeSurface}/>}
      {layers.infrastructure&&<Batch items={streetFurniture.barriers} material={facadeSurface}/>}
      {layers.infrastructure && city.bridges.map((b) => (
        <group key={b.id} position={toScene(b.position)}>
          <mesh receiveShadow>
            <boxGeometry args={[b.width_m + 1, 0.4, b.length_m]} />
            <meshStandardMaterial
              color={manualClosureIds.includes(b.road_id) || bridgesById.get(b.id)?.status === "closed" ? "#d15f52" : "#879391"}
            />
          </mesh>
          {[-1, 1].map((s) => (
            <mesh key={s} position={[s * (b.width_m / 2), 1.2, 0]}>
              <boxGeometry args={[0.7, 1.8, b.length_m]} />
              <meshStandardMaterial color="#b4c5bd" />
            </mesh>
          ))}
        </group>
      ))}
      {layers.infrastructure&&<Batch items={bridgeSupports} material={facadeSurface} shadows={!lowGraphics}/>}
      {layers.greenery &&
        city.green_areas.map((park) => (
          <group key={park.id}>
            <mesh
              position={[park.position.x_m, park.position.elevation_m + 0.12, -park.position.y_m]}
              receiveShadow
            >
              <boxGeometry args={[park.width_m, 0.3, park.depth_m]} />
              <meshStandardMaterial color="#6d896b" />
            </mesh>
          </group>
        ))}
      {layers.greenery&&<Batch items={treeInstances.trunks} geometry={trunkGeometry} material={trunkSurface} shadows={!lowGraphics}/>}
      {layers.greenery&&<Batch items={treeInstances.canopies} geometry={canopyGeometry} material={foliageSurface} shadows={!lowGraphics}/>}
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
              position={[b.position.x_m, b.position.elevation_m + b.height_m + 3.5, -b.position.y_m]}
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
      {layers.flood && <Floodwater scenario={scenario} lowGraphics={lowGraphics}/>}
    </>
  );
}

function Camera({
  target,
  mission,
  action,
  city,
  scenario,
  reducedMotion,
}: {
  target: Building | null;
  mission: Mission | null;
  action: { type: string; key: number };
  city: CityState;
  scenario: ScenarioState | null;
  reducedMotion: boolean;
}) {
  const controls = useRef<OrbitControlsImpl>(null);
  const { camera, invalidate, size, gl } = useThree();
  const lastCommand = useRef("");
  const transition = useRef<{ fromPosition: Vector3; toPosition: Vector3; fromTarget: Vector3; toTarget: Vector3; elapsed: number } | null>(null);
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
  useFrame((_, delta) => {
    const current = transition.current;
    if (!controls.current) return;
    if (current) {
      current.elapsed = reducedMotion ? 1 : Math.min(1, current.elapsed + delta / 0.55);
      const eased = current.elapsed * current.elapsed * (3 - 2 * current.elapsed);
      camera.position.lerpVectors(current.fromPosition, current.toPosition, eased);
      controls.current.target.lerpVectors(current.fromTarget, current.toTarget, eased);
      camera.updateProjectionMatrix();
      controls.current.update();
      if (current.elapsed >= 1) transition.current = null;
      else invalidate();
    }
    if (mission && mission.status === "en_route" && (action.type === "focus-mission" || action.type === "rescue")) {
      const sample = sampleMissionRoute(mission.route as unknown as MissionRouteGeometry, mission.traversed_distance_m);
      if (sample) {
        const desired = new Vector3(sample.position[0], sample.position[1] + 2, sample.position[2]);
        const deltaToUnit = desired.sub(controls.current.target).multiplyScalar(reducedMotion ? 1 : Math.min(1, delta * 2.4));
        controls.current.target.add(deltaToUnit);
        camera.position.add(deltaToUnit);
        controls.current.update();
        invalidate();
      }
    }
  });
  useLayoutEffect(() => {
    if (!controls.current) return;
    const commandKey = `${action.key}:${size.width}:${size.height}`;
    if (lastCommand.current === commandKey) return;
    lastCommand.current = commandKey;
    let center: Vector3 | null = null;
    let offset = new Vector3(220, 220, 240);
    let zoom = camera.zoom;
    if ((action.type === "focus-mission" || action.type === "rescue") && mission) {
      center = new Vector3(mission.position.x_m,(mission.position.elevation_m??0)+2,-mission.position.y_m);
      offset = new Vector3(105,105,125);
      zoom = 2.6;
    } else if (action.type === "focus" && target) {
      center = new Vector3(
        target.position.x_m,
        target.height_m / 2,
        -target.position.y_m,
      );
      zoom = 2;
    } else if (action.type === "hotspot") {
      let maxDepth = -1, row = 0, column = 0;
      scenario?.depth_m.forEach((line, y) => line.forEach((depth, x) => { if (depth > maxDepth) { maxDepth = depth; row = y; column = x; } }));
      if (maxDepth > 0) {
        const x = -320 + column * 20, north = -240 + row * 20;
        center = new Vector3(x, sampleGrid(scenario?.terrain_m ?? city.terrain.elevation_m, x, north) + maxDepth / 2, -north);
      }
      zoom = 1.65;
    } else if (action.type === "bridge" && city.bridges.length) {
      const bridge = city.bridges[0];
      center = new Vector3(bridge.position.x_m, bridge.position.elevation_m, -bridge.position.y_m);
      offset = new Vector3(85, 65, 100);
      zoom = 2.8;
    } else if (action.type === "zoom-in")
      camera.zoom = Math.min(4, camera.zoom * 1.2);
    else if (action.type === "zoom-out")
      camera.zoom = Math.max(0.4, camera.zoom / 1.2);
    else if (action.type === "reset") {
      center = new Vector3(0, 0, 0);
      offset = new Vector3(520, 500, 570);
      zoom = Math.min(size.width / 820, size.height / 570) * 1.05;
    }
    if (center) {
      transition.current = {
        fromPosition: camera.position.clone(),
        toPosition: center.clone().add(offset),
        fromTarget: controls.current.target.clone(),
        toTarget: center,
        elapsed: 0,
      };
      camera.zoom = zoom;
    }
    camera.updateProjectionMatrix();
    controls.current.update();
    invalidate();
  }, [action, camera, target, mission, city, scenario, reducedMotion, invalidate, size]);
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
  scenario,
  selected,
  onSelect,
  layers,
  lowGraphics,
  predictions,
  routeLines,
  manualClosureIds,
  missions,
  missionUnits,
  selectedMissionId,
  onSelectMission,
  hypotheticalRoutes = [],
  hypotheticalClosedRoadIds = [],
  hypotheticalClosedBridgeIds = [],
}: {
  city: CityState;
  scenario: ScenarioState | null;
  selected: Building | null;
  onSelect: (id: string) => void;
  layers: Layers;
  lowGraphics: boolean;
  predictions: ScenarioPredictionSet | null;
  routeLines: number[][][];
  manualClosureIds:string[];
  missions: Mission[];
  missionUnits: MissionUnitResource[];
  selectedMissionId: string | null;
  onSelectMission: (missionId:string)=>void;
  hypotheticalRoutes?:HypotheticalRoute[];
  hypotheticalClosedRoadIds?:string[];
  hypotheticalClosedBridgeIds?:string[];
}) {
  const [action, setAction] = useState({ type: "reset", key: 0 });
  const [mapMode, setMapMode] = useState(false);
  const [lighting, setLighting] = useState<"daylight"|"overcast"|"low-light">("daylight");
  const [rendererCanvas, setRendererCanvas] = useState<HTMLCanvasElement|null>(null);
  const [webglLost, setWebglLost] = useState(false);
  const reducedMotion = useReducedMotion() ?? false;
  const focusedMission=missions.find(item=>item.mission_id===selectedMissionId)??null;
  const focusedResource=focusedMission?missionUnits.find(unit=>unit.unit_id===focusedMission.unit_id):undefined;
  const isMoving=missions.some(item=>item.status==="en_route");
  const performanceProbe=import.meta.env.DEV&&new URLSearchParams(window.location.search).get("perf")==="1";
  const resourceById=new Map(missionUnits.map(item=>[item.unit_id,item]));
  const latestMissionByUnit=new Map<string,Mission>();
  for(const mission of missions)latestMissionByUnit.set(mission.unit_id,mission);
  useEffect(()=>{
    if(!rendererCanvas)return;
    const handleLost=(event:Event)=>{event.preventDefault();setWebglLost(true);};
    const handleRestored=()=>setWebglLost(false);
    rendererCanvas.addEventListener("webglcontextlost",handleLost);
    rendererCanvas.addEventListener("webglcontextrestored",handleRestored);
    return ()=>{
      rendererCanvas.removeEventListener("webglcontextlost",handleLost);
      rendererCanvas.removeEventListener("webglcontextrestored",handleRestored);
    };
  },[rendererCanvas]);
  useEffect(()=>{
    if(selectedMissionId)setAction(current=>({type:"focus-mission",key:current.key+1}));
  },[selectedMissionId]);
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
              frameloop={isMoving||performanceProbe?"always":"demand"}
              camera={{
                position: [520, 500, 570],
                zoom: 0.9,
                near: 1,
                far: 3000,
              }}
              shadows={lowGraphics ? false : { type: PCFShadowMap }}
              dpr={lowGraphics ? 1 : [1, 1.5]}
              gl={{ antialias: true, powerPreference: "high-performance" }}
              onCreated={({gl})=>setRendererCanvas(gl.domElement)}
            >
              <ScenePerformanceProbe enabled={performanceProbe} lowGraphics={lowGraphics} />
              <color attach="background" args={[lighting==="low-light"?"#121c24":lighting==="overcast"?"#344047":"#243633"]} />
              <ambientLight intensity={lighting==="low-light"?.72:lighting==="overcast"?1.55:1.2} color={lighting==="low-light"?"#9cb2c1":lighting==="overcast"?"#d6e0e4":"#c8e0db"} />
              <directionalLight
                position={[-180, 380, -220]}
                intensity={lighting==="low-light"?1.4:lighting==="overcast"?2.0:3}
                castShadow={!lowGraphics}
                shadow-mapSize={[2048, 2048]}
                shadow-camera-left={-450}
                shadow-camera-right={450}
                shadow-camera-top={450}
                shadow-camera-bottom={-450}
                shadow-camera-far={1200}
                shadow-bias={-0.001}
              />
              <Ground city={city} layers={layers} scenario={scenario} manualClosureIds={manualClosureIds} lowGraphics={lowGraphics} />
              {routeLines.map((route,index)=><Line key={`planned-route-${index}`} points={route.map(point=>routePointToScene(city,point))} color="#57d7cf" lineWidth={3} transparent opacity={0.9}/>) }
              {hypotheticalRoutes.map((route)=><Line key={`hypothetical-${route.id}`} points={route.points.map(point=>route.pointsAreXYZ&&point.length>=3?[point[0],point[2]+1.4,-point[1]] as [number,number,number]:routePointToScene(city,point))} color={route.color} lineWidth={3.5} dashed dashSize={5} gapSize={2} transparent opacity={0.94}/>) }
              {city.roads.filter(road=>hypotheticalClosedRoadIds.includes(road.id)).map(road=><Line key={`hypothetical-road-closure-${road.id}`} points={[road.start,road.end].map(point=>routePointToScene(city,[point.x_m,point.y_m]))} color="#f2aa5b" lineWidth={5} dashed dashSize={3} gapSize={2} transparent opacity={0.95}/>) }
              {city.bridges.filter(bridge=>hypotheticalClosedBridgeIds.includes(bridge.id)).map(bridge=>{
                const road=city.roads.find(item=>item.id===bridge.road_id);
                if(!road)return null;
                const dx=road.end.x_m-road.start.x_m,dy=road.end.y_m-road.start.y_m,length=Math.max(Math.hypot(dx,dy),1);
                const half=bridge.length_m/2;
                return <Line key={`hypothetical-bridge-closure-${bridge.id}`} points={[[bridge.position.x_m-dx/length*half,bridge.position.elevation_m+1.8,-(bridge.position.y_m-dy/length*half)],[bridge.position.x_m+dx/length*half,bridge.position.elevation_m+1.8,-(bridge.position.y_m+dy/length*half)]]} color="#ff765f" lineWidth={7} dashed dashSize={2} gapSize={1.5} transparent opacity={0.98}/>;
              })}
              {missions.filter(mission=>mission.status==="ready"||mission.status==="en_route"||mission.status==="blocked"||mission.status==="arrived"||mission.mission_id===selectedMissionId).map(mission=>{
                const points=missionRoutePoints(city,mission);
                if(points.length<2)return null;
                const color=mission.status==="blocked"?"#e36c65":mission.mission_id===selectedMissionId?"#9ce1cf":"#56bcb0";
                const last=points[points.length-1];
                return <group key={`mission-route-${mission.mission_id}`}>
                  <Line points={points} color={color} lineWidth={mission.mission_id===selectedMissionId?4:2.2} transparent opacity={mission.status==="ready" ? .46 : .82}/>
                  <mesh position={last} rotation={[-Math.PI/2,0,0]}><torusGeometry args={[3.6,.22,8,24]}/><meshBasicMaterial color={color}/></mesh>
                </group>;
              })}
              {layers.buildings && (
                <BuildingBlocks
                  city={city}
                  scenario={scenario}
                  selected={selected}
                  onSelect={onSelect}
                  predictions={predictions}
                  showPredictions={layers.predictedRisk}
                  lowGraphics={lowGraphics}
                />
              )}
              {layers.units&&missionUnits.map(resource=>{
                const mission=resource.mission_id?missions.find(item=>item.mission_id===resource.mission_id):latestMissionByUnit.get(resource.unit_id);
                if(!mission)return null;
                return <MissionVehicle key={`mission-unit-${resource.unit_id}`} mission={mission} resource={resource} selected={mission.mission_id===selectedMissionId} reducedMotion={reducedMotion} onSelect={()=>onSelectMission(mission.mission_id)}/>;
              })}
              {layers.units&&city.rescue_units.filter(unit=>!resourceById.has(unit.id)).map(unit=>(
                <group key={unit.id} position={toScene(unit.position)}>
                  <mesh position={[0,1.8,0]} castShadow><boxGeometry args={[unit.type==="boat"?4:2.8,1.65,unit.type==="boat"?9:5.8]}/><meshStandardMaterial color={unit.type==="ambulance"?"#deded1":"#b99a67"} roughness={.68}/></mesh>
                  <mesh position={[0,2.8,0]}><boxGeometry args={[1.2,.14,.45]}/><meshBasicMaterial color="#73bfa9"/></mesh>
                </group>
              ))}
              <Camera target={selected} mission={focusedMission} action={action} city={city} scenario={scenario} reducedMotion={reducedMotion} />
            </Canvas>
          </Suspense>
        </SceneBoundary>
      )}
      {webglLost&&<div className="scene-renderer-status" role="alert">3D graphics paused after a graphics context reset. Use the building inventory control or wait while the browser restores the scene.</div>}
      <div className="map-location">
        <span className="live-dot" /> RIVERSIDE <span>/ FICTIONAL CITY</span>
      </div>
      {focusedMission&&<div className={`scene-mission-status status-${focusedMission.status}`} aria-live="polite">UNIT {focusedMission.unit_id} · {focusedMission.status.replaceAll("_"," ").toUpperCase()} · {focusedMission.status==="ready"?"RESERVED":focusedMission.status==="completed"?focusedResource?.status==="available"?"RETURNED TO SERVICE":"AWAITING RETURN-TO-SERVICE":focusedMission.status==="en_route"?"DISPATCHED":"MISSION STATE"}</div>}
      <div className="map-coordinate">
        LOCAL GRID · METERS
        <span>
          SEED {city.city.seed} / V{city.scenario.state_version}
        </span>
      </div>
      <div className="scene-tools" aria-label="Camera controls">
        <select aria-label="Camera preset" value="" onChange={(event)=>event.target.value&&command(event.target.value)} disabled={mapMode}>
          <option value="" disabled>Camera preset</option>
          <option value="reset">City overview</option>
          <option value="hotspot">Flood hotspot</option>
          <option value="bridge">Bridge crossing</option>
          <option value="rescue">Rescue operation</option>
        </select>
        <select aria-label="Lighting preset" value={lighting} onChange={(event)=>setLighting(event.target.value as typeof lighting)} disabled={mapMode}>
          <option value="daylight">Daylight</option>
          <option value="overcast">Overcast</option>
          <option value="low-light">Low-light</option>
        </select>
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
