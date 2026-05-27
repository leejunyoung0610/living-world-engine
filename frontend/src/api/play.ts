import { apiFetch } from "./client";

export const SESSION_EXPIRED = "SESSION_EXPIRED";

export type PlayWorldBrief = {
  world_uuid: string;
  list_name: string;
  story_title: string;
  description: string;
  world_setting: string;
  /** 입장 설정 히어로 — HTTPS 만 */
  cover_image_url?: string;
  npcs: Record<string, unknown>[];
  suggested_player: Record<string, unknown> | null;
};

export type PlayStartResult = { session_id: string; world_name: string; resumed?: boolean };

export type SessionSummary = {
  session_id: string;
  world_id: string;
  world_name: string;
  turn: number;
  day: number;
  last_message_preview: string;
  created_at: string;
  last_active: string;
};

export type NpcSegment = { speaker: string; text: string };

export type TurnResult = {
  turn: number;
  day: number;
  response: string;
  response_segments: NpcSegment[];
  events_triggered: { event_id: string; description: string }[];
};

export type PlayHistoryMessage = {
  role: "user" | "assistant";
  content: string;
  segments: NpcSegment[];
};

export type PlayHistoryResult = {
  turn: number;
  day: number;
  world_name: string;
  messages: PlayHistoryMessage[];
  npc_names: string[];
};

async function failDetail(res: Response, fallback: string): Promise<never> {
  if (res.status === 401) throw new Error(SESSION_EXPIRED);
  const j = (await res.json().catch(() => ({}))) as { detail?: string };
  throw new Error(typeof j.detail === "string" ? j.detail : fallback);
}

export async function fetchPlayWorldBrief(token: string, worldId: string): Promise<PlayWorldBrief> {
  const res = await apiFetch(`/api/play/world/${worldId}/brief`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) await failDetail(res, "월드 정보를 불러오지 못했습니다");
  return res.json() as Promise<PlayWorldBrief>;
}

/** 기존 세션만 이어하기. 새 세션이 필요하면 null. */
export async function tryResumePlay(token: string, worldId: string): Promise<PlayStartResult | null> {
  const res = await apiFetch("/api/play/start", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ world_id: worldId, force_new: false }),
  });
  if (res.status === 200) return res.json() as Promise<PlayStartResult>;
  if (res.status === 401) throw new Error(SESSION_EXPIRED);
  return null;
}

export async function startPlay(
  token: string,
  worldId: string,
  options?: { forceNew?: boolean; player?: Record<string, unknown> },
): Promise<PlayStartResult> {
  const body: Record<string, unknown> = {
    world_id: worldId,
    force_new: options?.forceNew === true,
  };
  if (options?.player) body.player = options.player;
  const res = await apiFetch("/api/play/start", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) await failDetail(res, "세션 시작 실패");
  return res.json() as Promise<PlayStartResult>;
}

