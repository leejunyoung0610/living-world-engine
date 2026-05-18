import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchMe, SESSION_EXPIRED, type MeResponse } from "../api/auth";
import { TOKEN_KEY } from "../api/client";
import { SESSION_EXPIRED as PLAY_EXPIRED } from "../api/play";
import {
  exploreWorlds,
  fetchGenreMeta,
  SESSION_EXPIRED as W_SESSION,
  type ExploreSort,
  type ExploreWorldSummary,
  type GenreEntry,
} from "../api/worlds";
import { LoggedInNav } from "../components/LoggedInNav";

const PAGE_SIZE = 20;
const SORT_STORAGE_KEY = "homeExploreSort";

function readStoredSort(): ExploreSort {
  try {
    const raw = localStorage.getItem(SORT_STORAGE_KEY);
    if (raw === "recommended" || raw === "latest" || raw === "popular") return raw;
  } catch {
    /* ignore */
  }
  return "recommended";
}

function persistSort(next: ExploreSort) {
  try {
    localStorage.setItem(SORT_STORAGE_KEY, next);
  } catch {
    /* ignore */
  }
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

export function HomePage() {
  const nav = useNavigate();
  const [token, setToken] = useState<string | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [genreMeta, setGenreMeta] = useState<GenreEntry[]>([]);
  const [sort, setSort] = useState<ExploreSort>(() => readStoredSort());
  const [genreFilter, setGenreFilter] = useState<string>("");
  const [searchDraft, setSearchDraft] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [explore, setExplore] = useState<{
    items: ExploreWorldSummary[];
    total: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const genreLabel = useCallback(
    (slug: string) => genreMeta.find((g) => g.slug === slug)?.label ?? slug,
    [genreMeta],
  );

  const loadFirstPage = useCallback(
    async (t: string) => {
      setError(null);
      setExplore(null);
      try {
        const r = await exploreWorlds(t, {
          limit: PAGE_SIZE,
          offset: 0,
          sort,
          genre: genreFilter || null,
          q: searchQuery || null,
        });
        setExplore({ items: r.items, total: r.total });
      } catch (e) {
        const msg = e instanceof Error ? e.message : "";
        if (msg === W_SESSION || msg === PLAY_EXPIRED || msg === SESSION_EXPIRED) {
          localStorage.removeItem(TOKEN_KEY);
          nav("/login");
          return;
        }
        setError(e instanceof Error ? e.message : "목록을 불러오지 못했습니다.");
        setExplore({ items: [], total: 0 });
      }
    },
    [nav, sort, genreFilter, searchQuery],
  );

  useEffect(() => {
    const t = localStorage.getItem(TOKEN_KEY);
    if (!t) {
      nav("/login");
      return;
    }
    setToken(t);
    let cancelled = false;
    void fetchGenreMeta()
      .then((g) => {
        if (!cancelled) setGenreMeta(g);
      })
      .catch(() => {
        if (!cancelled) setGenreMeta([]);
      });
    (async () => {
      try {
        const m = await fetchMe(t);
        if (cancelled) return;
        setMe(m);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "";
        if (msg === SESSION_EXPIRED) {
          localStorage.removeItem(TOKEN_KEY);
          nav("/login");
          return;
        }
        if (!cancelled) setError("프로필을 불러오지 못했습니다.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [nav]);

  useEffect(() => {
    if (!token) return;
    void loadFirstPage(token);
  }, [token, loadFirstPage]);

  function onPlay(worldId: string) {
    nav(`/play/setup/${worldId}`);
  }

  function applySearch() {
    setSearchQuery(searchDraft.trim());
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
        sort,
        genre: genreFilter || null,
        q: searchQuery || null,
      });
      setExplore((prev) =>
        prev
          ? { total: r.total, items: [...prev.items, ...r.items] }
          : { total: r.total, items: r.items },
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      if (msg === W_SESSION || msg === PLAY_EXPIRED || msg === SESSION_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setError(e instanceof Error ? e.message : "추가 목록을 불러오지 못했습니다.");
    } finally {
      setLoadingMore(false);
    }
  }

  function Card({ w }: { w: ExploreWorldSummary }) {
    return (
      <li className="card">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="font-medium text-white">{w.name}</h3>
            <p className="mt-1 text-xs text-slate-500">
              by <span className="text-slate-400">{w.owner_username}</span>
              {w.is_mine && (
                <span className="ml-2 rounded bg-emerald-950/80 px-1.5 py-0.5 text-emerald-200">내 월드</span>
              )}
            </p>
            <div className="mt-2 flex flex-wrap gap-1">
              {(w.genres ?? []).map((g) => (
                <span
                  key={g}
                  className="rounded-md border border-slate-700 bg-slate-950/80 px-1.5 py-0.5 text-[10px] text-slate-400"
                >
                  {genreLabel(g)}
                </span>
              ))}
            </div>
            <p className="mt-1 font-mono text-xs text-slate-600">slug: {w.world_id}</p>
          </div>
        </div>
        <p className="mt-2 text-xs text-slate-600">
          플레이 시작 {w.play_start_count ?? 0}회 · 업데이트 {new Date(w.updated_at).toLocaleString()}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onPlay(w.id)}
            className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-500"
          >
            플레이 / 이어하기
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

  if (!token) {
    return <p className="px-4 py-8 text-slate-400">이동 중…</p>;
  }

  return (
    <div className="page-shell">
      <LoggedInNav />
      <div className="page-container-md">
        <div className="relative rounded-xl border border-slate-800 bg-slate-950/60 shadow-sm transition-colors focus-within:border-slate-600 focus-within:ring-1 focus-within:ring-slate-600">
          <span
            className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 text-slate-500"
            aria-hidden
          >
            <SearchIcon />
          </span>
          <input
            id="home-q"
            className="peer w-full rounded-xl border-0 bg-transparent py-3 pl-10 pr-12 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-0"
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && applySearch()}
            placeholder="월드 이름 검색…"
            aria-label="월드 이름 검색"
          />
          <button
            type="button"
            onClick={applySearch}
            className="absolute right-2 top-1/2 z-10 -translate-y-1/2 rounded-lg p-2 text-slate-400 transition hover:bg-slate-800 hover:text-white"
            aria-label="검색 적용"
          >
            <SearchIcon />
          </button>
        </div>

        <h1 className="mt-8 text-2xl font-semibold text-white">홈</h1>
        {me && (
          <p className="mt-2 text-sm text-slate-300">
            <span className="font-medium text-slate-200">{me.username}</span>
          </p>
        )}

        <div className="mt-4 flex flex-row gap-2 sm:gap-3">
          <select
            id="home-genre"
            aria-label="장르"
            value={genreFilter}
            onChange={(e) => setGenreFilter(e.target.value)}
            className="min-w-0 flex-1 truncate rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white"
          >
            <option value="">전체 장르</option>
            {genreMeta.map((g) => (
              <option key={g.slug} value={g.slug}>
                {g.label}
              </option>
            ))}
          </select>
          <select
            id="home-sort"
            aria-label="정렬"
            value={sort}
            onChange={(e) => {
              const v = e.target.value as ExploreSort;
              setSort(v);
              persistSort(v);
            }}
            className="w-[8.5rem] shrink-0 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white sm:w-[9.5rem]"
          >
            <option value="recommended">추천순</option>
            <option value="latest">최신순</option>
            <option value="popular">인기순</option>
          </select>
        </div>

        {explore !== null && explore.total > 0 && (
          <p className="mt-4 text-sm text-slate-500">
            {explore.items.length} / {explore.total}개 표시
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
            <p className="text-slate-400">조건에 맞는 공개 월드가 없습니다.</p>
            <Link
              to="/my"
              className="mt-4 inline-block text-sm text-indigo-400 hover:text-indigo-300"
            >
              마이페이지
            </Link>
          </div>
        ) : (
          <div className="mt-8 space-y-6">
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
      </div>
    </div>
  );
}
