import { apiFetch } from "./client";

export type WorldVisibility = "private" | "public";

export type WorldSummary = {
  id: string;
  name: string;
  visibility: WorldVisibility;
  world_id: string;
  created_at: string;
};

export type WorldDetail = {
  id: string;
  name: string;
  visibility: WorldVisibility;
  world: Record<string, unknown>;
  characters: Record<string, unknown>;
  events: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type ExploreWorldSummary = {
  id: string;
  name: string;
  world_id: string;
  owner_username: string;
  is_mine: boolean;
  created_at: string;
  updated_at: string;
};

export type ExploreWorldsPage = {
  items: ExploreWorldSummary[];
  total: number;
  limit: number;
  offset: number;
};

/** 엔진 `world.json` / `characters.json` 최소 형태 — 새 월드 기본값 */
export const EMPTY_WORLD: Record<string, unknown> = {
  id: "my_world",
  name: "새 세계",
  description: "",
  time: "Day 1",
  regions: [],
  facts: [],
  world_variables: {},
};

export const EMPTY_CHARACTERS: Record<string, unknown> = {
  player: {
    name: "플레이어",
    class: "traveler",
    stats: { hp: 10, mana: 5, focus: 5 },
  },
  npcs: [],
};

export const SESSION_EXPIRED = "SESSION_EXPIRED";

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

async function readJson<T>(res: Response): Promise<T> {
  if (res.status === 401) throw new Error(SESSION_EXPIRED);
  if (!res.ok) throw new Error(await textDetail(res));
  return res.json() as Promise<T>;
}

async function readEmpty(res: Response): Promise<void> {
  if (res.status === 401) throw new Error(SESSION_EXPIRED);
  if (!res.ok) throw new Error(await textDetail(res));
}

export async function listWorlds(token: string): Promise<WorldSummary[]> {
  const res = await apiFetch("/api/worlds/", { headers: authHeaders(token) });
  return readJson<WorldSummary[]>(res);
}

export async function exploreWorlds(
  token: string,
  opts?: { limit?: number; offset?: number },
): Promise<ExploreWorldsPage> {
  const q = new URLSearchParams();
  if (opts?.limit != null) q.set("limit", String(opts.limit));
  if (opts?.offset != null) q.set("offset", String(opts.offset));
  const qs = q.toString();
  const path = qs ? `/api/worlds/explore?${qs}` : "/api/worlds/explore";
  const res = await apiFetch(path, { headers: authHeaders(token) });
  return readJson<ExploreWorldsPage>(res);
}

export async function getWorld(token: string, id: string): Promise<WorldDetail> {
  const res = await apiFetch(`/api/worlds/${id}`, { headers: authHeaders(token) });
  return readJson<WorldDetail>(res);
}

export async function createWorld(
  token: string,
  body: {
    name: string;
    world: Record<string, unknown>;
    characters: Record<string, unknown>;
    events?: Record<string, unknown> | null;
    visibility?: WorldVisibility;
  },
): Promise<WorldDetail> {
  const res = await apiFetch("/api/worlds/", {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({
      ...body,
      events: body.events ?? null,
      visibility: body.visibility ?? "private",
    }),
  });
  return readJson<WorldDetail>(res);
}

export async function updateWorld(
  token: string,
  id: string,
  body: {
    name: string;
    world: Record<string, unknown>;
    characters: Record<string, unknown>;
    events?: Record<string, unknown> | null;
    visibility?: WorldVisibility;
  },
): Promise<WorldDetail> {
  const res = await apiFetch(`/api/worlds/${id}`, {
    method: "PUT",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({
      ...body,
      events: body.events ?? null,
      visibility: body.visibility ?? "private",
    }),
  });
  return readJson<WorldDetail>(res);
}

export async function deleteWorld(token: string, id: string): Promise<void> {
  const res = await apiFetch(`/api/worlds/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  await readEmpty(res);
}

async function textDetail(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: string | unknown };
    if (typeof j.detail === "string") return j.detail;
    return res.statusText || "요청 실패";
  } catch {
    return res.statusText || "요청 실패";
  }
}
