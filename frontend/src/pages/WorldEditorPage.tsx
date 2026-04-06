import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";
import {
  createWorld,
  EMPTY_CHARACTERS,
  EMPTY_WORLD,
  getWorld,
  SESSION_EXPIRED,
  updateWorld,
  type WorldVisibility,
} from "../api/worlds";
import { LoggedInNav } from "../components/LoggedInNav";

function stringifyJson(v: unknown): string {
  return JSON.stringify(v, null, 2);
}

export function WorldEditorPage({ create }: { create?: boolean }) {
  const { worldId } = useParams<{ worldId: string }>();
  const nav = useNavigate();
  const isCreate = create === true;

  const [token, setToken] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [worldText, setWorldText] = useState(stringifyJson(EMPTY_WORLD));
  const [charsText, setCharsText] = useState(stringifyJson(EMPTY_CHARACTERS));
  const [eventsText, setEventsText] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!isCreate);
  const [saving, setSaving] = useState(false);
  const [visibility, setVisibility] = useState<WorldVisibility>("private");

  useEffect(() => {
    const t = localStorage.getItem(TOKEN_KEY);
    if (!t) {
      nav("/login");
      return;
    }
    setToken(t);

    if (isCreate) {
      setLoading(false);
      return;
    }

    const id = worldId;
    if (!id) {
      nav("/my");
      return;
    }

    (async () => {
      try {
        const w = await getWorld(t, id);
        setName(w.name);
        setVisibility(w.visibility === "public" ? "public" : "private");
        setWorldText(stringifyJson(w.world));
        setCharsText(stringifyJson(w.characters));
        setEventsText(w.events ? stringifyJson(w.events) : "");
      } catch (e) {
        if (e instanceof Error && e.message === SESSION_EXPIRED) {
          localStorage.removeItem(TOKEN_KEY);
          nav("/login");
          return;
        }
        setApiError(e instanceof Error ? e.message : "불러오기 실패");
      } finally {
        setLoading(false);
      }
    })();
  }, [create, isCreate, nav, worldId]);

  function applyTemplate() {
    setWorldText(stringifyJson(EMPTY_WORLD));
    setCharsText(stringifyJson(EMPTY_CHARACTERS));
    setEventsText("");
    setParseError(null);
  }

  function parseBodies():
    | { ok: true; world: Record<string, unknown>; characters: Record<string, unknown>; events: Record<string, unknown> | null }
    | { ok: false; message: string } {
    let world: unknown;
    let characters: unknown;
    let events: Record<string, unknown> | null = null;
    try {
      world = JSON.parse(worldText) as unknown;
    } catch {
      return { ok: false, message: "world JSON 파싱 실패 — 괄호·쉼표를 확인하세요." };
    }
    try {
      characters = JSON.parse(charsText) as unknown;
    } catch {
      return { ok: false, message: "characters JSON 파싱 실패" };
    }
    const et = eventsText.trim();
    if (et) {
      try {
        events = JSON.parse(et) as Record<string, unknown>;
      } catch {
        return { ok: false, message: "events JSON 파싱 실패" };
      }
    }
    if (!world || typeof world !== "object" || Array.isArray(world)) {
      return { ok: false, message: "world 는 객체(JSON)여야 합니다." };
    }
    if (!characters || typeof characters !== "object" || Array.isArray(characters)) {
      return { ok: false, message: "characters 는 객체(JSON)여야 합니다." };
    }
    return {
      ok: true,
      world: world as Record<string, unknown>,
      characters: characters as Record<string, unknown>,
      events,
    };
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setParseError(null);
    setApiError(null);
    const parsed = parseBodies();
    if (!parsed.ok) {
      setParseError(parsed.message);
      return;
    }
    setSaving(true);
    try {
      if (isCreate) {
        await createWorld(token, {
          name: name.trim() || "이름 없음",
          world: parsed.world,
          characters: parsed.characters,
          events: parsed.events,
          visibility,
        });
      } else if (worldId) {
        await updateWorld(token, worldId, {
          name: name.trim() || "이름 없음",
          world: parsed.world,
          characters: parsed.characters,
          events: parsed.events,
          visibility,
        });
      }
      nav("/my");
    } catch (err) {
      if (err instanceof Error && err.message === SESSION_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setApiError(err instanceof Error ? err.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  }

  if (!token) {
    return <p className="px-4 py-8 text-slate-400">이동 중…</p>;
  }

  return (
    <div className="min-h-screen">
      <LoggedInNav />
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center gap-4">
          <Link to="/my" className="text-sm text-slate-400 hover:text-white">
            ← 마이페이지
          </Link>
          <h1 className="text-xl font-semibold text-white">
            {isCreate ? "새 월드" : "월드 편집"}
          </h1>
        </div>

        {loading ? (
          <p className="text-slate-500">불러오는 중…</p>
        ) : (
          <form onSubmit={onSubmit} className="flex flex-col gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-300">표시 이름</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white"
                placeholder="목록에 보이는 이름"
              />
            </div>

            <fieldset className="rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3">
              <legend className="px-1 text-sm font-medium text-slate-300">공개 범위</legend>
              <label className="mt-2 flex cursor-pointer items-start gap-2 text-sm text-slate-300">
                <input
                  type="radio"
                  name="visibility"
                  checked={visibility === "private"}
                  onChange={() => setVisibility("private")}
                  className="mt-1"
                />
                <span>
                  <span className="font-medium text-white">비공개</span>
                  <span className="mt-0.5 block text-xs text-slate-500">
                    나만 플레이·편집할 수 있습니다.
                  </span>
                </span>
              </label>
              <label className="mt-3 flex cursor-pointer items-start gap-2 text-sm text-slate-300">
                <input
                  type="radio"
                  name="visibility"
                  checked={visibility === "public"}
                  onChange={() => setVisibility("public")}
                  className="mt-1"
                />
                <span>
                  <span className="font-medium text-white">공개 (탐색)</span>
                  <span className="mt-0.5 block text-xs text-slate-500">
                    탐색에 노출되며, 로그인한 다른 유저도 플레이할 수 있습니다. 편집은 여전히 나만 가능합니다.
                  </span>
                </span>
              </label>
            </fieldset>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={applyTemplate}
                className="rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
              >
                빈 템플릿으로 채우기
              </button>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300">world (JSON)</label>
              <p className="mt-0.5 text-xs text-slate-500">필수 키: id, name</p>
              <textarea
                value={worldText}
                onChange={(e) => setWorldText(e.target.value)}
                rows={14}
                spellCheck={false}
                className="mt-1 w-full resize-y rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm text-slate-200"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300">characters (JSON)</label>
              <p className="mt-0.5 text-xs text-slate-500">필수 키: player, npcs</p>
              <textarea
                value={charsText}
                onChange={(e) => setCharsText(e.target.value)}
                rows={12}
                spellCheck={false}
                className="mt-1 w-full resize-y rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm text-slate-200"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300">events (JSON, 선택)</label>
              <textarea
                value={eventsText}
                onChange={(e) => setEventsText(e.target.value)}
                rows={6}
                spellCheck={false}
                placeholder="비우면 null"
                className="mt-1 w-full resize-y rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm text-slate-200 placeholder:text-slate-600"
              />
            </div>

            {parseError && (
              <p className="rounded-lg border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-sm text-amber-200">
                {parseError}
              </p>
            )}
            {apiError && (
              <p className="rounded-lg border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">
                {apiError}
              </p>
            )}

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {saving ? "저장 중…" : "저장"}
              </button>
              <Link
                to="/my"
                className="rounded-lg border border-slate-600 px-5 py-2 text-sm text-slate-300 hover:bg-slate-800"
              >
                취소
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
