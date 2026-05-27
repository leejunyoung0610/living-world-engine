import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";
import {
  fetchPlayWorldBrief,
  SESSION_EXPIRED as PLAY_EXPIRED,
  startPlay,
  tryResumePlay,
  type PlayWorldBrief,
} from "../api/play";
import { LoggedInNav } from "../components/LoggedInNav";

type StatRow = { key: string; value: string };

function parseStatRows(rows: StatRow[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const { key, value } of rows) {
    const k = key.trim();
    if (!k) continue;
    const n = Number(String(value).trim());
    if (!Number.isFinite(n)) continue;
    out[k] = n;
  }
  return out;
}

/** 브라우저 표시용 — HTTPS URL 만 (공개 상세·brief API 동일 철학). */
function httpsImageUrl(raw?: string): string | null {
  const u = (raw ?? "").trim();
  return u.startsWith("https://") ? u : null;
}

export function PlaySetupPage() {
  const { worldId } = useParams<{ worldId: string }>();
  const [searchParams] = useSearchParams();
  const nav = useNavigate();
  const forceNew = searchParams.get("forceNew") === "1";

  const [token, setToken] = useState<string | null>(null);
  const [brief, setBrief] = useState<PlayWorldBrief | null>(null);
  const [loadingBrief, setLoadingBrief] = useState(true);
  const [tryingResume, setTryingResume] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [name, setName] = useState("");
  const [pclass, setPclass] = useState("");
  const [statRows, setStatRows] = useState<StatRow[]>([
    { key: "hp", value: "10" },
    { key: "mana", value: "5" },
    { key: "focus", value: "5" },
  ]);

  const redirectIfExpired = useCallback(
    (e: unknown) => {
      if (e instanceof Error && e.message === PLAY_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return true;
      }
      return false;
    },
    [nav],
  );

  useEffect(() => {
    const t = localStorage.getItem(TOKEN_KEY);
    if (!t) {
      nav("/login");
      return;
    }
    setToken(t);
  }, [nav]);

  useEffect(() => {
    if (!token || !worldId) return;

    (async () => {
      if (!forceNew) {
        setTryingResume(true);
        try {
          const resumed = await tryResumePlay(token, worldId);
          if (resumed?.resumed && resumed.session_id) {
            nav(`/play/${resumed.session_id}`, { replace: true });
            return;
          }
        } catch (e) {
          if (redirectIfExpired(e)) return;
        } finally {
          setTryingResume(false);
        }
      } else {
        setTryingResume(false);
      }

      setLoadingBrief(true);
      setError(null);
      try {
        const b = await fetchPlayWorldBrief(token, worldId);
        setBrief(b);
        const sug = b.suggested_player;
        if (sug && typeof sug === "object") {
          const sn = sug.name;
          const sc = sug.class;
          if (typeof sn === "string" && sn) setName(sn);
          if (typeof sc === "string" && sc) setPclass(sc);
          const st = sug.stats;
          if (st && typeof st === "object" && !Array.isArray(st)) {
            const entries = Object.entries(st as Record<string, unknown>)
              .filter(([, v]) => typeof v === "number" || typeof v === "string")
              .map(([k, v]) => ({ key: k, value: String(v) }));
            if (entries.length > 0) setStatRows(entries);
          }
        }
      } catch (e) {
        if (redirectIfExpired(e)) return;
        setError(e instanceof Error ? e.message : "월드 정보를 불러오지 못했습니다.");
        setBrief(null);
      } finally {
        setLoadingBrief(false);
      }
    })();
  }, [token, worldId, forceNew, nav, redirectIfExpired]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token || !worldId) return;
    const trimmed = name.trim();
    if (!trimmed) {
      setError("캐릭터 이름을 입력하세요.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const stats = parseStatRows(statRows);
      const r = await startPlay(token, worldId, {
        forceNew,
        player: {
          name: trimmed,
          class: pclass.trim() || "traveler",
          stats,
        },
      });
      nav(`/play/${r.session_id}`);
    } catch (err) {
      if (redirectIfExpired(err)) return;
      setError(err instanceof Error ? err.message : "세션 시작 실패");
    } finally {
      setSubmitting(false);
    }
  }

  const playBriefHeroUrl = brief != null ? httpsImageUrl(brief.cover_image_url) : null;

  if (!token || !worldId) {
    return <p className="px-4 py-8 text-slate-400">이동 중…</p>;
  }

  if (tryingResume || loadingBrief) {
    return (
      <div className="page-shell">
        <LoggedInNav />
        <p className="page-container-md text-slate-500">{tryingResume ? "진행 복구 확인 중…" : "월드 불러오는 중…"}</p>
      </div>
    );
  }

  return (
    <div className="page-shell">
      <LoggedInNav />
      <div className="page-container-md">
        <p className="text-sm text-slate-500">
          <Link to="/my" className="text-indigo-400 hover:text-indigo-300">
            마이페이지
          </Link>
          {" · "}
          <Link to="/" className="text-indigo-400 hover:text-indigo-300">
            홈
          </Link>
        </p>
        <h1 className="mt-4 text-2xl font-semibold text-white">입장 캐릭터</h1>
        <p className="mt-2 text-sm text-slate-400">
          월드에 저장된 NPC·세계관은 그대로 두고, 이 플레이에서만 사용할 캐릭터를 정합니다.
        </p>

        {brief && (
          <div className="mt-6 overflow-hidden rounded-xl border border-slate-800 bg-slate-900/50">
            {!playBriefHeroUrl ? (
              <div className="p-4">
                <h2 className="text-sm font-medium text-slate-200">{brief.story_title || brief.list_name}</h2>
                <p className="mt-1 text-xs text-slate-500">목록 이름: {brief.list_name}</p>
              </div>
            ) : (
              <div className="relative border-b border-slate-800">
                <div className="aspect-[21/9] max-h-48 w-full overflow-hidden bg-slate-950 sm:max-h-56">
                  <img
                    src={playBriefHeroUrl}
                    alt=""
                    className="h-full w-full object-cover object-center"
                    loading="lazy"
                    referrerPolicy="no-referrer"
                  />
                </div>
                <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-slate-950 via-slate-950/50 to-transparent px-4 pb-4 pt-12">
                  <h2 className="text-base font-semibold text-white drop-shadow">{brief.story_title || brief.list_name}</h2>
                  <p className="mt-0.5 text-xs text-slate-300">목록 이름: {brief.list_name}</p>
                </div>
              </div>
            )}
            <div className="p-4">
              {brief.description ? (
                <p className="mt-1 text-sm text-slate-400">{brief.description}</p>
              ) : null}
              {brief.world_setting ? (
                <div className="mt-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">세계관 설정</p>
                  <pre className="mt-2 max-h-64 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-slate-800 bg-slate-950/80 p-3 text-sm text-slate-300">
                    {brief.world_setting}
                  </pre>
                </div>
              ) : null}
              {brief.npcs.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">이 월드의 NPC</p>
                  <ul className="mt-3 space-y-2">
                    {brief.npcs.map((n, i) => {
                      const row = n as Record<string, unknown>;
                      const port =
                        httpsImageUrl(
                          typeof row.portrait_url === "string"
                            ? row.portrait_url
                            : typeof row.portrait_image_url === "string"
                              ? row.portrait_image_url
                              : undefined,
                        );
                      const nm =
                        typeof row.name === "string" ? row.name : `NPC ${i + 1}`;
                      const rl = typeof row.role === "string" ? row.role : "";
                      return (
                        <li key={i} className="flex gap-3 rounded-lg border border-slate-800/80 bg-slate-950/40 px-3 py-2">
                          {port ? (
                            <img
                              src={port}
                              alt=""
                              className="mt-0.5 h-14 w-14 shrink-0 rounded-md border border-slate-700 object-cover"
                              loading="lazy"
                              referrerPolicy="no-referrer"
                            />
                          ) : (
                            <div className="mt-0.5 flex h-14 w-14 shrink-0 items-center justify-center rounded-md border border-dashed border-slate-700 bg-slate-900 text-xs text-slate-600">
                              NPC
                            </div>
                          )}
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-slate-200">{nm}</p>
                            {rl ? <p className="mt-0.5 text-xs text-slate-500">{rl}</p> : null}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}

        {forceNew && (
          <p className="mt-4 rounded-lg border border-amber-900/40 bg-amber-950/25 px-3 py-2 text-sm text-amber-200/90">
            새 캐릭터로 처음부터 시작합니다. (기존 이어하기는 건너뜁니다.)
          </p>
        )}

        {error && (
          <p className="mt-4 rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}

        <form onSubmit={(e) => void onSubmit(e)} className="mt-6 space-y-4">
          <div>
            <label htmlFor="pc-name" className="block text-sm font-medium text-slate-300">
              이름
            </label>
            <input
              id="pc-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white placeholder:text-slate-600"
              placeholder="캐릭터 이름"
              autoComplete="off"
            />
          </div>
          <div>
            <label htmlFor="pc-class" className="block text-sm font-medium text-slate-300">
              직업 / 역할 (선택)
            </label>
            <input
              id="pc-class"
              value={pclass}
              onChange={(e) => setPclass(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white placeholder:text-slate-600"
              placeholder="예: 모험가"
              autoComplete="off"
            />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-300">스탯</p>
            <ul className="mt-2 space-y-2">
              {statRows.map((row, i) => (
                <li key={i} className="flex gap-2">
                  <input
                    value={row.key}
                    onChange={(e) => {
                      const next = [...statRows];
                      next[i] = { ...next[i], key: e.target.value };
                      setStatRows(next);
                    }}
                    className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                    placeholder="이름"
                  />
                  <input
                    type="text"
                    inputMode="decimal"
                    value={row.value}
                    onChange={(e) => {
                      const next = [...statRows];
                      next[i] = { ...next[i], value: e.target.value };
                      setStatRows(next);
                    }}
                    className="w-24 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                    placeholder="값"
                  />
                  <button
                    type="button"
                    onClick={() => setStatRows(statRows.filter((_, j) => j !== i))}
                    className="rounded-lg border border-slate-700 px-2 text-slate-400 hover:bg-slate-800"
                    aria-label="행 삭제"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={() => setStatRows([...statRows, { key: "", value: "" }])}
              className="mt-2 text-sm text-indigo-400 hover:text-indigo-300"
            >
              + 스탯 줄 추가
            </button>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {submitting ? "입장 중…" : "이 세계로 들어가기"}
          </button>
        </form>
      </div>
    </div>
  );
}
