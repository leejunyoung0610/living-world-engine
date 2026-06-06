/** 플랫폼 고정 관계 스탯 — backend `relationship_stats.py` 와 동기화 */

export type RelationshipStatSlug =
  | "affection"
  | "trust"
  | "respect"
  | "fear"
  | "loyalty"
  | "romance"
  | "disgust"
  | "wrath";

export type RelationshipStatEntry = {
  slug: RelationshipStatSlug;
  label: string;
  defaultOnAdd: number;
};

export const RELATIONSHIP_STAT_CATALOG: RelationshipStatEntry[] = [
  { slug: "affection", label: "호감", defaultOnAdd: 50 },
  { slug: "trust", label: "신뢰", defaultOnAdd: 50 },
  { slug: "respect", label: "존경", defaultOnAdd: 50 },
  { slug: "fear", label: "두려움", defaultOnAdd: 50 },
  { slug: "loyalty", label: "충성", defaultOnAdd: 50 },
  { slug: "romance", label: "로맨스", defaultOnAdd: 0 },
  { slug: "disgust", label: "혐오", defaultOnAdd: 0 },
  { slug: "wrath", label: "살의", defaultOnAdd: 0 },
];

export const RELATIONSHIP_STAT_LABELS: Record<RelationshipStatSlug, string> = Object.fromEntries(
  RELATIONSHIP_STAT_CATALOG.map((e) => [e.slug, e.label]),
) as Record<RelationshipStatSlug, string>;

export type NpcRelationshipStats = Partial<Record<RelationshipStatSlug, number>>;

export function clampRelationshipValue(n: number): number {
  return Math.max(0, Math.min(100, Math.round(n)));
}

export function parseRelationshipStatsFromNpcJson(
  o: Record<string, unknown>,
): NpcRelationshipStats {
  const raw = o.relationship_stats ?? o.initial_stats;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  const out: NpcRelationshipStats = {};
  for (const e of RELATIONSHIP_STAT_CATALOG) {
    const v = (raw as Record<string, unknown>)[e.slug];
    if (typeof v === "number" && Number.isFinite(v)) {
      out[e.slug] = clampRelationshipValue(v);
    }
  }
  return out;
}
