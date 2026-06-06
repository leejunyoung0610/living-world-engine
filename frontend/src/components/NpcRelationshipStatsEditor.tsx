import {
  RELATIONSHIP_STAT_CATALOG,
  type NpcRelationshipStats,
  type RelationshipStatSlug,
  clampRelationshipValue,
} from "../constants/relationshipStats";

type Props = {
  value: NpcRelationshipStats;
  onChange: (next: NpcRelationshipStats) => void;
};

export function NpcRelationshipStatsEditor({ value, onChange }: Props) {
  const active = RELATIONSHIP_STAT_CATALOG.filter((e) => value[e.slug] !== undefined);
  const inactive = RELATIONSHIP_STAT_CATALOG.filter((e) => value[e.slug] === undefined);

  function addStat(slug: RelationshipStatSlug) {
    const entry = RELATIONSHIP_STAT_CATALOG.find((e) => e.slug === slug);
    if (!entry) return;
    onChange({ ...value, [slug]: entry.defaultOnAdd });
  }

  function removeStat(slug: RelationshipStatSlug) {
    const next = { ...value };
    delete next[slug];
    onChange(next);
  }

  function setValue(slug: RelationshipStatSlug, raw: string) {
    const n = Number(raw);
    if (!Number.isFinite(n)) return;
    onChange({ ...value, [slug]: clampRelationshipValue(n) });
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-slate-400">관계 수치</span>
        <span className="text-[11px] text-slate-500">플레이 중 추적 · 대화창에는 숫자 미표시</span>
      </div>
      {active.length === 0 ? (
        <p className="text-xs text-slate-500">아래에서 스탯을 추가하면 플레이 화면 「관계」에서 볼 수 있습니다.</p>
      ) : (
        <ul className="space-y-2">
          {active.map((e) => (
            <li key={e.slug} className="flex flex-wrap items-center gap-2">
              <span className="w-14 text-xs text-slate-300">{e.label}</span>
              <input
                type="number"
                min={0}
                max={100}
                value={value[e.slug] ?? e.defaultOnAdd}
                onChange={(ev) => setValue(e.slug, ev.target.value)}
                className="w-16 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
              />
              <button
                type="button"
                onClick={() => removeStat(e.slug)}
                className="text-xs text-red-400 hover:text-red-300"
                title={`${e.label} 제거`}
              >
                제거
              </button>
            </li>
          ))}
        </ul>
      )}
      {inactive.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {inactive.map((e) => (
            <button
              key={e.slug}
              type="button"
              onClick={() => addStat(e.slug)}
              className="rounded-md border border-slate-700 bg-slate-950/80 px-2 py-0.5 text-xs text-slate-300 hover:border-indigo-700 hover:text-indigo-200"
            >
              + {e.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
