import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";
import { deleteWorld, listWorlds, SESSION_EXPIRED, type WorldSummary } from "../api/worlds";
import { LoggedInNav } from "../components/LoggedInNav";

const MAX_WORLDS = 3;

export function WorldsListPage() {
  const nav = useNavigate();
  const [token, setToken] = useState<string | null>(null);
  const [worlds, setWorlds] = useState<WorldSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async (t: string) => {
    setError(null);
    try {
      setWorlds(await listWorlds(t));
    } catch (e) {
      if (e instanceof Error && e.message === SESSION_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setError(e instanceof Error ? e.message : "목록을 불러오지 못했습니다.");
      setWorlds([]);
    }
  }, []);

  useEffect(() => {
    const t = localStorage.getItem(TOKEN_KEY);
    if (!t) {
      nav("/login");
      return;
    }
    setToken(t);
    void load(t);
  }, [nav, load]);

  async function onDelete(id: string, name: string) {
    if (!token) return;
    if (!window.confirm(`「${name}」월드를 삭제할까요?`)) return;
    setBusyId(id);
    setError(null);
    try {
      await deleteWorld(token, id);
      await load(token);
    } catch (e) {
      if (e instanceof Error && e.message === SESSION_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setError(e instanceof Error ? e.message : "삭제 실패");
    } finally {
      setBusyId(null);
    }
  }

  if (!token) {
    return <p className="px-4 py-8 text-slate-400">이동 중…</p>;
  }

  const atLimit = worlds !== null && worlds.length >= MAX_WORLDS;

  return (
    <div className="min-h-screen">
      <LoggedInNav />
      <div className="mx-auto max-w-4xl px-4 py-10">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-white">내 월드</h1>
            <p className="mt-1 text-sm text-slate-400">
              계정당 최대 {MAX_WORLDS}개 · JSON으로 세계관을 편집합니다.
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

        {error && (
          <p className="mt-4 rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}

        {worlds === null ? (
          <p className="mt-10 text-slate-500">불러오는 중…</p>
        ) : worlds.length === 0 ? (
          <div className="mt-12 rounded-xl border border-dashed border-slate-700 bg-slate-900/40 px-6 py-12 text-center">
            <p className="text-slate-400">아직 만든 월드가 없습니다.</p>
            <Link
              to="/worlds/new"
              className={`mt-4 inline-block text-sm font-medium text-indigo-400 hover:text-indigo-300 ${atLimit ? "pointer-events-none text-slate-600" : ""}`}
            >
              첫 월드 만들기 →
            </Link>
          </div>
        ) : (
          <ul className="mt-8 grid gap-4 sm:grid-cols-2">
            {worlds.map((w) => (
              <li
                key={w.id}
                className="flex flex-col rounded-xl border border-slate-800 bg-slate-900/50 p-5 shadow-sm transition hover:border-slate-700"
              >
                <h2 className="font-medium text-white">{w.name}</h2>
                <p className="mt-1 font-mono text-xs text-slate-500">id: {w.world_id}</p>
                <p className="mt-2 text-xs text-slate-600">
                  {new Date(w.created_at).toLocaleString()}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Link
                    to={`/worlds/${w.id}`}
                    className="rounded-md bg-slate-800 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-700"
                  >
                    편집
                  </Link>
                  <button
                    type="button"
                    disabled={busyId === w.id}
                    onClick={() => onDelete(w.id, w.name)}
                    className="rounded-md border border-red-900/60 px-3 py-1.5 text-sm text-red-300 hover:bg-red-950/40 disabled:opacity-50"
                  >
                    {busyId === w.id ? "…" : "삭제"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
