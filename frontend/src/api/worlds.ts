import { apiFetch } from "./client";

export type WorldVisibility = "private" | "public";

export type WorldSummary = {
  id: string;
  name: string;
  visibility: WorldVisibility;
  world_id: string;
  genres: string[];
  created_at: string;
};

export type WorldDetail = {
  id: string;
  name: string;
  visibility: WorldVisibility;
  world: Record<string, unknown>;
  characters: Record<string, unknown>;
  events: Record<string, unknown> | null;
  genres: string[];
  created_at: string;
  updated_at: string;
};

export type ExploreWorldSummary = {
  id: string;
  name: string;
  world_id: string;
  owner_username: string;
  is_mine: boolean;
  genres: string[];
  play_start_count: number;
  like_count: number;
  liked_by_me: boolean;
  cover_image_url?: string;
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
  id: "seoul_national_university",
  name: "서울대학교",
  description: "관악 캠퍼스. 수업과 동아리가 얽인 하루하루.",
  world_setting: "",
  time: "개강 첫 주",
  regions: [],
  facts: [],
  world_variables: {},
};

/** 월드 저장용 최소 characters — NPC만 (플레이어는 플레이 시작 시 설정) */
export const EMPTY_CHARACTERS: Record<string, unknown> = {
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

export type ExploreSort = "latest" | "popular" | "recommended";

export type GenreEntry = { slug: string; label: string };

export async function fetchGenreMeta(): Promise<GenreEntry[]> {
  const res = await apiFetch("/api/worlds/meta/genres");
  if (!res.ok) throw new Error(await textDetail(res));
  return res.json() as Promise<GenreEntry[]>;
}

export async function exploreWorlds(
  token: string,
  opts?: {
    limit?: number;
    offset?: number;
    sort?: ExploreSort;
    genre?: string | null;
    q?: string | null;
  },
): Promise<ExploreWorldsPage> {
  const q = new URLSearchParams();
  if (opts?.limit != null) q.set("limit", String(opts.limit));
  if (opts?.offset != null) q.set("offset", String(opts.offset));
  if (opts?.sort != null) q.set("sort", opts.sort);
  if (opts?.genre != null && opts.genre !== "") q.set("genre", opts.genre);
  if (opts?.q != null && opts.q.trim() !== "") q.set("q", opts.q.trim());
  const qs = q.toString();
  const path = qs ? `/api/worlds/explore?${qs}` : "/api/worlds/explore";
  const res = await apiFetch(path, { headers: authHeaders(token) });
  return readJson<ExploreWorldsPage>(res);
}

export type PublicNpcBrief = {
  name: string;
  role: string;
  location: string;
  summary: string;
  portrait_url: string;
};

export type PublicWorldDetail = {
  id: string;
  name: string;
  world_id: string;
  owner_username: string;
  is_mine: boolean;
  genres: string[];
  description: string;
  world_setting: string;
  time: string;
  npc_count: number;
  npcs: PublicNpcBrief[];
  play_start_count: number;
  like_count: number;
  liked_by_me: boolean;
  cover_image_url: string;
  created_at: string;
  updated_at: string;
};

export type WorldLikeState = {
  liked: boolean;
  like_count: number;
};

export type GenerateCoverResponse = {
  cover_image_url: string;
  remaining_user_monthly: number | null;
  remaining_world_monthly: number | null;
};

export async function fetchPublicWorld(token: string, id: string): Promise<PublicWorldDetail> {
  const res = await apiFetch(`/api/worlds/public/${id}`, { headers: authHeaders(token) });
  return readJson<PublicWorldDetail>(res);
}

export async function toggleWorldLike(token: string, id: string): Promise<WorldLikeState> {
  const res = await apiFetch(`/api/worlds/${id}/like`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return readJson<WorldLikeState>(res);
}

export async function generateWorldCover(token: string, id: string): Promise<GenerateCoverResponse> {
  const res = await apiFetch(`/api/worlds/${id}/generate-cover`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return readJson<GenerateCoverResponse>(res);
}

export type GenerateNpcPortraitResponse = {
  npc_id: string;
  portrait_image_url: string;
  remaining_avatar_user_monthly: number | null;
  remaining_avatar_world_monthly: number | null;
};

export async function generateNpcPortrait(
  token: string,
  worldId: string,
  npcId: string,
): Promise<GenerateNpcPortraitResponse> {
  const enc = encodeURIComponent(npcId);
  const res = await apiFetch(`/api/worlds/${worldId}/npcs/${enc}/generate-portrait`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return readJson<GenerateNpcPortraitResponse>(res);
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
    genres: string[];
  },
): Promise<WorldDetail> {
  const res = await apiFetch("/api/worlds/", {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({
      ...body,
      events: body.events ?? null,
      visibility: body.visibility ?? "private",
      genres: body.genres,
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
    genres: string[];
  },
): Promise<WorldDetail> {
  const res = await apiFetch(`/api/worlds/${id}`, {
    method: "PUT",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({
      ...body,
      events: body.events ?? null,
      visibility: body.visibility ?? "private",
      genres: body.genres,
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
    const j = (await res.json()) as {
      detail?: string | unknown;
      errors?: Array<{ loc?: (string | number)[]; msg?: string; type?: string }>;
    };
    if (Array.isArray(j.errors) && j.errors.length > 0) {
      const e = j.errors[0];
      const loc = (e.loc ?? [])
        .filter((x) => x !== "body" && x !== "json")
        .join(".");
      if (e.msg) return loc ? `${loc}: ${e.msg}` : e.msg;
    }
    if (typeof j.detail === "string") return j.detail;
    return res.statusText || "요청 실패";
  } catch {
    return res.statusText || "요청 실패";
  }
}
