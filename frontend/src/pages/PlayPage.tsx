import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";
import {
  fetchPlayHistory,
  fetchPlayRelationships,
  sendRegenerateStream,
  sendTurnStream,
  SESSION_EXPIRED,
  type NpcRelationshipRow,
  type NpcSegment,
  type TriggeredEvent,
  type TurnResult,
} from "../api/play";
import { EventCard } from "../components/EventCard";
import { LoggedInNav } from "../components/LoggedInNav";
import {
  RELATIONSHIP_STAT_LABELS,
  type RelationshipStatSlug,
} from "../constants/relationshipStats";
import { splitAssistantIntoSegments } from "../utils/dialogueSplit";

type ChatLine =
  | { role: "user"; text: string }
  | { role: "assistant"; text: string; segments: NpcSegment[] };

/** 마지막 본문 assistant(이벤트 시스템 줄 제외) 인덱스 — 바로 앞이 user 여야 함. */
function findRegenerateTargetIndex(lines: ChatLine[]): number | null {
  for (let i = lines.length - 1; i >= 0; i--) {
    const ln = lines[i];
    if (ln.role !== "assistant") continue;
    if (ln.text.startsWith("[이벤트]")) continue;
    if (i > 0 && lines[i - 1].role === "user") return i;
  }
  return null;
}

function showSpeakerLabel(speaker: string, segmentCount: number): boolean {
  if (segmentCount > 1) return true;
  if (speaker === "응답" || speaker === "내레이션") return false;
  return true;
}

function AssistantBlocks({ text, segments }: { text: string; segments: NpcSegment[] }) {
  const list = segments.length > 0 ? segments : [{ speaker: "응답", text }];
  return (
    <div className="mr-4 space-y-2">
      {list.map((seg, j) => (
        <div
          key={j}
          className="rounded-lg border border-slate-700/60 bg-slate-800/80 px-3 py-2 text-sm text-slate-200"
        >
          {showSpeakerLabel(seg.speaker, list.length) && (
            <p className="mb-1 text-xs font-medium text-amber-200/90">{seg.speaker}</p>
          )}
          <p className="whitespace-pre-wrap">{seg.text}</p>
        </div>
      ))}
    </div>
  );
}

