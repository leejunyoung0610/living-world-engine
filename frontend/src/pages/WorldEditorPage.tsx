import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";
import {
  createWorld,
  EMPTY_CHARACTERS,
  EMPTY_WORLD,
  fetchGenreMeta,
  getWorld,
  SESSION_EXPIRED,
  updateWorld,
  type GenreEntry,
  type WorldVisibility,
} from "../api/worlds";
import { LoggedInNav } from "../components/LoggedInNav";
import {
  campusSampleForm,
  defaultSimpleForm,
  formToWorldPayload,
  slugifyWorldId,
  tryImportSimpleFromJson,
  type SimpleNpcRow,
  type SimpleWorldFormState,
} from "../utils/worldEditorSimple";

function stringifyJson(v: unknown): string {
  return JSON.stringify(v, null, 2);
}

type EditorMode = "simple" | "json";

export function WorldEditorPage({ create }: { create?: boolean }) {
  const { worldId } = useParams<{ worldId: string }>();
  const nav = useNavigate();
  const isCreate = create === true;

  const [token, setToken] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [editorMode, setEditorMode] = useState<EditorMode>("simple");
  const [simpleForm, setSimpleForm] = useState<SimpleWorldFormState>(defaultSimpleForm);
  const [worldText, setWorldText] = useState(stringifyJson(EMPTY_WORLD));
  const [charsText, setCharsText] = useState(stringifyJson(EMPTY_CHARACTERS));
  const [eventsText, setEventsText] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!isCreate);
  const [saving, setSaving] = useState(false);
  const [visibility, setVisibility] = useState<WorldVisibility>("private");
  const [genreCatalog, setGenreCatalog] = useState<GenreEntry[]>([]);
  const [selectedGenres, setSelectedGenres] = useState<string[]>(["fantasy"]);
  const [simpleImportWarn, setSimpleImportWarn] = useState<string | null>(null);

  useEffect(() => {
    const t = localStorage.getItem(TOKEN_KEY);
    if (!t) {
      nav("/login");
      return;
    }
    setToken(t);
    void fetchGenreMeta()
      .then(setGenreCatalog)
      .catch(() => setGenreCatalog([]));

    if (isCreate) {
      setLoading(false);
      setSelectedGenres(["fantasy"]);
      const init = defaultSimpleForm();
      setSimpleForm(init);
      setName(init.worldStoryName);
      const { world, characters } = formToWorldPayload({ ...init, worldStoryName: init.worldStoryName });
      setWorldText(stringifyJson(world));
      setCharsText(stringifyJson(characters));
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
        const g = Array.isArray(w.genres) ? w.genres.filter((x): x is string => typeof x === "string") : [];
        setSelectedGenres(g.length > 0 ? g : ["fantasy"]);
        setWorldText(stringifyJson(w.world));
        setCharsText(stringifyJson(w.characters));
        setEventsText(w.events ? stringifyJson(w.events) : "");
        const imp = tryImportSimpleFromJson(
          w.world as Record<string, unknown>,
          w.characters as Record<string, unknown>,
        );
        if (imp) {
          setSimpleForm({ ...imp, worldStoryName: w.world.name as string });
          setEditorMode("simple");
          setSimpleImportWarn(null);
        } else {
          setEditorMode("json");
          setSimpleImportWarn("이 월드는 구조가 복잡해 간편 모드를 쓸 수 없습니다. JSON으로 편집하세요.");
        }
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

  useEffect(() => {
    if (editorMode !== "simple") return;
    const { world, characters } = formToWorldPayload({
      ...simpleForm,
      worldStoryName: name.trim() || simpleForm.worldStoryName || "새 세계",
    });
    setWorldText(stringifyJson(world));
    setCharsText(stringifyJson(characters));
  }, [editorMode, simpleForm, name]);

  function applyJsonTemplate() {
    setWorldText(stringifyJson(EMPTY_WORLD));
    setCharsText(stringifyJson(EMPTY_CHARACTERS));
    setEventsText("");
    setParseError(null);
    const next = defaultSimpleForm();
    setSimpleForm(next);
    setEditorMode("json");
  }

  function applySimpleTemplate() {
    const next = defaultSimpleForm();
    setSimpleForm(next);
    setName("");
    setEditorMode("simple");
    setParseError(null);
  }

  function applyCampusSample() {
    const next = campusSampleForm();
    setSimpleForm(next);
    setName(next.worldStoryName);
    setEditorMode("simple");
    setParseError(null);
  }

  function switchToSimple() {
    setParseError(null);
    let world: unknown;
    let characters: unknown;
    try {
      world = JSON.parse(worldText) as unknown;
      characters = JSON.parse(charsText) as unknown;
    } catch {
      setParseError("JSON 형식이 맞지 않아 간편 모드로 바꿀 수 없습니다.");
      return;
    }
    if (!world || typeof world !== "object" || Array.isArray(world)) {
      setParseError("world 가 객체가 아닙니다.");
      return;
    }
    if (!characters || typeof characters !== "object" || Array.isArray(characters)) {
      setParseError("characters 가 객체가 아닙니다.");
      return;
    }
    const imp = tryImportSimpleFromJson(
      world as Record<string, unknown>,
      characters as Record<string, unknown>,
    );
    if (!imp) {
      setParseError("이 JSON은 간편 모드 필드로 옮길 수 없습니다. (world.id/name, npcs 배열 필요)");
      return;
    }
    setSimpleForm(imp);
    setEditorMode("simple");
  }

  function updateNpc(i: number, patch: Partial<SimpleNpcRow>) {
    setSimpleForm((s) => {
      const npcs = s.npcs.map((row, j) => (j === i ? { ...row, ...patch } : row));
      return { ...s, npcs };
    });
  }

  function addNpc() {
    setSimpleForm((s) => ({
      ...s,
      npcs: [...s.npcs, { id: "", name: "", role: "", location: "" }],
    }));
  }

  function removeNpc(i: number) {
    setSimpleForm((s) => ({
      ...s,
      npcs: s.npcs.filter((_, j) => j !== i),
    }));
  }

  function parseBodies():
    | { ok: true; world: Record<string, unknown>; characters: Record<string, unknown>; events: Record<string, unknown> | null }
    | { ok: false; message: string } {
    if (editorMode === "simple") {
      const { world, characters } = formToWorldPayload({
        ...simpleForm,
        worldStoryName: name.trim() || simpleForm.worldStoryName || "새 세계",
      });
      let events: Record<string, unknown> | null = null;
      const et = eventsText.trim();
      if (et) {
        try {
          events = JSON.parse(et) as Record<string, unknown>;
        } catch {
          return { ok: false, message: "events JSON 파싱 실패" };
        }
      }
      return { ok: true, world, characters, events };
    }

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
    if (selectedGenres.length === 0) {
      setParseError("장르를 최소 1개 선택해 주세요.");
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
          genres: selectedGenres,
        });
      } else if (worldId) {
        await updateWorld(token, worldId, {
          name: name.trim() || "이름 없음",
          world: parsed.world,
          characters: parsed.characters,
          events: parsed.events,
          visibility,
          genres: selectedGenres,
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
    <div className="page-shell">
      <LoggedInNav />
      <div className="page-container-wide">
        <div className="mb-6 flex flex-wrap items-center gap-3">
          <Link to="/my" className="text-sm text-slate-400 hover:text-white">
            ← 마이페이지
          </Link>
          <h1 className="text-xl font-semibold text-white">{isCreate ? "새 월드" : "월드 편집"}</h1>
        </div>

        {loading ? (
          <p className="text-slate-500">불러오는 중…</p>
        ) : (
          <form onSubmit={onSubmit} className="flex flex-col gap-6">
            <div className="flex flex-wrap gap-2 rounded-lg border border-slate-800 bg-slate-900/50 p-2">
              <button
                type="button"
                onClick={() => {
                  if (editorMode === "json") switchToSimple();
                }}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                  editorMode === "simple"
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                }`}
              >
                간편 만들기
              </button>
              <button
                type="button"
                onClick={() => {
                  setParseError(null);
                  setEditorMode("json");
                }}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                  editorMode === "json"
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                }`}
              >
                JSON (고급)
              </button>
            </div>

            {simpleImportWarn && (
              <p className="rounded-lg border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-sm text-amber-200">
                {simpleImportWarn}
              </p>
            )}

            <div>
              <label className="block text-sm font-medium text-slate-300">목록에 보이는 이름</label>
              <p className="mt-0.5 text-xs text-slate-500">마이페이지·탐색에 표시됩니다. 간편 모드에서는 스토리 속 세계 이름과 같이 씁니다.</p>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white"
                placeholder="예: 우리 학교 미스터리"
              />
            </div>

            <fieldset className="rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3">
              <legend className="px-1 text-sm font-medium text-slate-300">장르 (필수 · 복수 선택)</legend>
              <p className="mt-1 text-xs text-slate-500">홈 정렬·추천·필터에 사용됩니다.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {genreCatalog.map((g) => {
                  const on = selectedGenres.includes(g.slug);
                  return (
                    <button
                      key={g.slug}
                      type="button"
                      onClick={() =>
                        setSelectedGenres((prev) =>
                          on ? prev.filter((x) => x !== g.slug) : [...prev, g.slug],
                        )
                      }
                      className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                        on
                          ? "border-indigo-500 bg-indigo-950/80 text-indigo-100"
                          : "border-slate-600 bg-slate-950 text-slate-400 hover:border-slate-500"
                      }`}
                    >
                      {g.label}
                    </button>
                  );
                })}
              </div>
              {selectedGenres.length === 0 && (
                <p className="mt-2 text-xs text-amber-400">최소 1개를 선택해 주세요.</p>
              )}
            </fieldset>

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
                  <span className="mt-0.5 block text-xs text-slate-500">나만 플레이·편집할 수 있습니다.</span>
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
                  <span className="font-medium text-white">공개 (홈)</span>
                  <span className="mt-0.5 block text-xs text-slate-500">
                    홈 공개 목록에 노출되며, 로그인한 다른 유저도 플레이할 수 있습니다. 편집은 여전히 나만 가능합니다.
                  </span>
                </span>
              </label>
            </fieldset>

            {editorMode === "simple" && (
              <div className="space-y-5 rounded-xl border border-slate-800 bg-slate-950/40 p-5">
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={applySimpleTemplate}
                    className="rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
                  >
                    간편 폼 비우기
                  </button>
                  <button
                    type="button"
                    onClick={applyCampusSample}
                    className="rounded-lg border border-indigo-700 bg-indigo-950/40 px-3 py-1.5 text-sm text-indigo-200 hover:bg-indigo-950/70"
                  >
                    캠퍼스 샘플 (NPC 2)
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setSimpleForm((s) => ({ ...s, worldSlug: slugifyWorldId(name || s.worldStoryName) }))
                    }
                    className="rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
                  >
                    월드 ID 제안 (목록 이름 기준)
                  </button>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300">월드 ID</label>
                  <p className="mt-0.5 text-xs text-slate-500">영문·숫자·_ 권장. URL/저장용 식별자입니다.</p>
                  <input
                    type="text"
                    value={simpleForm.worldSlug}
                    onChange={(e) => setSimpleForm((s) => ({ ...s, worldSlug: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-sm text-white"
                    placeholder="my_world"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300">한 줄 설명</label>
                  <p className="mt-0.5 text-xs text-slate-500">
                    마이·탐색 카드·입장 화면 요약용으로 짧게 씁니다. (스토리 본문은 아래 세계관 설정)
                  </p>
                  <textarea
                    value={simpleForm.description}
                    onChange={(e) => setSimpleForm((s) => ({ ...s, description: e.target.value }))}
                    rows={2}
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                    placeholder="예: 관악 캠퍼스에서 펼쳐지는 하루하루"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300">커버 이미지 URL</label>
                  <p className="mt-0.5 text-xs text-slate-500">
                    공개 상세 상단 히어로로 쓰입니다. <strong className="text-slate-400">https://</strong> 만
                    허용. AI 이미지 도구가 준 링크·CDN URL을 붙여 넣으면 됩니다.
                  </p>
                  <input
                    type="url"
                    inputMode="url"
                    value={simpleForm.coverImageUrl}
                    onChange={(e) => setSimpleForm((s) => ({ ...s, coverImageUrl: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-sm text-white"
                    placeholder="https://…"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300">세계관 설정 (상세)</label>
                  <p className="mt-0.5 text-xs text-slate-500">
                    시대·지리·분위기·금지 사항 등 LLM이 따를 긴 설명. JSON 키는{" "}
                    <code className="text-slate-400">world_setting</code>
                  </p>
                  <textarea
                    value={simpleForm.worldSetting}
                    onChange={(e) => setSimpleForm((s) => ({ ...s, worldSetting: e.target.value }))}
                    rows={8}
                    spellCheck={false}
                    className="mt-1 w-full resize-y rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                    placeholder="예: 무대는 현대 한국 대학 캠퍼스. 판타지 없이 일상 드라마로…"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300">시간·분위기</label>
                  <input
                    type="text"
                    value={simpleForm.time}
                    onChange={(e) => setSimpleForm((s) => ({ ...s, time: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
                    placeholder="Day 1 · 개학철"
                  />
                </div>

                <p className="text-xs text-slate-500">
                  <strong className="text-slate-400">플레이어 캐릭터</strong>는 월드에 넣지 않습니다. 플레이
                  시작할 때「입장 캐릭터」화면에서 정합니다.
                </p>

                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <label className="text-sm font-medium text-slate-300">NPC</label>
                    <button
                      type="button"
                      onClick={addNpc}
                      className="rounded-md border border-slate-600 px-2 py-1 text-xs text-slate-200 hover:bg-slate-800"
                    >
                      + NPC 추가
                    </button>
                  </div>
                  {simpleForm.npcs.length === 0 ? (
                    <p className="text-sm text-slate-500">NPC가 없어도 저장할 수 있습니다. 대화 상대를 추가해 보세요.</p>
                  ) : (
                    <ul className="space-y-3">
                      {simpleForm.npcs.map((row, i) => (
                        <li
                          key={i}
                          className="grid gap-2 rounded-lg border border-slate-800 bg-slate-900/80 p-3 sm:grid-cols-2"
                        >
                          <input
                            type="text"
                            placeholder="id (비우면 이름에서 만듦)"
                            value={row.id}
                            onChange={(e) => updateNpc(i, { id: e.target.value })}
                            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 font-mono text-xs text-slate-200"
                          />
                          <input
                            type="text"
                            placeholder="이름"
                            value={row.name}
                            onChange={(e) => updateNpc(i, { name: e.target.value })}
                            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                          />
                          <input
                            type="text"
                            placeholder="역할"
                            value={row.role}
                            onChange={(e) => updateNpc(i, { role: e.target.value })}
                            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                          />
                          <input
                            type="text"
                            placeholder="장소"
                            value={row.location}
                            onChange={(e) => updateNpc(i, { location: e.target.value })}
                            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                          />
                          <div className="sm:col-span-2 flex justify-end">
                            <button
                              type="button"
                              onClick={() => removeNpc(i)}
                              className="text-xs text-red-400 hover:text-red-300"
                            >
                              삭제
                            </button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <p className="text-xs text-slate-500">
                  이벤트·세밀한 필드는 상단 <strong className="text-slate-400">JSON (고급)</strong> 탭에서만
                  다룹니다.
                </p>
              </div>
            )}

            {editorMode === "json" && (
              <>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={applyJsonTemplate}
                    className="rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
                  >
                    빈 JSON 템플릿
                  </button>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-300">world (JSON)</label>
                  <p className="mt-0.5 text-xs text-slate-500">
                    필수 키: id, name — 선택: description, world_setting, time,{" "}
                    <code className="text-slate-400">cover_image_url</code>(공개 상세 히어로, HTTPS), regions,
                    facts …
                  </p>
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
                  <p className="mt-0.5 text-xs text-slate-500">필수 키: npcs 배열</p>
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
              </>
            )}
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
