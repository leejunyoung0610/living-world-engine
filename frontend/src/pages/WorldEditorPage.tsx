import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { TOKEN_KEY } from "../api/client";
import {
  createWorld,
  EMPTY_CHARACTERS,
  EMPTY_WORLD,
  fetchGenreMeta,
  fetchImageStorageMeta,
  generateNpcPortrait,
  generateWorldCover,
  getWorld,
  SESSION_EXPIRED,
  updateWorld,
  type GenreEntry,
  type ImageStorageMeta,
  type WorldVisibility,
} from "../api/worlds";
import { LoggedInNav } from "../components/LoggedInNav";
import { NpcRelationshipStatsEditor } from "../components/NpcRelationshipStatsEditor";
import { PreviewHttpsImage } from "../components/PreviewHttpsImage";
import { WorldEventsEditor } from "../components/WorldEventsEditor";
import {
  campusSampleForm,
  defaultSimpleForm,
  defaultSimpleNpcRow,
  formToWorldPayload,
  slugifyWorldId,
  tryImportSimpleFromJson,
  type SimpleNpcRow,
  type SimpleWorldFormState,
} from "../utils/worldEditorSimple";
import {
  defaultResourceStatRow,
  parseEventsFromJson,
  serializeEventsToJson,
  type SimpleEventRow,
} from "../utils/worldEditorEvents";

function stringifyJson(v: unknown): string {
  return JSON.stringify(v, null, 2);
}

type EditorMode = "simple" | "json";

type CoverSourceMode = "url" | "ai";

