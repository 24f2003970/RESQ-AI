import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchMissionClock } from "../api/client";

afterEach(()=>vi.unstubAllGlobals());

describe("API error details",()=>{
  it("preserves the backend's stale-version explanation for mission operations",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:false,status:409,json:async()=>({detail:"Mission clock version is stale; refresh before advancing."})} as Response));
    await expect(fetchMissionClock("scenario-riverside-2026")).rejects.toThrow("Mission clock version is stale; refresh before advancing.");
  });
});