export function PlayPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const nav = useNavigate();
  const [token, setToken] = useState<string | null>(null);
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [meta, setMeta] = useState<{ turn: number; day: number } | null>(null);
  const [npcNames, setNpcNames] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editDraft, setEditDraft] = useState("");
  const [editFieldError, setEditFieldError] = useState<string | null>(null);
  const [relOpen, setRelOpen] = useState(false);
  const [relLoading, setRelLoading] = useState(false);
  const [relError, setRelError] = useState<string | null>(null);
  const [relRows, setRelRows] = useState<NpcRelationshipRow[]>([]);
  const [eventQueue, setEventQueue] = useState<TriggeredEvent[]>([]);

  useEffect(() => {
    const t = localStorage.getItem(TOKEN_KEY);
    if (!t) {
      nav("/login");
      return;
    }
    setToken(t);
  }, [nav]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines, loading]);

  useEffect(() => {
    if (!token || !sessionId) return;
    let cancelled = false;
    setHistoryLoading(true);
    setError(null);
    fetchPlayHistory(token, sessionId)
      .then((h) => {
        if (cancelled) return;
        setMeta({ turn: h.turn, day: h.day });
        setNpcNames(h.npc_names ?? []);
        const next: ChatLine[] = [];
        for (const m of h.messages) {
          if (m.role === "user") {
            next.push({ role: "user", text: m.content });
          } else {
            next.push({
              role: "assistant",
              text: m.content,
              segments: m.segments ?? [],
            });
          }
        }
        setLines(next);
      })
      .catch((err) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : "오류";
        if (msg === SESSION_EXPIRED) {
          localStorage.removeItem(TOKEN_KEY);
          nav("/login");
          return;
        }
        setError(msg);
        setLines([]);
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, sessionId, nav]);

  useEffect(() => {
    if (!editOpen && !relOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setEditOpen(false);
        setRelOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editOpen, relOpen]);

  async function openRelationshipsPanel() {
    if (!token || !sessionId) return;
    setRelOpen(true);
    setRelLoading(true);
    setRelError(null);
    try {
      const data = await fetchPlayRelationships(token, sessionId);
      setRelRows(data.npcs);
      if (meta) setMeta({ turn: data.turn, day: data.day });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "오류";
      if (msg === SESSION_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setRelError(msg);
      setRelRows([]);
    } finally {
      setRelLoading(false);
    }
  }

  function statLabel(slug: string): string {
    return RELATIONSHIP_STAT_LABELS[slug as RelationshipStatSlug] ?? slug;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token || !sessionId || !input.trim() || loading) return;
    const msg = input.trim();
    setInput("");
    setError(null);

    setLines((prev) => [
      ...prev,
      { role: "user", text: msg },
      { role: "assistant", text: "", segments: [] },
    ]);
    setLoading(true);

    let streamedText = "";
    let doneFired = false;

    const updateAssistant = (text: string, segments: NpcSegment[]) => {
      setLines((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i--) {
          if (next[i].role === "assistant") {
            next[i] = { role: "assistant", text, segments };
            break;
          }
        }
        return next;
      });
    };

    try {
      await sendTurnStream(token, sessionId, msg, {
        onDelta: (chunk) => {
          streamedText += chunk;
          const segs = splitAssistantIntoSegments(streamedText, npcNames);
          updateAssistant(streamedText, segs);
        },
        onDone: (r: TurnResult) => {
          doneFired = true;
          setMeta({ turn: r.turn, day: r.day });
          updateAssistant(
            r.response,
            splitAssistantIntoSegments(r.response, npcNames),
          );
          if (r.events_triggered.length > 0) {
            setEventQueue(r.events_triggered);
          }
        },
        onError: (m) => {
          setError(m);
          if (!doneFired) {
            setLines((prev) => prev.slice(0, -2));
          }
        },
      });
      if (!doneFired && !streamedText) {
        setLines((prev) => prev.slice(0, -2));
        if (!error) setError("응답을 받지 못했습니다");
      }
    } catch (err) {
      const m = err instanceof Error ? err.message : "오류";
      if (m === SESSION_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setError(m);
      setLines((prev) => prev.slice(0, -2));
    } finally {
      setLoading(false);
    }
  }

  const regenerateAi = findRegenerateTargetIndex(lines);
  const canRegenerate =
    !loading && !historyLoading && regenerateAi !== null;

  function openEditLastUserModal() {
    if (!canRegenerate || regenerateAi === null) return;
    const ui = regenerateAi - 1;
    if (ui < 0 || lines[ui]?.role !== "user") return;
    setEditDraft(lines[ui].text);
    setEditFieldError(null);
    setEditOpen(true);
  }

  async function runRegenerate(options?: { userMessageOverride?: string }) {
    if (!token || !sessionId || loading || historyLoading) return;
    const ai = findRegenerateTargetIndex(lines);
    if (ai === null) return;
    const ui = ai - 1;
    if (ui < 0 || lines[ui].role !== "user") return;

    const before = [...lines];
    const override = options?.userMessageOverride?.trim();
    setError(null);
    setLines((prev) => {
      const head = prev.slice(0, ai);
      if (override) {
        const nextHead = [...head];
        nextHead[nextHead.length - 1] = { role: "user", text: override };
        return [...nextHead, { role: "assistant", text: "", segments: [] }];
      }
      return [...head, { role: "assistant", text: "", segments: [] }];
    });
    setLoading(true);

    let streamedText = "";
    let doneFired = false;

    const updateAssistant = (text: string, segments: NpcSegment[]) => {
      setLines((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i--) {
          if (next[i].role === "assistant") {
            next[i] = { role: "assistant", text, segments };
            break;
          }
        }
        return next;
      });
    };

    try {
      await sendRegenerateStream(
        token,
        sessionId,
        {
          onDelta: (chunk) => {
            streamedText += chunk;
            const segs = splitAssistantIntoSegments(streamedText, npcNames);
            updateAssistant(streamedText, segs);
          },
          onDone: (r: TurnResult) => {
            doneFired = true;
            setMeta({ turn: r.turn, day: r.day });
            updateAssistant(
              r.response,
              splitAssistantIntoSegments(r.response, npcNames),
            );
            if (r.events_triggered.length > 0) {
              setEventQueue(r.events_triggered);
            }
          },
          onError: (m) => {
            setError(m);
            if (!doneFired) {
              setLines(before);
            }
          },
        },
        undefined,
        override ? { message: override } : undefined,
      );
      if (!doneFired && !streamedText) {
        setLines(before);
        setError("응답을 받지 못했습니다");
      }
    } catch (err) {
      const m = err instanceof Error ? err.message : "오류";
      if (m === SESSION_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setError(m);
      setLines(before);
    } finally {
      setLoading(false);
    }
  }

  function submitEditAndRegenerate() {
    const t = editDraft.trim();
    if (!t) {
      setEditFieldError("대사를 입력해 주세요.");
      return;
    }
    setEditOpen(false);
    void runRegenerate({ userMessageOverride: t });
  }

  if (!token || !sessionId) {
    return <p className="px-4 py-8 text-slate-400">준비 중…</p>;
  }

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-slate-950">
      <LoggedInNav />
      <div className="mx-auto flex min-h-0 w-full max-w-2xl flex-1 flex-col gap-2 px-4 pt-2 pb-2 sm:gap-3 sm:px-6 sm:pt-3">
        <div className="shrink-0 flex flex-wrap items-center justify-between gap-2">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <Link to="/my" className="shrink-0 text-sm text-slate-400 hover:text-white">
              ← 마이페이지
            </Link>
            <h1 className="truncate text-base font-semibold text-white sm:text-lg">플레이</h1>
          </div>
          <div className="flex flex-shrink-0 flex-wrap items-center justify-end gap-2">
            {meta && (
              <span className="text-xs text-slate-500">
                Turn {meta.turn} · Day {meta.day}
              </span>
            )}
            <button
              type="button"
              onClick={() => void openRelationshipsPanel()}
              disabled={historyLoading}
              title="NPC별 관계 수치 보기 (대화창에는 숫자 미표시)"
              className="rounded-lg border border-slate-600/80 bg-slate-950/60 px-2.5 py-1.5 text-xs font-medium text-amber-200/90 hover:bg-slate-800/80 disabled:cursor-not-allowed disabled:opacity-40"
            >
              관계
            </button>
            <div className="flex overflow-hidden rounded-lg border border-slate-600/80 bg-slate-950/60 shadow-sm">
              <button
                type="button"
                onClick={() => void runRegenerate()}
                disabled={!canRegenerate}
                title="같은 플레이어 대사로 NPC 응답만 다시 받습니다"
                className="border-r border-slate-600/80 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-800/80 disabled:cursor-not-allowed disabled:opacity-40"
              >
                다시 생성
              </button>
              <button
                type="button"
                onClick={openEditLastUserModal}
                disabled={!canRegenerate}
                title="마지막 플레이어 대사를 고친 뒤 다시 받기"
                className="px-2.5 py-1.5 text-xs font-medium text-indigo-200 hover:bg-indigo-950/50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                대사 수정
              </button>
            </div>
          </div>
        </div>
        <p className="hidden shrink-0 text-xs text-slate-500 sm:block">
          대화는 같은 세션으로 돌아오면 서버에서 다시 불러옵니다.
        </p>

        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40 shadow-inner">
          <div
            className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-y-contain scroll-smooth p-3 sm:p-4"
            style={{ WebkitOverflowScrolling: "touch" }}
          >
            {historyLoading && <p className="text-sm text-slate-500">대화 불러오는 중…</p>}
            {!historyLoading && lines.length === 0 && (
              <p className="text-sm text-slate-500">첫 입력을 내면 NPC 응답이 옵니다.</p>
            )}
            {lines.map((ln, i) =>
              ln.role === "user" ? (
                <div
                  key={i}
                  className="ml-8 rounded-lg bg-indigo-950/50 px-3 py-2 text-sm text-indigo-100"
                >
                  {ln.text}
                </div>
              ) : (
                <AssistantBlocks key={i} text={ln.text} segments={ln.segments} />
              ),
            )}
            {loading && <p className="text-xs text-slate-500">응답 대기 중…</p>}
            <div ref={bottomRef} />
          </div>
          {error && (
            <p className="shrink-0 border-t border-red-900/40 px-4 py-2 text-sm text-red-300">{error}</p>
          )}
          <form
            onSubmit={onSubmit}
            className="shrink-0 flex gap-2 border-t border-slate-800 bg-slate-900/80 p-3"
            style={{ paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom, 0px))" }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="무엇을 하시겠습니까?"
              enterKeyHint="send"
              autoComplete="off"
              disabled={loading || historyLoading}
              className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white placeholder:text-slate-600"
            />
            <button
              type="submit"
              disabled={loading || historyLoading || !input.trim()}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
            >
              보내기
            </button>
          </form>
        </div>
      </div>

      {relOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/55 p-0 sm:items-center sm:p-4"
          role="presentation"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setRelOpen(false);
          }}
        >
          <div
            className="flex max-h-[min(85dvh,28rem)] w-full max-w-md flex-col rounded-t-2xl border border-slate-700 bg-slate-900 shadow-2xl sm:rounded-2xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="play-relationships-title"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="border-b border-slate-800 px-4 py-3 sm:px-5">
              <h2 id="play-relationships-title" className="text-base font-semibold text-white">
                NPC 관계 수치
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                월드 편집에서 설정한 스탯만 표시됩니다. 대화 후 「관계」를 다시 눌러 갱신하세요.
              </p>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 sm:px-5">
              {relLoading && <p className="text-sm text-slate-500">불러오는 중…</p>}
              {relError && <p className="text-sm text-red-300">{relError}</p>}
              {!relLoading && !relError && relRows.length === 0 && (
                <p className="text-sm text-slate-500">
                  추적 중인 관계 수치가 없습니다. 월드 편집에서 NPC별 스탯을 추가하세요.
                </p>
              )}
              {!relLoading && relRows.length > 0 && (
                <ul className="space-y-4">
                  {relRows.map((row) => (
                    <li key={row.npc_id} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                      <p className="text-sm font-medium text-white">{row.npc_name}</p>
                      <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                        {Object.entries(row.stats).map(([slug, val]) => (
                          <div key={slug} className="flex justify-between gap-2 text-slate-400">
                            <dt>{statLabel(slug)}</dt>
                            <dd className="font-mono text-amber-200/90">{val}</dd>
                          </div>
                        ))}
                      </dl>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-800 px-4 py-3 sm:px-5">
              <button
                type="button"
                onClick={() => void openRelationshipsPanel()}
                disabled={relLoading}
                className="rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-40"
              >
                새로고침
              </button>
              <button
                type="button"
                onClick={() => setRelOpen(false)}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}

      {editOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/55 p-0 sm:items-center sm:p-4"
          role="presentation"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setEditOpen(false);
          }}
        >
          <div
            className="flex max-h-[min(90dvh,32rem)] w-full max-w-lg flex-col rounded-t-2xl border border-slate-700 bg-slate-900 shadow-2xl sm:rounded-2xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-user-line-title"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="border-b border-slate-800 px-4 py-3 sm:px-5">
              <h2 id="edit-user-line-title" className="text-base font-semibold text-white">
                플레이어 대사 수정
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                마지막으로 보낸 말만 바꿉니다. 적용 시 새 턴과 같이 호출 · 사용량이
                적용됩니다.
              </p>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 sm:px-5">
              <label htmlFor="edit-user-line" className="sr-only">
                플레이어 대사
              </label>
              <textarea
                id="edit-user-line"
                value={editDraft}
                onChange={(e) => {
                  setEditDraft(e.target.value);
                  if (editFieldError) setEditFieldError(null);
                }}
                rows={5}
                autoFocus
                className="w-full resize-y rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                placeholder="NPC에게 보낼 문장을 수정하세요"
              />
              {editFieldError && (
                <p className="mt-2 text-xs text-amber-400">{editFieldError}</p>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-800 px-4 py-3 sm:px-5">
              <button
                type="button"
                onClick={() => setEditOpen(false)}
                className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
              >
                취소
              </button>
              <button
                type="button"
                onClick={submitEditAndRegenerate}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
              >
                이 대사로 다시 받기
              </button>
            </div>
          </div>
        </div>
      )}

      {eventQueue.length > 0 && (
        <EventCard
          event={eventQueue[0]}
          onContinue={() => setEventQueue((q) => q.slice(1))}
        />
      )}
    </div>
  );
}
