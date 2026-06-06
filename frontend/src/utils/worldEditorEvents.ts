/** 월드 에디터 간편 모드 ↔ 엔진 events.json */

import { RELATIONSHIP_STAT_CATALOG, type RelationshipStatSlug } from "../constants/relationshipStats";
import { slugifyWorldId } from "./worldEditorSimple";

export type EventConditionKind = "relationship" | "resource_stat" | "compound_and";

export type CompareOp = ">=" | ">" | "<=" | "<" | "==";

export type SimpleResourceStatRow = {
  key: string;
  label: string;
};

export type SimpleEventRow = {
  id: string;
  name: string;
  description: string;
  narrativeHint: string;
  conditionKind: EventConditionKind;
  npcId: string;
  relationshipStat: RelationshipStatSlug | "";
  relationshipOp: CompareOp;
  relationshipValue: number;
  resourceStat: string;
  resourceOp: CompareOp;
  resourceValue: number;
  compoundResourceStat: string;
  compoundResourceValue: number;
  effectKey1: string;
  effectDelta1: number;
  effectKey2: string;
  effectDelta2: number;
  once: boolean;
  cooldown: number;
  priority: number;
};

export const COMPARE_OPS: CompareOp[] = [">=", ">", "<=", "<", "=="];

export function defaultSimpleEventRow(): SimpleEventRow {
  return {
    id: "",
    name: "",
    description: "",
    narrativeHint: "",
    conditionKind: "relationship",
    npcId: "",
    relationshipStat: "affection",
    relationshipOp: ">=",
    relationshipValue: 40,
    resourceStat: "",
    resourceOp: ">=",
    resourceValue: 20,
    compoundResourceStat: "",
    compoundResourceValue: 15,
    effectKey1: "",
    effectDelta1: 10,
    effectKey2: "",
    effectDelta2: 0,
    once: true,
    cooldown: 999,
    priority: 5,
  };
}

export function milestoneRelationshipSample(npcId: string, npcName: string): SimpleEventRow {
  const base = defaultSimpleEventRow();
  return {
    ...base,
    id: "",
    name: `${npcName}과의 인연`,
    description: `${npcName}을 떠올리며 무언가 달라진다.`,
    narrativeHint: `플레이어가 ${npcName}과 관계가 깊어졌다. 주변 NPC가 은근히 느낄 수 있다.`,
    conditionKind: "relationship",
    npcId,
    relationshipStat: "affection",
    relationshipValue: 40,
    effectKey1: "skill",
    effectDelta1: 10,
    priority: 10,
  };
}

function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

function eventsArrayFromRaw(raw: unknown): unknown[] {
  if (Array.isArray(raw)) return raw;
  const o = asRecord(raw);
  if (o && Array.isArray(o.events)) return o.events;
  return [];
}

function parseOp(v: unknown): CompareOp {
  const s = String(v ?? ">=");
  return (COMPARE_OPS.includes(s as CompareOp) ? s : ">=") as CompareOp;
}

function parseEffects(effects: unknown): { key1: string; d1: number; key2: string; d2: number } {
  if (!Array.isArray(effects)) return { key1: "", d1: 0, key2: "", d2: 0 };
  const stats = effects.filter(
    (e) => asRecord(e)?.type === "resource_stat" || asRecord(e)?.type === "player_stat",
  );
  const first = asRecord(stats[0]);
  const second = asRecord(stats[1]);
  return {
    key1: typeof first?.key === "string" ? first.key : "",
    d1: typeof first?.change === "number" ? first.change : Number(first?.change) || 0,
    key2: typeof second?.key === "string" ? second.key : "",
    d2: typeof second?.change === "number" ? second.change : Number(second?.change) || 0,
  };
}

function tryParseCondition(
  cond: Record<string, unknown>,
): Pick<
  SimpleEventRow,
  | "conditionKind"
  | "npcId"
  | "relationshipStat"
  | "relationshipOp"
  | "relationshipValue"
  | "resourceStat"
  | "resourceOp"
  | "resourceValue"
  | "compoundResourceStat"
  | "compoundResourceValue"
