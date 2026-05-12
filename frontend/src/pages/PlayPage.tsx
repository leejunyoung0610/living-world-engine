import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";
import {
  fetchPlayHistory,
  sendRegenerateStream,
  sendTurnStream,
  SESSION_EXPIRED,
  type NpcSegment,
  type TurnResult,
} from "../api/play";
import { LoggedInNav } from "../components/LoggedInNav";
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
          updateAssistant(r.response, r.response_segments ?? []);
          if (r.events_triggered.length > 0) {
            const ev = r.events_triggered.map((x) => x.description || x.event_id).join(" · ");
            setLines((prev) => [
              ...prev,
              {
                role: "assistant",
                text: `[이벤트] ${ev}`,
                segments: [{ speaker: "이벤트", text: `[이벤트] ${ev}` }],
              },
            ]);
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

  const canRegenerate =
    !loading && !historyLoading && findRegenerateTargetIndex(lines) !== null;

  async function onRegenerate() {
    if (!token || !sessionId || loading || historyLoading) return;
    const ai = findRegenerateTargetIndex(lines);
    if (ai === null) return;

    const before = [...lines];
    setError(null);
    setLines((prev) => [...prev.slice(0, ai), { role: "assistant", text: "", segments: [] }]);
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
      await sendRegenerateStream(token, sessionId, {
        onDelta: (chunk) => {
          streamedText += chunk;
          const segs = splitAssistantIntoSegments(streamedText, npcNames);
          updateAssistant(streamedText, segs);
        },
        onDone: (r: TurnResult) => {
          doneFired = true;
          setMeta({ turn: r.turn, day: r.day });
          updateAssistant(r.response, r.response_segments ?? []);
          if (r.events_triggered.length > 0) {
            const ev = r.events_triggered.map((x) => x.description || x.event_id).join(" · ");
            setLines((prev) => [
              ...prev,
              {
                role: "assistant",
                text: `[이벤트] ${ev}`,
                segments: [{ speaker: "이벤트", text: `[이벤트] ${ev}` }],
              },
            ]);
          }
        },
        onError: (m) => {
          setError(m);
          if (!doneFired) {
            setLines(before);
          }
        },
      });
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

  if (!token || !sessionId) {
    return <p className="px-4 py-8 text-slate-400">준비 중…</p>;
  }

  return (
    <div className="flex h-[100dvh] flex-col">
      <LoggedInNav />
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-3 px-4 pt-4 pb-2 sm:gap-4 sm:px-6 sm:pt-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Link to="/my" className="text-sm text-slate-400 hover:text-white">
            ← 마이페이지
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            {meta && (
              <span className="text-xs text-slate-500">
                Turn {meta.turn} · Day {meta.day}
              </span>
            )}
            <button
              type="button"
              onClick={() => void onRegenerate()}
              disabled={!canRegenerate}
              className="rounded-md border border-slate-600 px-2 py-1 text-xs text-slate-300 hover:border-slate-400 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              다시 생성
            </button>
          </div>
        </div>
        <div>
          <h1 className="text-lg font-semibold text-white">플레이</h1>
          <p className="mt-1 hidden text-xs text-slate-500 sm:block">
            대화는 같은 세션으로 돌아오면 서버에서 다시 불러옵니다.
          </p>
        </div>

        <div className="flex min-h-0 flex-1 flex-col rounded-xl border border-slate-800 bg-slate-900/40">
          <div className="flex-1 space-y-3 overflow-y-auto p-3 sm:p-4">
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
            <p className="border-t border-red-900/40 px-4 py-2 text-sm text-red-300">{error}</p>
          )}
          <form
            onSubmit={onSubmit}
            className="flex gap-2 border-t border-slate-800 p-3"
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
    </div>
  );
}
