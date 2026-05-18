import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchMe, type MeResponse } from "../api/auth";
import { TOKEN_KEY } from "../api/client";
import {
  listPlaySessions,
  SESSION_EXPIRED as PLAY_EXPIRED,
  type SessionSummary,
} from "../api/play";
import { deleteWorld, listWorlds, SESSION_EXPIRED, type WorldSummary } from "../api/worlds";
import { LoggedInNav } from "../components/LoggedInNav";

const MAX_WORLDS = 3;

export function MyPage() {
  const nav = useNavigate();
  const [token, setToken] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [worlds, setWorlds] = useState<WorldSummary[] | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyWorldId, setBusyWorldId] = useState<string | null>(null);

  const loadAll = useCallback(async (t: string) => {
    setError(null);
    try {
      const [sess, w, m] = await Promise.all([listPlaySessions(t), listWorlds(t), fetchMe(t)]);
      setSessions(sess);
      setWorlds(w);
      setMe(m);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      if (msg === SESSION_EXPIRED || msg === PLAY_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setError(e instanceof Error ? e.message : "불러오지 못했습니다.");
      setSessions([]);
      setWorlds([]);
    }
  }, [nav]);

  useEffect(() => {
    const t = localStorage.getItem(TOKEN_KEY);
    if (!t) {
      nav("/login");
      return;
    }
    setToken(t);
    void loadAll(t);
  }, [nav, loadAll]);

  async function onDeleteWorld(id: string, name: string) {
    if (!token) return;
    if (!window.confirm(`「${name}」월드를 삭제할까요?`)) return;
    setBusyWorldId(id);
    setError(null);
    try {
      await deleteWorld(token, id);
      await loadAll(token);
    } catch (e) {
      if (e instanceof Error && e.message === SESSION_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setError(e instanceof Error ? e.message : "삭제 실패");
    } finally {
      setBusyWorldId(null);
    }
  }

  function onPlayWorld(worldId: string) {
    nav(`/play/setup/${worldId}`);
  }

  function onRestartSession(s: SessionSummary) {
    if (!window.confirm(`「${s.world_name}」진행을 초기화하고 처음부터 시작할까요?`)) return;
    nav(`/play/setup/${s.world_id}?forceNew=1`);
  }

  if (!token) {
    return <p className="px-4 py-8 text-slate-400">이동 중…</p>;
  }

  const atLimit = worlds !== null && worlds.length >= MAX_WORLDS;
  const loading = sessions === null || worlds === null;

  return (
    <div className="page-shell">
      <LoggedInNav />
      <div className="page-container-wide space-y-12 sm:space-y-16">
        <header>
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h1 className="text-2xl font-semibold text-white">마이페이지</h1>
            {me && (
              <span className="text-xs text-slate-500">
                {me.email}
                {me.kakao_linked && (
                  <span className="ml-2 inline-flex items-center rounded bg-[#FEE500]/20 px-1.5 py-0.5 text-[10px] font-semibold text-amber-200">
                    카카오 연동
                  </span>
                )}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-slate-400">
            만든 월드와 진행 중인 플레이를 한곳에서 관리합니다.
          </p>
          <p className="mt-3 text-sm text-slate-500">
            다른 사람의 공개 월드는{" "}
            <Link to="/" className="font-medium text-indigo-400 hover:text-indigo-300">
              홈
            </Link>
            에서 추천·최신·인기 순으로 골라 플레이할 수 있습니다.
          </p>
        </header>

        {error && (
          <p className="rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}

        {/* 플레이 중 */}
        <section aria-labelledby="my-play-heading">
          <h2 id="my-play-heading" className="text-lg font-semibold text-white">
            플레이 중인 게임
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            월드당 하나의 진행이 유지됩니다. 서버를 재시작하면 목록이 비워질 수 있습니다.
          </p>

          {loading ? (
            <p className="mt-6 text-slate-500">불러오는 중…</p>
          ) : sessions.length === 0 ? (
            <div className="mt-6 rounded-xl border border-dashed border-slate-700 bg-slate-900/40 px-6 py-10 text-center">
              <p className="text-slate-400">진행 중인 게임이 없습니다.</p>
              <p className="mt-2 text-xs text-slate-500">
                아래「내가 만든 월드」에서 플레이를 시작하거나, 상단 「홈」에서 공개 월드를 플레이하세요.
              </p>
            </div>
          ) : (
            <ul className="mt-6 space-y-4">
              {sessions.map((s) => (
                <li key={s.session_id} className="card">
                  <div>
                    <h3 className="text-lg font-medium text-white">{s.world_name || "(이름 없음)"}</h3>
                    <p className="mt-1 text-xs text-slate-500">
                      Turn {s.turn} · Day {s.day}
                    </p>
                  </div>
                  {s.last_message_preview && (
                    <p className="mt-3 line-clamp-2 text-sm text-slate-400">{s.last_message_preview}</p>
                  )}
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Link
                      to={`/play/${s.session_id}`}
                      className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-500"
                    >
                      이어하기
                    </Link>
                    <button
                      type="button"
                      onClick={() => onRestartSession(s)}
                      className="rounded-md border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800"
                    >
                      처음부터
                    </button>
                    <Link
                      to={`/worlds/${s.world_id}`}
                      className="rounded-md border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
                    >
                      월드 편집
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* 내 월드 */}
        <section aria-labelledby="my-worlds-heading">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 id="my-worlds-heading" className="text-lg font-semibold text-white">
                내가 만든 월드
              </h2>
              <p className="mt-1 text-sm text-slate-400">
                계정당 최대 {MAX_WORLDS}개 · 같은 월드는 플레이 진행이 이어집니다.
              </p>
            </div>
            <Link
              to="/worlds/new"
              className={`inline-flex justify-center rounded-lg px-4 py-2 text-sm font-medium transition ${
                atLimit
                  ? "cursor-not-allowed bg-slate-800 text-slate-500"
                  : "bg-indigo-600 text-white hover:bg-indigo-500"
              }`}
              aria-disabled={atLimit}
              onClick={(e) => atLimit && e.preventDefault()}
            >
              새 월드
            </Link>
          </div>

          {atLimit && (
            <p className="mt-4 rounded-lg border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-sm text-amber-200/90">
              월드 개수 한도에 도달했습니다. 기존 월드를 삭제한 뒤 새로 만드세요.
            </p>
          )}

          {loading ? (
            <p className="mt-6 text-slate-500">불러오는 중…</p>
          ) : worlds.length === 0 ? (
            <div className="mt-6 rounded-xl border border-dashed border-slate-700 bg-slate-900/40 px-6 py-12 text-center">
              <p className="text-slate-400">아직 만든 월드가 없습니다.</p>
              <Link
                to="/worlds/new"
                className={`mt-4 inline-block text-sm font-medium text-indigo-400 hover:text-indigo-300 ${atLimit ? "pointer-events-none text-slate-600" : ""}`}
              >
                첫 월드 만들기 →
              </Link>
            </div>
          ) : (
            <ul className="mt-6 grid gap-4 sm:grid-cols-2">
              {worlds.map((w) => (
                <li key={w.id} className="card flex flex-col transition hover:border-slate-700">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-medium text-white">{w.name}</h3>
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-medium ${
                        w.visibility === "public"
                          ? "bg-emerald-950/80 text-emerald-200"
                          : "bg-slate-800 text-slate-400"
                      }`}
                    >
                      {w.visibility === "public" ? "공개" : "비공개"}
                    </span>
                  </div>
                  <p className="mt-1 font-mono text-xs text-slate-500">id: {w.world_id}</p>
                  <p className="mt-2 text-xs text-slate-600">{new Date(w.created_at).toLocaleString()}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={busyWorldId === w.id}
                      onClick={() => onPlayWorld(w.id)}
                      className="rounded-md bg-indigo-700 px-3 py-1.5 text-sm text-white hover:bg-indigo-600 disabled:opacity-50"
                    >
                      플레이 / 이어하기
                    </button>
                    <Link
                      to={`/worlds/${w.id}`}
                      className="rounded-md bg-slate-800 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700"
                    >
                      편집
                    </Link>
                    <button
                      type="button"
                      disabled={busyWorldId === w.id}
                      onClick={() => onDeleteWorld(w.id, w.name)}
                      className="rounded-md border border-red-900/60 px-3 py-1.5 text-sm text-red-300 hover:bg-red-950/40 disabled:opacity-50"
                    >
                      {busyWorldId === w.id ? "…" : "삭제"}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* 좋아요 (예정) */}
        <section aria-labelledby="my-likes-heading">
          <h2 id="my-likes-heading" className="text-lg font-semibold text-white">
            좋아요한 월드
          </h2>
          <p className="mt-1 text-sm text-slate-500">곧 추가됩니다.</p>
          <div className="mt-4 rounded-xl border border-dashed border-slate-700 bg-slate-900/30 px-6 py-10 text-center text-sm text-slate-500">
            좋아요 목록은 추후 연결됩니다. 지금은 「홈」에서 공개 월드를 찾을 수 있습니다.
          </div>
        </section>
      </div>
    </div>
  );
}
