import {
  COMPARE_OPS,
  defaultSimpleEventRow,
  milestoneCompoundRelationshipSample,
  milestoneRelationshipSample,
  type CompareOp,
  type EventConditionKind,
  type SimpleEventRow,
  type SimpleResourceStatRow,
} from "../utils/worldEditorEvents";
import {
  RELATIONSHIP_STAT_CATALOG,
  type RelationshipStatSlug,
} from "../constants/relationshipStats";

type NpcOption = { id: string; name: string };

type Props = {
  events: SimpleEventRow[];
  onChange: (next: SimpleEventRow[]) => void;
  npcs: NpcOption[];
  resourceStats: SimpleResourceStatRow[];
};

function updateRow(rows: SimpleEventRow[], i: number, patch: Partial<SimpleEventRow>): SimpleEventRow[] {
  return rows.map((r, j) => (j === i ? { ...r, ...patch } : r));
}

export function WorldEventsEditor({ events, onChange, npcs, resourceStats }: Props) {
  const statOptions = resourceStats.length > 0 ? resourceStats : [{ key: "skill", label: "실력" }];

  function addEvent() {
    onChange([...events, defaultSimpleEventRow()]);
  }

  function addSample(kind: "relationship" | "compound_relationship" = "relationship") {
    const npc = npcs[0];
    if (!npc) {
      onChange([...events, defaultSimpleEventRow()]);
      return;
    }
    const row =
      kind === "compound_relationship"
        ? milestoneCompoundRelationshipSample(npc.id, npc.name)
        : milestoneRelationshipSample(npc.id, npc.name);
    onChange([...events, row]);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-slate-300">마일스톤 이벤트</p>
          <p className="mt-0.5 text-xs text-slate-500">
            관계·스탯 조건 충족 시 플레이 중 카드로 발동. 1회성(once) 권장.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => addSample("relationship")}
            className="rounded-md border border-amber-800/60 bg-amber-950/30 px-2 py-1 text-xs text-amber-100 hover:bg-amber-950/50"
          >
            + 관계 샘플
          </button>
          <button
            type="button"
            onClick={() => addSample("compound_relationship")}
            className="rounded-md border border-amber-800/60 bg-amber-950/30 px-2 py-1 text-xs text-amber-100 hover:bg-amber-950/50"
          >
            + 복합 관계 샘플
          </button>
          <button
            type="button"
            onClick={addEvent}
            className="rounded-md border border-slate-600 px-2 py-1 text-xs text-slate-200 hover:bg-slate-800"
          >
            + 이벤트
          </button>
        </div>
      </div>

      {events.length === 0 ? (
        <p className="text-sm text-slate-500">비우면 플레이 중 이벤트가 없습니다.</p>
      ) : (
        <ul className="space-y-4">
          {events.map((row, i) => (
            <li key={i} className="rounded-lg border border-slate-800 bg-slate-900/80 p-4 space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <span className="text-xs font-medium text-amber-200/90">이벤트 {i + 1}</span>
                <button
                  type="button"
                  onClick={() => onChange(events.filter((_, j) => j !== i))}
                  className="text-xs text-red-400 hover:text-red-300"
                >
                  삭제
                </button>
              </div>

              <div className="grid gap-2 sm:grid-cols-2">
                <input
                  type="text"
                  placeholder="id (비우면 자동)"
                  value={row.id}
                  onChange={(e) => onChange(updateRow(events, i, { id: e.target.value }))}
                  className="rounded border border-slate-700 bg-slate-950 px-2 py-1 font-mono text-xs text-slate-200"
                />
                <input
                  type="text"
                  placeholder="카드 제목 *"
                  value={row.name}
                  onChange={(e) => onChange(updateRow(events, i, { name: e.target.value }))}
                  className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                />
              </div>

              <textarea
                placeholder="카드 설명 (유저에게 보임) *"
                value={row.description}
                onChange={(e) => onChange(updateRow(events, i, { description: e.target.value }))}
                rows={2}
                className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
              />
              <textarea
                placeholder="narrative_hint — 다음 턴 NPC가 은근히 인지 (유저 비표시)"
                value={row.narrativeHint}
                onChange={(e) => onChange(updateRow(events, i, { narrativeHint: e.target.value }))}
                rows={2}
                className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-300"
              />

              <fieldset className="rounded border border-slate-700/80 px-3 py-2">
                <legend className="px-1 text-xs text-slate-400">발동 조건</legend>
                <select
                  value={row.conditionKind}
                  onChange={(e) =>
                    onChange(updateRow(events, i, { conditionKind: e.target.value as EventConditionKind }))
                  }
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                >
                  <option value="relationship">NPC 관계 수치</option>
                  <option value="compound_relationship">NPC 관계 2개 (AND)</option>
                  <option value="resource_stat">플레이어 스탯</option>
                  <option value="compound_and">복합 (관계+스탯 AND)</option>
                </select>

                {(row.conditionKind === "relationship" ||
                  row.conditionKind === "compound_relationship" ||
                  row.conditionKind === "compound_and") && (
                  <div className="mt-2 space-y-2">
                    <select
                      value={row.npcId}
                      onChange={(e) => onChange(updateRow(events, i, { npcId: e.target.value }))}
                      className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                    >
                      <option value="">NPC 선택 *</option>
                      {npcs.map((n) => (
                        <option key={n.id} value={n.id}>
                          {n.name} ({n.id})
                        </option>
                      ))}
                    </select>
                    <div className="grid gap-2 sm:grid-cols-3">
                      <select
                        value={row.relationshipStat}
                        onChange={(e) =>
                          onChange(updateRow(events, i, { relationshipStat: e.target.value as RelationshipStatSlug }))
                        }
                        className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                      >
                        {RELATIONSHIP_STAT_CATALOG.map((e) => (
                          <option key={e.slug} value={e.slug}>
                            {e.label} ({e.slug})
                          </option>
                        ))}
                      </select>
                      <select
                        value={row.relationshipOp}
                        onChange={(e) =>
                          onChange(updateRow(events, i, { relationshipOp: e.target.value as CompareOp }))
                        }
                        className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                      >
                        {COMPARE_OPS.map((op) => (
                          <option key={op} value={op}>
                            {op}
                          </option>
                        ))}
                      </select>
                      <input
                        type="number"
                        min={0}
                        max={100}
                        value={row.relationshipValue}
                        onChange={(e) =>
                          onChange(updateRow(events, i, { relationshipValue: Number(e.target.value) || 0 }))
                        }
                        className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                        placeholder="임계값 1"
                      />
                    </div>
                    {row.conditionKind === "compound_relationship" && (
                      <div className="grid gap-2 sm:grid-cols-3">
                        <select
                          value={row.relationshipStat2}
                          onChange={(e) =>
                            onChange(updateRow(events, i, { relationshipStat2: e.target.value as RelationshipStatSlug }))
                          }
                          className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                        >
                          {RELATIONSHIP_STAT_CATALOG.map((e) => (
                            <option key={e.slug} value={e.slug}>
                              {e.label} ({e.slug})
                            </option>
                          ))}
                        </select>
                        <select
                          value={row.relationshipOp2}
                          onChange={(e) =>
                            onChange(updateRow(events, i, { relationshipOp2: e.target.value as CompareOp }))
                          }
                          className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                        >
                          {COMPARE_OPS.map((op) => (
                            <option key={op} value={op}>
                              {op}
                            </option>
                          ))}
                        </select>
                        <input
                          type="number"
                          min={0}
                          max={100}
                          value={row.relationshipValue2}
                          onChange={(e) =>
                            onChange(updateRow(events, i, { relationshipValue2: Number(e.target.value) || 0 }))
                          }
                          className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                          placeholder="임계값 2"
                        />
                      </div>
                    )}
                  </div>
                )}

                {(row.conditionKind === "resource_stat" || row.conditionKind === "compound_and") && (
                  <div className="mt-2 grid gap-2 sm:grid-cols-3">
                    <select
                      value={row.resourceStat}
                      onChange={(e) => onChange(updateRow(events, i, { resourceStat: e.target.value }))}
                      className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                    >
                      <option value="">스탯 키</option>
                      {statOptions.map((s) => (
                        <option key={s.key} value={s.key}>
                          {s.label} ({s.key})
                        </option>
                      ))}
                    </select>
                    <select
                      value={row.resourceOp}
                      onChange={(e) =>
                        onChange(updateRow(events, i, { resourceOp: e.target.value as CompareOp }))
                      }
                      className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                    >
                      {COMPARE_OPS.map((op) => (
                        <option key={op} value={op}>
                          {op}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      value={row.resourceValue}
                      onChange={(e) =>
                        onChange(updateRow(events, i, { resourceValue: Number(e.target.value) || 0 }))
                      }
                      className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                    />
                  </div>
                )}

                {row.conditionKind === "compound_and" && (
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    <select
                      value={row.compoundResourceStat}
                      onChange={(e) => onChange(updateRow(events, i, { compoundResourceStat: e.target.value }))}
                      className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                    >
                      <option value="">추가 스탯 (선택)</option>
                      {statOptions.map((s) => (
                        <option key={s.key} value={s.key}>
                          {s.label} ({s.key})
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      value={row.compoundResourceValue}
                      onChange={(e) =>
                        onChange(updateRow(events, i, { compoundResourceValue: Number(e.target.value) || 0 }))
                      }
                      className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                      placeholder="추가 임계값"
                    />
                  </div>
                )}
              </fieldset>

              <fieldset className="rounded border border-slate-700/80 px-3 py-2">
                <legend className="px-1 text-xs text-slate-400">효과 (스탯 변화)</legend>
                <div className="mt-1 grid gap-2 sm:grid-cols-2">
                  <select
                    value={row.effectKey1}
                    onChange={(e) => onChange(updateRow(events, i, { effectKey1: e.target.value }))}
                    className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                  >
                    <option value="">스탯 1</option>
                    {statOptions.map((s) => (
                      <option key={s.key} value={s.key}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    value={row.effectDelta1}
                    onChange={(e) =>
                      onChange(updateRow(events, i, { effectDelta1: Number(e.target.value) || 0 }))
                    }
                    className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                    placeholder="변화량 (+10)"
                  />
                  <select
                    value={row.effectKey2}
                    onChange={(e) => onChange(updateRow(events, i, { effectKey2: e.target.value }))}
                    className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                  >
                    <option value="">스탯 2 (선택)</option>
                    {statOptions.map((s) => (
                      <option key={s.key} value={s.key}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    value={row.effectDelta2}
                    onChange={(e) =>
                      onChange(updateRow(events, i, { effectDelta2: Number(e.target.value) || 0 }))
                    }
                    className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-white"
                  />
                </div>
              </fieldset>

              <div className="flex flex-wrap gap-3 text-xs text-slate-400">
                <label className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={row.once}
                    onChange={(e) => onChange(updateRow(events, i, { once: e.target.checked }))}
                  />
                  1회만 (once)
                </label>
                <label className="flex items-center gap-1">
                  우선순위
                  <input
                    type="number"
                    value={row.priority}
                    onChange={(e) =>
                      onChange(updateRow(events, i, { priority: Number(e.target.value) || 0 }))
                    }
                    className="w-14 rounded border border-slate-700 bg-slate-950 px-1 py-0.5 text-white"
                  />
                </label>
                <label className="flex items-center gap-1">
                  쿨다운
                  <input
                    type="number"
                    value={row.cooldown}
                    onChange={(e) =>
                      onChange(updateRow(events, i, { cooldown: Number(e.target.value) || 999 }))
                    }
                    className="w-16 rounded border border-slate-700 bg-slate-950 px-1 py-0.5 text-white"
                  />
                </label>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
