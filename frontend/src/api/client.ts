import Ajv2020 from "ajv/dist/2020";
import citySchema from "./city.schema.json";
import type { components } from "./schema";

export type CityState = components["schemas"]["CityState"];
export type Building = components["schemas"]["Building"];
export type Position = components["schemas"]["Position"];
export type Health = components["schemas"]["Health"];

const validate = new Ajv2020({
  strict: false,
  allErrors: true,
}).compile<CityState>(citySchema);

export function parseCity(value: unknown): CityState {
  if (!validate(value))
    throw new Error(
      "The local service returned an invalid city. Restart the backend and retry.",
    );
  if (!value.buildings.length)
    throw new Error(
      "The city has no buildings. Check the local seed configuration and retry.",
    );
  return value;
}

async function request(path: string, signal?: AbortSignal): Promise<unknown> {
  const timeout = AbortSignal.timeout(8000);
  const response = await fetch(`/api/v1/${path}`, {
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  });
  if (!response.ok)
    throw new Error(
      `The local service returned ${response.status}. Check that FastAPI is running on port 8000.`,
    );
  return response.json();
}

export async function fetchCity(signal?: AbortSignal): Promise<CityState> {
  return parseCity(await request("city/state", signal));
}

export async function fetchHealth(): Promise<Health> {
  const value = (await request("health")) as Health;
  if (value.status !== "ok" || value.mode !== "local")
    throw new Error("The local health response is invalid.");
  return value;
}

export async function fetchBuilding(
  id: string,
  city: CityState,
  signal?: AbortSignal,
): Promise<Building> {
  const value = await request(
    `city/buildings/${encodeURIComponent(id)}`,
    signal,
  );
  const expected = city.buildings.find((b) => b.id === id);
  if (!expected || JSON.stringify(value) !== JSON.stringify(expected))
    throw new Error(
      "Building details do not match the city snapshot. Refresh the city.",
    );
  return value as Building;
}
