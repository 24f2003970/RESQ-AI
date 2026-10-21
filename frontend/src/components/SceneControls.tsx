import { Focus, Minus, Plus, RotateCcw, View } from "lucide-react";

export default function SceneControls({ inventory, lighting, hasSelection, hasFlood, hasBridge, hasMission, onCommand, onLighting, onInventory }: {
  inventory: boolean; lighting: string; hasSelection: boolean; hasFlood: boolean; hasBridge: boolean; hasMission: boolean;
  onCommand: (command: string) => void; onLighting: (value: "daylight" | "overcast" | "low-light") => void; onInventory: () => void;
}) {
  return <div className="scene-navigation" role="group" aria-label="Camera controls">
    <div className="scene-navigation-actions">
      <button onClick={() => onCommand("reset")} disabled={inventory} aria-label="Reset camera"><RotateCcw size={15}/> City overview</button>
      <button onClick={() => onCommand("zoom-in")} disabled={inventory} aria-label="Zoom in"><Plus size={16}/> Zoom in</button>
      <button onClick={() => onCommand("zoom-out")} disabled={inventory} aria-label="Zoom out"><Minus size={16}/> Zoom out</button>
      <button onClick={() => onCommand("focus")} disabled={!hasSelection || inventory} aria-label="Focus selected building"><Focus size={15}/> Focus building</button>
      <button onClick={onInventory} aria-label={inventory ? "Show 3D city" : "Show building inventory"} aria-pressed={inventory}><View size={15}/>{inventory ? "Back to 3D" : "Find a building"}</button>
    </div>
    <div className="scene-navigation-options">
      <label>Jump to<select aria-label="Camera preset" value="" onChange={(event) => onCommand(event.target.value)} disabled={inventory}>
        <option value="" disabled>Choose a place</option>
        <option value="reset">City overview</option>
        <option value="hotspot" disabled={!hasFlood}>Flood hotspot{!hasFlood ? " · no water yet" : ""}</option>
        <option value="bridge" disabled={!hasBridge}>Bridge crossing</option>
        <option value="rescue" disabled={!hasMission}>Selected mission{!hasMission ? " · select a mission first" : ""}</option>
      </select></label>
      <label>Lighting<select aria-label="Lighting preset" value={lighting} onChange={(event) => onLighting(event.target.value as "daylight" | "overcast" | "low-light")} disabled={inventory}>
        <option value="daylight">Daylight</option><option value="overcast">Overcast</option><option value="low-light">Low-light</option>
      </select></label>
    </div>
  </div>;
}
