import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { SESSION_EXPIRED } from "../api/auth";
import { TOKEN_KEY } from "../api/client";
import { SESSION_EXPIRED as PLAY_EXPIRED } from "../api/play";
import {
  fetchGenreMeta,
  fetchPublicWorld,
  SESSION_EXPIRED as W_SESSION,
  toggleWorldLike,
  type GenreEntry,
  type PublicWorldDetail,
} from "../api/worlds";
import { LoggedInNav } from "../components/LoggedInNav";

export function WorldBrowsePage() {
  const { worldId } = useParams<{ worldId: string }>();
  const nav = useNavigate();
  const [token, setToken] = useState<string | null>(null);
  const [genreMeta, setGenreMeta] = useState<GenreEntry[]>([]);
  const [data, setData] = useState<PublicWorldDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [likeBusy, setLikeBusy] = useState(false);

  const genreLabel = useCallback(
    (slug: string) => genreMeta.find((g) => g.slug === slug)?.label ?? slug,
    [genreMeta],
  );

  useEffect(() => {
    const t = localStorage.getItem(TOKEN_KEY);
    if (!t) {
      nav("/login");
      return;
    }
    setToken(t);
    void fetchGenreMeta()
      .then(setGenreMeta)
      .catch(() => setGenreMeta([]));
  }, [nav]);

  useEffect(() => {
    if (!token || !worldId) return;
    let cancelled = false;
    setError(null);
    setData(null);
    void fetchPublicWorld(token, worldId)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "";
        if (msg === W_SESSION || msg === PLAY_EXPIRED || msg === SESSION_EXPIRED) {
          localStorage.removeItem(TOKEN_KEY);
          nav("/login");
          return;
        }
        if (!cancelled) setError(msg || "월드를 불러오지 못했습니다.");
      });
    return () => {
      cancelled = true;
    };
  }, [token, worldId, nav]);

  async function onToggleLike() {
    if (!token || !worldId || !data || likeBusy) return;
    setLikeBusy(true);
    setError(null);
    try {
      const s = await toggleWorldLike(token, worldId);
      setData((prev) =>
        prev
          ? { ...prev, liked_by_me: s.liked, like_count: s.like_count }
          : prev,
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      if (msg === W_SESSION || msg === PLAY_EXPIRED || msg === SESSION_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setError(msg || "따봉 처리에 실패했습니다.");
    } finally {
      setLikeBusy(false);
    }
  }

  if (!token) {
    return <p className="px-4 py-8 text-slate-400">이동 중…</p>;
  }

  return (
    <div className="page-shell">
      <LoggedInNav />
      <div className="page-container-md">
        <p className="text-sm">
          <Link to="/" className="text-slate-500 hover:text-indigo-400">
            ← 홈
          </Link>
        </p>

        {error && (
          <p className="mt-4 rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}

        {data === null && !error ? (
          <p className="mt-8 text-slate-500">불러오는 중…</p>
        ) : data ? (
          <article className="mt-6 space-y-6">
            <header>
              <h1 className="text-2xl font-semibold text-white">{data.name}</h1>
              <p className="mt-2 text-sm text-slate-500">
                <span className="text-slate-400">{data.owner_username}</span>
                {data.is_mine && (
                  <span className="ml-2 rounded bg-emerald-950/80 px-1.5 py-0.5 text-emerald-200">내 월드</span>
                )}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {(data.genres ?? []).map((g) => (
                  <span
                    key={g}
                    className="rounded-md border border-slate-700 bg-slate-950/80 px-2 py-0.5 text-xs text-slate-400"
                  >
                    {genreLabel(g)}
                  </span>
                ))}
              </div>
            </header>

            <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500">
              <button
                type="button"
                disabled={likeBusy}
                onClick={() => void onToggleLike()}
                className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 font-medium transition ${
                  data.liked_by_me
                    ? "border-amber-700/80 bg-amber-950/40 text-amber-200"
                    : "border-slate-600 text-slate-300 hover:bg-slate-800"
                } disabled:opacity-50`}
              >
                <span aria-hidden>👍</span>
                <span>따봉 {data.like_count}</span>
              </button>
              <span>플레이 시작 {data.play_start_count}회</span>
              <span>NPC {data.npc_count}명</span>
              {data.time ? <span>시점: {data.time}</span> : null}
            </div>

            {data.description ? (
              <section>
                <h2 className="text-sm font-medium text-slate-400">소개</h2>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-300">{data.description}</p>
              </section>
            ) : null}

            {data.world_setting ? (
              <section>
                <h2 className="text-sm font-medium text-slate-400">세계 설정</h2>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-400">{data.world_setting}</p>
              </section>
            ) : null}

            <div className="flex flex-wrap gap-2 border-t border-slate-800 pt-6">
              <button
                type="button"
                onClick={() => nav(`/play/setup/${data.id}`)}
                className="rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-500"
              >
                플레이 / 이어하기
              </button>
              {data.is_mine ? (
                <Link
                  to={`/worlds/${data.id}`}
                  className="rounded-lg border border-slate-600 px-4 py-2.5 text-sm text-slate-200 hover:bg-slate-800"
                >
                  편집
                </Link>
              ) : null}
            </div>
          </article>
        ) : null}
      </div>
    </div>
  );
}