export async function listPlaySessions(token: string): Promise<SessionSummary[]> {
  const res = await apiFetch("/api/play/sessions", {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) await failDetail(res, "세션 목록을 불러오지 못했습니다");
  return res.json() as Promise<SessionSummary[]>;
}

export async function deletePlaySession(token: string, sessionId: string): Promise<void> {
  const res = await apiFetch(`/api/play/${sessionId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) await failDetail(res, "세션을 삭제하지 못했습니다");
}

export async function fetchPlayHistory(token: string, sessionId: string): Promise<PlayHistoryResult> {
  const res = await apiFetch(`/api/play/${sessionId}/history`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) await failDetail(res, "히스토리를 불러오지 못했습니다");
  return res.json() as Promise<PlayHistoryResult>;
}

export async function sendTurn(token: string, sessionId: string, message: string): Promise<TurnResult> {
  const res = await apiFetch(`/api/play/${sessionId}/turn`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) await failDetail(res, "턴 처리 실패");
  return res.json() as Promise<TurnResult>;
}

export type StreamCallbacks = {
  onDelta: (text: string) => void;
  onDone: (result: TurnResult) => void;
  onError: (message: string) => void;
};

export async function sendTurnStream(
  token: string,
  sessionId: string,
  message: string,
  cb: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const res = await apiFetch(`/api/play/${sessionId}/turn/stream`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!res.ok || !res.body) {
    if (res.status === 401) throw new Error(SESSION_EXPIRED);
    const j = (await res.json().catch(() => ({}))) as { detail?: string };
    cb.onError(typeof j.detail === "string" ? j.detail : "스트리밍을 시작하지 못했습니다");
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const handleEvent = (rawEvent: string) => {
    let evType = "message";
    const dataLines: string[] = [];
    for (const line of rawEvent.split("\n")) {
      if (line.startsWith("event:")) evType = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (dataLines.length === 0) return;
    let payload: unknown;
    try {
      payload = JSON.parse(dataLines.join("\n"));
    } catch {
      return;
    }
    if (evType === "delta") {
      const text = (payload as { text?: string }).text ?? "";
      if (text) cb.onDelta(text);
    } else if (evType === "done") {
      cb.onDone(payload as TurnResult);
    } else if (evType === "error") {
      cb.onError((payload as { detail?: string }).detail ?? "스트리밍 오류");
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sepIdx = buffer.indexOf("\n\n");
      while (sepIdx !== -1) {
        const evtChunk = buffer.slice(0, sepIdx);
        buffer = buffer.slice(sepIdx + 2);
        if (evtChunk.trim().length > 0) handleEvent(evtChunk);
        sepIdx = buffer.indexOf("\n\n");
      }
    }
    if (buffer.trim().length > 0) handleEvent(buffer);
  } catch (e) {
    if ((e as { name?: string }).name === "AbortError") return;
    cb.onError(e instanceof Error ? e.message : "스트리밍 중단");
  }
}

/** 마지막 NPC 본문 응답만 다시 생성 (동일 SSE 프로토콜). `options.message`가 있으면 마지막 플레이어 대사를 교체한 뒤 실행. */
export async function sendRegenerateStream(
  token: string,
  sessionId: string,
  cb: StreamCallbacks,
  signal?: AbortSignal,
  options?: { message?: string },
): Promise<void> {
  const hasBody = options?.message != null && options.message !== "";
  const res = await apiFetch(`/api/play/${sessionId}/turn/regenerate/stream`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "text/event-stream",
      ...(hasBody ? { "Content-Type": "application/json" } : {}),
    },
    body: hasBody ? JSON.stringify({ message: options!.message }) : undefined,
    signal,
  });

  if (!res.ok || !res.body) {
    if (res.status === 401) throw new Error(SESSION_EXPIRED);
    const j = (await res.json().catch(() => ({}))) as { detail?: string };
    cb.onError(typeof j.detail === "string" ? j.detail : "재생성 스트림을 시작하지 못했습니다");
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const handleEvent = (rawEvent: string) => {
    let evType = "message";
    const dataLines: string[] = [];
    for (const line of rawEvent.split("\n")) {
      if (line.startsWith("event:")) evType = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (dataLines.length === 0) return;
    let payload: unknown;
    try {
      payload = JSON.parse(dataLines.join("\n"));
    } catch {
      return;
    }
    if (evType === "delta") {
      const text = (payload as { text?: string }).text ?? "";
      if (text) cb.onDelta(text);
    } else if (evType === "done") {
      cb.onDone(payload as TurnResult);
    } else if (evType === "error") {
      cb.onError((payload as { detail?: string }).detail ?? "재생성 스트리밍 오류");
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sepIdx = buffer.indexOf("\n\n");
      while (sepIdx !== -1) {
        const evtChunk = buffer.slice(0, sepIdx);
        buffer = buffer.slice(sepIdx + 2);
        if (evtChunk.trim().length > 0) handleEvent(evtChunk);
        sepIdx = buffer.indexOf("\n\n");
      }
    }
    if (buffer.trim().length > 0) handleEvent(buffer);
  } catch (e) {
    if ((e as { name?: string }).name === "AbortError") return;
    cb.onError(e instanceof Error ? e.message : "재생성 스트리밍 중단");
  }
}
