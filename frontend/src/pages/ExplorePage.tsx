import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";
import { startPlay, SESSION_EXPIRED as PLAY_EXPIRED } from "../api/play";
import { exploreWorlds, SESSION_EXPIRED, type ExploreWorldSummary } from "../api/worlds";
import { LoggedInNav } from "../components/LoggedInNav";

const PAGE_SIZE = 20;

export function ExplorePage() {
  const nav = useNavigate();
  const [token, setToken] = useState<string | null>(null);
  const [explore, setExplore] = useState<{
    items: ExploreWorldSummary[];
    total: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [startingId, setStartingId] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const load = useCallback(async (t: string) => {
    setError(null);
    try {
      const r = await exploreWorlds(t, { limit: PAGE_SIZE, offset: 0 });
      setExplore({ items: r.items, total: r.total });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      if (msg === SESSION_EXPIRED || msg === PLAY_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setError(e instanceof Error ? e.message : "목록을 불러오지 못했습니다.");
      setExplore({ items: [], total: 0 });
    }
  }, [nav]);

  useEffect(() => {
    const t = localStorage.getItem(TOKEN_KEY);
    if (!t) {
      nav("/login");
      return;
    }
    setToken(t);
    void load(t);
  }, [nav, load]);

  async function onPlay(worldId: string) {
    if (!token) return;
    setStartingId(worldId);
    setError(null);
    try {
      const { session_id } = await startPlay(token, worldId);
      nav(`/play/${session_id}`);
    } catch (e) {
      if (e instanceof Error && e.message === PLAY_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setError(e instanceof Error ? e.message : "플레이 시작 실패");
    } finally {
      setStartingId(null);
    }
  }

  async function onLoadMore() {
    if (!token || explore === null || loadingMore) return;
    if (explore.items.length >= explore.total) return;
    setLoadingMore(true);
    setError(null);
    try {
      const r = await exploreWorlds(token, {
        limit: PAGE_SIZE,
        offset: explore.items.length,
      });
      setExplore((prev) =>
        prev
          ? { total: r.total, items: [...prev.items, ...r.items] }
          : { total: r.total, items: r.items },
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      if (msg === SESSION_EXPIRED || msg === PLAY_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setError(e instanceof Error ? e.message : "추가 목록을 불러오지 못했습니다.");
    } finally {
      setLoadingMore(false);
    }
  }

  if (!token) {
    return <p className="px-4 py-8 text-slate-400">이동 중…</p>;
  }

  function Card({ w }: { w: ExploreWorldSummary }) {
    return (
      <li className="rounded-xl border border-slate-800 bg-slate-900/50 p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="font-medium text-white">{w.name}</h3>
            <p className="mt-1 text-xs text-slate-500">
              by <span className="text-slate-400">{w.owner_username}</span>
              {w.is_mine && (
                <span className="ml-2 rounded bg-emerald-950/80 px-1.5 py-0.5 text-emerald-200">내 월드</span>
              )}
            </p>
            <p className="mt-1 font-mono text-xs text-slate-600">slug: {w.world_id}</p>
          </div>
        </div>
        <p className="mt-2 text-xs text-slate-600">
          업데이트 {new Date(w.updated_at).toLocaleString()}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={startingId === w.id}
            onClick={() => onPlay(w.id)}
            className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {startingId === w.id ? "시작 중…" : "플레이 / 이어하기"}
          </button>
          {w.is_mine && (
            <Link
              to={`/worlds/${w.id}`}
              className="rounded-md border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800"
            >
              편집
            </Link>
          )}
        </div>
      </li>
    );
  }

  return (
    <div className="min-h-screen">
      <LoggedInNav />
      <div className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-semibold text-white">탐색</h1>
        <p className="mt-2 text-sm text-slate-400">
          공개로 설정된 월드가 여기에 보입니다. 내가 올린 공개 월드와 다른 사람의 월드를 함께 플레이할 수 있습니다.
        </p>
        <p className="mt-1 text-xs text-slate-600">
          비공개 월드는 목록에 나오지 않으며, 소유자만 플레이할 수 있습니다.
        </p>
        {explore !== null && explore.total > 0 && (
          <p className="mt-2 text-sm text-slate-500">
            최신순 · {explore.items.length} / {explore.total}개 표시
          </p>
        )}

        {error && (
          <p className="mt-4 rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}

        {explore === null ? (
          <p className="mt-10 text-slate-500">불러오는 중…</p>
        ) : explore.items.length === 0 ? (
          <div className="mt-10 rounded-xl border border-dashed border-slate-700 bg-slate-900/40 px-6 py-12 text-center">
            <p className="text-slate-400">아직 공개된 월드가 없습니다.</p>
            <p className="mt-2 text-sm text-slate-500">
              마이페이지에서 월드를 만들고「공개 (탐색)」로 저장해 보세요.
            </p>
            <Link
              to="/my"
              className="mt-4 inline-block text-sm font-medium text-indigo-400 hover:text-indigo-300"
            >
              마이페이지로 →
            </Link>
          </div>
        ) : (
          <div className="mt-10 space-y-6">
            <ul className="space-y-4">
              {explore.items.map((w) => (
                <Card key={w.id} w={w} />
              ))}
            </ul>
            {explore.items.length < explore.total && (
              <div className="flex justify-center pt-2">
                <button
                  type="button"
                  disabled={loadingMore}
                  onClick={() => void onLoadMore()}
                  className="rounded-md border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
                >
                  {loadingMore ? "불러오는 중…" : "더 보기"}
                </button>
              </div>
            )}
          </div>
        )}

        <p className="mt-12 text-center text-sm text-slate-500">
          <Link to="/my" className="text-indigo-400 hover:text-indigo-300">
            마이페이지
          </Link>
        </p>
      </div>
    </div>
  );
}