> | null {
  const type = cond.type;
  if (type === "relationship_threshold") {
    const stat = String(cond.stat ?? "affection");
    const relSlug = RELATIONSHIP_STAT_CATALOG.some((e) => e.slug === stat)
      ? (stat as RelationshipStatSlug)
      : "affection";
    return {
      conditionKind: "relationship",
      npcId: typeof cond.npc_id === "string" ? cond.npc_id : "",
      relationshipStat: relSlug,
      relationshipOp: parseOp(cond.op),
      relationshipValue: Number(cond.value) || 0,
      resourceStat: "",
      resourceOp: ">=",
      resourceValue: 0,
      compoundResourceStat: "",
      compoundResourceValue: 0,
    };
  }
  if (type === "resource_stat_threshold") {
    return {
      conditionKind: "resource_stat",
      npcId: "",
      relationshipStat: "",
      relationshipOp: ">=",
      relationshipValue: 0,
      resourceStat: typeof cond.stat === "string" ? cond.stat : "",
      resourceOp: parseOp(cond.op),
      resourceValue: Number(cond.value) || 0,
      compoundResourceStat: "",
      compoundResourceValue: 0,
    };
  }
  if (type === "compound" && String(cond.op).toLowerCase() === "and" && Array.isArray(cond.conditions)) {
    const subs = cond.conditions.map((c) => asRecord(c)).filter(Boolean) as Record<string, unknown>[];
    const res = subs.filter((c) => c.type === "resource_stat_threshold");
    if (res.length >= 2) {
      return {
        conditionKind: "compound_and",
        npcId: "",
        relationshipStat: "",
        relationshipOp: ">=",
        relationshipValue: 0,
        resourceStat: typeof res[0].stat === "string" ? res[0].stat : "",
        resourceOp: parseOp(res[0].op),
        resourceValue: Number(res[0].value) || 0,
        compoundResourceStat: typeof res[1].stat === "string" ? res[1].stat : "",
        compoundResourceValue: Number(res[1].value) || 0,
      };
    }
    const rel = subs.find((c) => c.type === "relationship_threshold");
    const r1 = subs.find((c) => c.type === "resource_stat_threshold");
    if (rel && r1) {
      const stat = String(rel.stat ?? "affection");
      const relSlug = RELATIONSHIP_STAT_CATALOG.some((e) => e.slug === stat)
        ? (stat as RelationshipStatSlug)
        : "affection";
      return {
        conditionKind: "compound_and",
        npcId: typeof rel.npc_id === "string" ? rel.npc_id : "",
        relationshipStat: relSlug,
        relationshipOp: parseOp(rel.op),
        relationshipValue: Number(rel.value) || 0,
        resourceStat: typeof r1.stat === "string" ? r1.stat : "",
        resourceOp: parseOp(r1.op),
        resourceValue: Number(r1.value) || 0,
        compoundResourceStat: "",
        compoundResourceValue: 0,
      };
    }
  }
  return null;
}

export function tryParseSingleEvent(raw: unknown): SimpleEventRow | null {
  const o = asRecord(raw);
  if (!o || typeof o.id !== "string") return null;
  const cond = asRecord(o.condition);
  if (!cond) return null;
  const parsed = tryParseCondition(cond);
  if (!parsed) return null;
  const fx = parseEffects(o.effects);
  return {
    id: o.id,
    name: typeof o.name === "string" ? o.name : o.id,
    description: typeof o.description === "string" ? o.description : "",
    narrativeHint: typeof o.narrative_hint === "string" ? o.narrative_hint : "",
    ...parsed,
    effectKey1: fx.key1,
    effectDelta1: fx.d1,
    effectKey2: fx.key2,
    effectDelta2: fx.d2,
    once: o.once !== false,
    cooldown: typeof o.cooldown === "number" ? o.cooldown : 999,
    priority: typeof o.priority === "number" ? o.priority : 5,
  };
}