function stripCoverKeysFromWorld(w: Record<string, unknown>): Record<string, unknown> {
  const out = { ...w };
  delete out.cover_image_url;
  return out;
}

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
  const [simpleEvents, setSimpleEvents] = useState<SimpleEventRow[]>([]);
  const [eventsUseAdvanced, setEventsUseAdvanced] = useState(false);
  const [eventsImportWarn, setEventsImportWarn] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!isCreate);
  const [saving, setSaving] = useState(false);
  const [visibility, setVisibility] = useState<WorldVisibility>("private");
  const [genreCatalog, setGenreCatalog] = useState<GenreEntry[]>([]);
  const [selectedGenres, setSelectedGenres] = useState<string[]>(["fantasy"]);
  const [simpleImportWarn, setSimpleImportWarn] = useState<string | null>(null);
  const [coverGenerating, setCoverGenerating] = useState(false);
  const [coverGenInfo, setCoverGenInfo] = useState<string | null>(null);
  /** 커버: URL 입력 vs AI 생성 — 둘 중 하나만 활성 */
  const [coverSource, setCoverSource] = useState<CoverSourceMode>(() => (isCreate ? "ai" : "url"));
  const [npcPortraitBusyIndex, setNpcPortraitBusyIndex] = useState<number | null>(null);
  const [imageStorageMeta, setImageStorageMeta] = useState<ImageStorageMeta | null>(null);

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
    void fetchImageStorageMeta()
      .then(setImageStorageMeta)
      .catch(() => setImageStorageMeta(null));

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
        const { rows: evRows, unparsedCount } = parseEventsFromJson(w.events);
        setSimpleEvents(evRows);
        setEventsText(w.events ? stringifyJson(w.events) : "");
        if (unparsedCount > 0) {
          setEventsUseAdvanced(true);
          setEventsImportWarn(
            `간편 폼으로 읽지 못한 이벤트 ${unparsedCount}개가 있습니다. 고급 JSON을 확인하세요.`,
          );
        } else {
          setEventsUseAdvanced(false);
          setEventsImportWarn(null);
        }
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
        const wd = w.world as Record<string, unknown>;
        const cu = wd.cover_image_url;
        const hasCover =
          typeof cu === "string" && cu.trim().startsWith("https://");
        setCoverSource(hasCover ? "url" : "ai");
      } catch (e) {
        if (e instanceof Error && e.message === SESSION_EXPIRED) {
          localStorage.removeItem(TOKEN_KEY);
          nav("/login");
          return;
        }
        setApiError(
          e instanceof Error
            ? e.message === "World not found"
              ? "월드를 찾을 수 없거나, 이 계정이 만든 월드가 아닙니다. 마이페이지「내가 만든 월드」에서 편집하세요."
              : e.message
            : "불러오기 실패",
        );
      } finally {
        setLoading(false);
      }
    })();
  }, [create, isCreate, nav, worldId]);

  useEffect(() => {
    if (editorMode !== "simple") return;
    if (!isCreate && loading) return;
    const { world, characters } = formToWorldPayload({
      ...simpleForm,
      worldStoryName: name.trim() || simpleForm.worldStoryName || "새 세계",
    });
    setWorldText(stringifyJson(world));
    setCharsText(stringifyJson(characters));
  }, [editorMode, simpleForm, name, isCreate, loading]);

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
    setSimpleEvents([]);
    setEventsUseAdvanced(false);
    setEventsImportWarn(null);
    setEventsText("");
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
    const et = eventsText.trim();
    if (et) {
      try {
        const { rows, unparsedCount } = parseEventsFromJson(JSON.parse(et));
        setSimpleEvents(rows);
        setEventsUseAdvanced(unparsedCount > 0);
        setEventsImportWarn(
          unparsedCount > 0
            ? `간편 폼으로 읽지 못한 이벤트 ${unparsedCount}개 — 고급 JSON 유지`
            : null,
        );
      } catch {
        setEventsImportWarn("events JSON 파싱 실패 — 고급 JSON만 유지됩니다.");
        setEventsUseAdvanced(true);
      }
    }
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
      npcs: [...s.npcs, defaultSimpleNpcRow()],
    }));
  }

  function removeNpc(i: number) {
    setSimpleForm((s) => ({
      ...s,
      npcs: s.npcs.filter((_, j) => j !== i),
    }));
  }

  function parseBodies():
    | { ok: true; world: Record<string, unknown>; characters: Record<string, unknown>; events: unknown }
    | { ok: false; message: string } {
    if (editorMode === "simple") {
      const { world, characters } = formToWorldPayload({
        ...simpleForm,
        worldStoryName: name.trim() || simpleForm.worldStoryName || "새 세계",
      });
      if (eventsUseAdvanced) {
        const et = eventsText.trim();
        if (!et) return { ok: true, world, characters, events: null };
        try {
          return { ok: true, world, characters, events: JSON.parse(et) as unknown };
        } catch {
          return { ok: false, message: "events JSON 파싱 실패" };
        }
      }
      const events =
        simpleEvents.length > 0 ? serializeEventsToJson(simpleEvents) : null;
      return { ok: true, world, characters, events };
    }

    let world: unknown;
    let characters: unknown;
    let events: unknown = null;
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

  function readCoverUrlFromWorldJson(): string {
    try {
      const w = JSON.parse(worldText) as Record<string, unknown>;
      const u = w.cover_image_url;
      return typeof u === "string" ? u.trim() : "";
    } catch {
      return "";
    }
  }

  function patchWorldCoverUrl(raw: string): void {
    try {
      const w = JSON.parse(worldText) as Record<string, unknown>;
      const v = raw.trim();
      if (v && v.startsWith("https://")) {
        w.cover_image_url = v;
      } else {
        delete w.cover_image_url;
      }
      setWorldText(stringifyJson(w));
    } catch {
      /* malformed json — 무시 */
    }
  }

  function selectCoverSource(next: CoverSourceMode): void {
    if (next === coverSource) return;
    setCoverSource(next);
  }

  function currentCoverPreviewUrl(): string {
    if (editorMode === "simple") return simpleForm.coverImageUrl.trim();
    try {
      const w = JSON.parse(worldText) as Record<string, unknown>;
      const u = w.cover_image_url;
      return typeof u === "string" ? u.trim() : "";
    } catch {
      return "";
    }
  }

  function effectiveNpcRowId(row: SimpleNpcRow, index: number): string {
    return row.id.trim() || slugifyWorldId(row.name.replace(/\s+/g, "_")) || `npc_${index + 1}`;
  }

  async function onGenerateCover() {
    if (!token) return;
    setCoverGenInfo(null);
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
    setCoverGenerating(true);
    try {
      if (isCreate) {
        const worldPayload = stripCoverKeysFromWorld(parsed.world);
        const created = await createWorld(token, {
          name: name.trim() || "이름 없음",
          world: worldPayload,
          characters: parsed.characters,
          events: parsed.events,
          visibility,
          genres: selectedGenres,
        });
        try {
          const genRes = await generateWorldCover(token, created.id);
          const parts: string[] = [];
          if (genRes.remaining_user_monthly !== null) {
            parts.push(`이번 달 계정 ${genRes.remaining_user_monthly}회 남음`);
          }
          if (genRes.remaining_world_monthly !== null) {
            parts.push(`이 월드 ${genRes.remaining_world_monthly}회 남음`);
          }
          if (genRes.storage_notice) parts.push(genRes.storage_notice);
          setCoverGenInfo(parts.join(" · ") || null);
        } catch (genErr) {
          if (genErr instanceof Error && genErr.message === SESSION_EXPIRED) {
            localStorage.removeItem(TOKEN_KEY);
            nav("/login");
            return;
          }
          setApiError(genErr instanceof Error ? genErr.message : "커버 생성 실패");
        }
        nav(`/worlds/${created.id}`, { replace: true });
        return;
      }
      if (!worldId) return;
      const res = await generateWorldCover(token, worldId);
      const url = res.cover_image_url.trim();
      if (editorMode === "simple") {
        setSimpleForm((s) => ({ ...s, coverImageUrl: url }));
      } else {
        try {
          const w = JSON.parse(worldText) as Record<string, unknown>;
          w.cover_image_url = url;
          setWorldText(stringifyJson(w));
        } catch {
          /* malformed json — 사용자가 수정할 때까지 스킵 */
        }
      }
      const parts: string[] = [];
      if (res.remaining_user_monthly !== null) {
        parts.push(`이번 달 계정 ${res.remaining_user_monthly}회 남음`);
      }
      if (res.remaining_world_monthly !== null) {
        parts.push(`이 월드 ${res.remaining_world_monthly}회 남음`);
      }
      if (res.storage_notice) parts.push(res.storage_notice);
      setCoverGenInfo(parts.join(" · ") || null);
    } catch (err) {
      if (err instanceof Error && err.message === SESSION_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setApiError(err instanceof Error ? err.message : "커버 생성 실패");
    } finally {
      setCoverGenerating(false);
    }
  }

  async function onGenerateNpcPortrait(index: number) {
    if (!token || !worldId || isCreate || editorMode !== "simple") return;
    const row = simpleForm.npcs[index];
    if (!row) return;
    const npcId = effectiveNpcRowId(row, index);
    setApiError(null);
    setNpcPortraitBusyIndex(index);
    try {
      const res = await generateNpcPortrait(token, worldId, npcId);
      const url = res.portrait_image_url.trim();
      setSimpleForm((s) => {
        const npcs = s.npcs.map((r, j) => (j === index ? { ...r, portraitImageUrl: url } : r));
        return { ...s, npcs };
      });
    } catch (err) {
      if (err instanceof Error && err.message === SESSION_EXPIRED) {
        localStorage.removeItem(TOKEN_KEY);
        nav("/login");
        return;
      }
      setApiError(err instanceof Error ? err.message : "초상 생성 실패");
    } finally {
      setNpcPortraitBusyIndex(null);
    }
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
        const created = await createWorld(token, {
          name: name.trim() || "이름 없음",
          world: parsed.world,
          characters: parsed.characters,
          events: parsed.events,
          visibility,
          genres: selectedGenres,
        });
        // 첫 저장 직후 편집 화면으로 — AI 커버·NPC 초상 API는 world UUID가 있어야 동작
        nav(`/worlds/${created.id}`, { replace: true });
        return;
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

            {imageStorageMeta && !imageStorageMeta.permanent_storage && imageStorageMeta.notice && (
              <p className="rounded-lg border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-sm text-amber-200">
                {imageStorageMeta.notice}{" "}
                <span className="text-amber-300/80">자세히: docs/IMAGE_STORAGE.md</span>
              </p>
            )}

            <fieldset className="rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3">
              <legend className="px-1 text-sm font-medium text-slate-300">커버 이미지 (공개 상세)</legend>
              <p className="mt-1 text-xs text-slate-500">
                <strong className="text-slate-400">두 방식 중 하나만</strong> 씁니다. 바꿀 때 기존 커버 값은 초기화됩니다.
              </p>
              <div className="mt-3 flex flex-wrap gap-4">
                <label className="flex cursor-pointer items-start gap-2 text-sm text-slate-300">
                  <input
                    type="radio"
                    name="coverSource"
                    className="mt-1"
                    checked={coverSource === "url"}
                    onChange={() => selectCoverSource("url")}
                  />
                  <span>
                    <span className="font-medium text-white">HTTPS URL 직접 입력</span>
                    <span className="mt-0.5 block text-xs text-slate-500">
                      CDN·이미지 호스트에서 받은 주소만 붙여 넣습니다.
                    </span>
                  </span>
                </label>
                <label className="flex cursor-pointer items-start gap-2 text-sm text-slate-300">
                  <input
                    type="radio"
                    name="coverSource"
                    className="mt-1"
                    checked={coverSource === "ai"}
                    onChange={() => selectCoverSource("ai")}
                  />
                  <span>
                    <span className="font-medium text-white">AI로 생성</span>
                    <span className="mt-0.5 block text-xs text-slate-500">
                      세계 이름·설명·세계관을 바탕으로 16:9 커버 URL을 만듭니다(Replicate 설정·크레딧 필요).
                    </span>
                  </span>
                </label>
              </div>

              {coverSource === "url" && editorMode === "simple" && (
                <div className="mt-4">
                  <label className="block text-sm font-medium text-slate-300">커버 이미지 URL</label>
                  <p className="mt-0.5 text-xs text-slate-500">
                    <strong className="text-slate-400">https://</strong> 만 허용됩니다.
                  </p>
                  <input
                    type="url"
                    inputMode="url"
                    value={simpleForm.coverImageUrl}
                    onChange={(e) => setSimpleForm((s) => ({ ...s, coverImageUrl: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-sm text-white"
                    placeholder="https://…"
                  />
                  {currentCoverPreviewUrl().startsWith("https://") && (
                    <div className="mt-3">
                      <p className="text-xs text-slate-500">미리보기</p>
                      <PreviewHttpsImage
                        src={currentCoverPreviewUrl()}
                        className="mt-1 max-h-40 w-full max-w-xl rounded-md border border-slate-700 object-cover"
                      />
                    </div>
                  )}
                </div>
              )}

              {coverSource === "url" && editorMode === "json" && (
                <div className="mt-4 space-y-2">
                  <label className="block text-sm font-medium text-slate-300">
                    커버 URL — JSON의 <code className="text-slate-400">cover_image_url</code>
                  </label>
                  <p className="text-xs text-slate-500">
                    아래에 입력하면 world JSON 에 반영됩니다. 또는 하단 편집기에서 직접 수정해도 됩니다.
                  </p>
                  <input
                    type="url"
                    inputMode="url"
                    value={readCoverUrlFromWorldJson()}
                    onChange={(e) => patchWorldCoverUrl(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-sm text-white"
                    placeholder="https://…"
                  />
                  {readCoverUrlFromWorldJson().startsWith("https://") && (
                    <div className="mt-2">
                      <p className="text-xs text-slate-500">미리보기</p>
                      <PreviewHttpsImage
                        src={readCoverUrlFromWorldJson()}
                        className="mt-1 max-h-40 w-full max-w-xl rounded-md border border-slate-700 object-cover"
                      />
                    </div>
                  )}
                </div>
              )}

              {coverSource === "ai" && (
                <div className="mt-4 space-y-2">
                  {isCreate && (
                    <p className="text-xs text-slate-500">
                      새 월드에서는 버튼을 누르면 <strong className="text-slate-400">먼저 저장(생성)</strong>한 뒤 곧바로 AI
                      커버를 생성하고, 편집 화면으로 이동합니다.
                    </p>
                  )}
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      disabled={coverGenerating}
                      onClick={() => void onGenerateCover()}
                      className="rounded-lg border border-violet-600 bg-violet-950/50 px-3 py-2 text-sm font-medium text-violet-100 hover:bg-violet-900/60 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {coverGenerating
                        ? "생성 중…"
                        : isCreate
                          ? "AI 커버 생성 (저장 후 실행)"
                          : "AI 커버 생성"}
                    </button>
                    {coverGenInfo && <span className="text-xs text-slate-400">{coverGenInfo}</span>}
                  </div>
                  {currentCoverPreviewUrl().startsWith("https://") && (
                    <div className="mt-2">
                      <p className="text-xs text-slate-500">미리보기</p>
                      <PreviewHttpsImage
                        src={currentCoverPreviewUrl()}
                        className="mt-1 max-h-40 w-full max-w-xl rounded-md border border-slate-700 object-cover"
                      />
                    </div>
                  )}
                </div>
              )}
            </fieldset>

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
                            placeholder="역할 *"
                            value={row.role}
                            onChange={(e) => updateNpc(i, { role: e.target.value })}
                            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                          />
                          <div>
                            <input
                              type="text"
                              placeholder="전공·직업"
                              value={row.major}
                              onChange={(e) => updateNpc(i, { major: e.target.value })}
                              className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                            />
                            <p className="mt-0.5 text-[11px] text-slate-500">
                              대화에 쓰임 — 자기소개·학과 언급에 반영
                            </p>
                          </div>
                          <div className="sm:col-span-2">
                            <label className="text-xs font-medium text-slate-400">성격</label>
                            <textarea
                              value={row.personality}
                              onChange={(e) => updateNpc(i, { personality: e.target.value })}
                              rows={2}
                              spellCheck={false}
                              placeholder='예: "차분하고 책임감 강함"'
                              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-white placeholder:text-slate-600"
                            />
                            <p className="mt-0.5 text-[11px] text-slate-500">NPC 대사 톤·성격에 반영</p>
                          </div>
                          <div className="sm:col-span-2">
                            <label className="text-xs font-medium text-slate-400">배경 (선택)</label>
                            <textarea
                              value={row.background}
                              onChange={(e) => updateNpc(i, { background: e.target.value })}
                              rows={2}
                              spellCheck={false}
                              placeholder="과거·동아리·추가 설정"
                              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-white placeholder:text-slate-600"
                            />
                          </div>
                          <div className="sm:col-span-2">
                            <label className="text-xs font-medium text-slate-400">말투 (선택)</label>
                            <input
                              type="text"
                              value={row.speakingStyle}
                              onChange={(e) => updateNpc(i, { speakingStyle: e.target.value })}
                              placeholder='예: "존댓말, 밝고 친근"'
                              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white placeholder:text-slate-600"
                            />
                          </div>
                          <div className="sm:col-span-2 border-t border-slate-800 pt-2">
                            <NpcRelationshipStatsEditor
                              value={row.relationshipStats}
                              onChange={(relationshipStats) => updateNpc(i, { relationshipStats })}
                            />
                          </div>
                          <div className="sm:col-span-2 border-t border-slate-800 pt-2">
                            <label className="text-xs font-medium text-slate-400">
                              외모·복장 (AI 초상 전용)
                            </label>
                            <textarea
                              value={row.appearanceForAi}
                              onChange={(e) => updateNpc(i, { appearanceForAi: e.target.value })}
                              rows={3}
                              spellCheck={false}
                              placeholder="예: 검은 숏컷·교복 블레이저. 대화 LLM에는 넣지 않음."
                              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-white placeholder:text-slate-600"
                            />
                            <p className="mt-1 text-[11px] text-slate-500">
                              초상 AI만 사용. 레거시 <code className="text-slate-500">location</code> 은 JSON 탭에서
                              수정 가능.
                            </p>
                          </div>
                          {row.portraitImageUrl ? (
                            <div className="sm:col-span-2 flex flex-wrap items-center gap-2">
                              <span className="text-xs text-slate-500">초상</span>
                              <PreviewHttpsImage
                                src={row.portraitImageUrl}
                                className="h-14 w-14 rounded-md border border-slate-700 object-cover"
                                expiredMessage="초상 만료 — AI 초상으로 다시 생성하세요."
                              />
                            </div>
                          ) : null}
                          <div className="sm:col-span-2 flex flex-wrap items-center justify-between gap-2">
                            {!isCreate && worldId && token ? (
                              <button
                                type="button"
                                disabled={npcPortraitBusyIndex !== null}
                                onClick={() => void onGenerateNpcPortrait(i)}
                                className="rounded-lg border border-cyan-800 bg-cyan-950/40 px-2 py-1 text-xs font-medium text-cyan-100 hover:bg-cyan-950/70 disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                {npcPortraitBusyIndex === i ? "초상 생성 중…" : "AI 초상"}
                              </button>
                            ) : (
                              <span />
                            )}
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

                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <label className="text-sm font-medium text-slate-300">플레이어 스탯 (자원)</label>
                    <button
                      type="button"
                      onClick={() =>
                        setSimpleForm((s) => ({
                          ...s,
                          resourceStats: [...s.resourceStats, defaultResourceStatRow()],
                        }))
                      }
                      className="rounded-md border border-slate-600 px-2 py-1 text-xs text-slate-200 hover:bg-slate-800"
                    >
                      + 스탯
                    </button>
                  </div>
                  <p className="mb-2 text-xs text-slate-500">
                    입장 시 플레이어가 설정하는 수치. 이벤트 조건·효과·카드 한글 라벨에 사용됩니다.
                  </p>
                  <ul className="space-y-2">
                    {simpleForm.resourceStats.map((row, i) => (
                      <li key={i} className="flex flex-wrap gap-2">
                        <input
                          type="text"
                          placeholder="키 (영문, 예: producing)"
                          value={row.key}
                          onChange={(e) =>
                            setSimpleForm((s) => ({
                              ...s,
                              resourceStats: s.resourceStats.map((r, j) =>
                                j === i ? { ...r, key: e.target.value } : r,
                              ),
                            }))
                          }
                          className="w-36 rounded border border-slate-700 bg-slate-950 px-2 py-1 font-mono text-xs text-slate-200"
                        />
                        <input
                          type="text"
                          placeholder="한글 라벨"
                          value={row.label}
                          onChange={(e) =>
                            setSimpleForm((s) => ({
                              ...s,
                              resourceStats: s.resourceStats.map((r, j) =>
                                j === i ? { ...r, label: e.target.value } : r,
                              ),
                            }))
                          }
                          className="min-w-[8rem] flex-1 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                        />
                        <button
                          type="button"
                          onClick={() =>
                            setSimpleForm((s) => ({
                              ...s,
                              resourceStats: s.resourceStats.filter((_, j) => j !== i),
                            }))
                          }
                          className="text-xs text-red-400 hover:text-red-300"
                        >
                          삭제
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>

                <WorldEventsEditor
                  events={simpleEvents}
                  onChange={setSimpleEvents}
                  npcs={simpleForm.npcs.map((row, i) => ({
                    id: effectiveNpcRowId(row, i),
                    name: row.name.trim() || `NPC ${i + 1}`,
                  }))}
                  resourceStats={simpleForm.resourceStats.filter((r) => r.key.trim())}
                />

                {eventsImportWarn && (
                  <p className="rounded-lg border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-xs text-amber-200">
                    {eventsImportWarn}
                  </p>
                )}

                <details className="rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2">
                  <summary className="cursor-pointer text-xs text-slate-400">
                    이벤트 고급 JSON {eventsUseAdvanced ? "(사용 중)" : "(선택)"}
                  </summary>
                  <label className="mt-2 flex items-center gap-2 text-xs text-slate-400">
                    <input
                      type="checkbox"
                      checked={eventsUseAdvanced}
                      onChange={(e) => setEventsUseAdvanced(e.target.checked)}
                    />
                    간편 폼 대신 아래 JSON을 저장에 사용
                  </label>
                  <textarea
                    value={eventsText}
                    onChange={(e) => setEventsText(e.target.value)}
                    rows={8}
                    spellCheck={false}
                    className="mt-2 w-full resize-y rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-200"
                    placeholder='[{"id":"evt_1", ...}] 또는 {"events":[...]}'
                  />
                </details>
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
                    facts … — NPC 초상은 <code className="text-slate-400">npcs[].portrait_image_url</code>
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
                  <p className="mt-0.5 text-xs text-slate-500">
                    필수 키: npcs 배열 — 대화: <code className="text-slate-400">major</code>,{" "}
                    <code className="text-slate-400">personality</code>,{" "}
                    <code className="text-slate-400">background</code>,{" "}
                    <code className="text-slate-400">speaking_style</code> — 초상:{" "}
                    <code className="text-slate-400">appearance_for_ai</code>, URL{" "}
                    <code className="text-slate-400">portrait_image_url</code>
                  </p>
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
                  <p className="mt-0.5 text-xs text-slate-500">
                    배열 또는 {"{ \"events\": [...] }"}. 조건: relationship_threshold(npc_id), resource_stat_threshold,
                    compound · 효과: resource_stat
                  </p>
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