export function parseEventsFromJson(raw: unknown): {
  rows: SimpleEventRow[];
  unparsedCount: number;
} {
  const arr = eventsArrayFromRaw(raw);
  const rows: SimpleEventRow[] = [];
  let unparsed = 0;
  for (const item of arr) {
    const row = tryParseSingleEvent(item);
    if (row) rows.push(row);
    else unparsed += 1;
  }
  return { rows, unparsedCount: unparsed };
}

function buildCondition(row: SimpleEventRow): Record<string, unknown> {
  if (row.conditionKind === "relationship") {
    const c: Record<string, unknown> = {
      type: "relationship_threshold",
      stat: row.relationshipStat || "affection",
      op: row.relationshipOp,
      value: row.relationshipValue,
    };
    if (row.npcId.trim()) c.npc_id = row.npcId.trim();
    return c;
  }
  if (row.conditionKind === "resource_stat") {
    return {
      type: "resource_stat_threshold",
      stat: row.resourceStat.trim() || "skill",
      op: row.resourceOp,
      value: row.resourceValue,
    };
  }
  const subs: Record<string, unknown>[] = [];
  if (row.npcId.trim() && row.relationshipStat) {
    subs.push({
      type: "relationship_threshold",
      npc_id: row.npcId.trim(),
      stat: row.relationshipStat,
      op: row.relationshipOp,
      value: row.relationshipValue,
    });
  }
  if (row.resourceStat.trim()) {
    subs.push({
      type: "resource_stat_threshold",
      stat: row.resourceStat.trim(),
      op: row.resourceOp,
      value: row.resourceValue,
    });
  }
  if (row.compoundResourceStat.trim()) {
    subs.push({
      type: "resource_stat_threshold",
      stat: row.compoundResourceStat.trim(),
      op: ">=",
      value: row.compoundResourceValue,
    });
  }
  if (subs.length === 1) return subs[0];
  return { type: "compound", op: "and", conditions: subs };
}

function buildEffects(row: SimpleEventRow): Record<string, unknown>[] {
  const out: Record<string, unknown>[] = [];
  const k1 = row.effectKey1.trim();
  if (k1 && row.effectDelta1 !== 0) {
    out.push({ type: "resource_stat", key: k1, change: row.effectDelta1 });
  }
  const k2 = row.effectKey2.trim();
  if (k2 && row.effectDelta2 !== 0) {
    out.push({ type: "resource_stat", key: k2, change: row.effectDelta2 });
  }
  return out;
}

export function simpleEventRowToJson(row: SimpleEventRow, index: number): Record<string, unknown> {
  const name = row.name.trim() || `이벤트 ${index + 1}`;
  const id =
    row.id.trim() ||
    slugifyWorldId(name).replace(/^world_/, "evt_") ||
    `event_${index + 1}`;
  const ev: Record<string, unknown> = {
    id,
    name,
    description: row.description.trim(),
    narrative_hint: row.narrativeHint.trim(),
    condition: buildCondition(row),
    effects: buildEffects(row),
    once: row.once,
    cooldown: row.cooldown,
    priority: row.priority,
  };
  return ev;
}

export function serializeEventsToJson(rows: SimpleEventRow[]): Record<string, unknown>[] {
  return rows.map((r, i) => simpleEventRowToJson(r, i));
}

export function parseResourceStatsFromWorld(world: Record<string, unknown>): SimpleResourceStatRow[] {
  const schema = asRecord(world.stats_schema);
  const resource = schema ? asRecord(schema.resource) : null;
  if (!resource) return [];
  return Object.entries(resource)
    .map(([key, cfg]) => {
      const c = asRecord(cfg);
      const label = typeof c?.label === "string" ? c.label : key;
      return { key, label };
    })
    .filter((r) => r.key.trim());
}

export function defaultResourceStatRow(): SimpleResourceStatRow {
  return { key: "skill", label: "실력" };
}
