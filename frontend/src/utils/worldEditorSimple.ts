/** 월드 에디터 간편 모드 ↔ 엔진 JSON (world / characters.npcs만) — 플레이어는 입장 시 설정 */

import {
  type NpcRelationshipStats,
  parseRelationshipStatsFromNpcJson,
} from "../constants/relationshipStats";
import {
  defaultResourceStatRow,
  parseResourceStatsFromWorld,
  type SimpleResourceStatRow,
} from "./worldEditorEvents";

export type SimpleNpcRow = {
  id: string;
  name: string;
  role: string;
  /** 전공·직업 — LLM 대화(자기소개)용 */
  major: string;
  /** 성격 — LLM 대화용 */
  personality: string;
  /** 배경·추가 설정 — LLM 대화용 */
  background: string;
  /** 말투 — LLM 대화용 (저장 시 speaking_style) */
  speakingStyle: string;
  /** 플레이·프롬프트용 장소. JSON에만 두거나 과거 데이터 유지 시 자동 로드됨. */
  location?: string;
  /** 초상 AI(Replicate) 프롬프트용 외모·무드·복장 등 — 저장 시 appearance_for_ai */
  appearanceForAi: string;
  /** 초상 미리보기용 — 저장 시 npc.portrait_image_url 로 직렬화 */
  portraitImageUrl?: string;
  /** 활성 관계 스탯만 키로 — 저장 시 relationship_stats */
  relationshipStats: NpcRelationshipStats;
};

export type SimpleWorldFormState = {
  worldSlug: string;
  worldStoryName: string;
  description: string;
  /** 스토리·LLM용 상세 세계관 (목록용 한 줄 설명과 별도) */
  worldSetting: string;
  /** 공개 상세 상단 히어로 — HTTPS 이미지 URL (AI 생성 URL·CDN 등). 비우면 표시 안 함. */
  coverImageUrl: string;
  time: string;
  /** 이벤트 효과·조건용 — `world.stats_schema.resource` */
  resourceStats: SimpleResourceStatRow[];
  npcs: SimpleNpcRow[];
};

export function defaultSimpleNpcRow(): SimpleNpcRow {
  return {
    id: "",
    name: "",
    role: "",
    major: "",
    personality: "",
    background: "",
    speakingStyle: "",
    appearanceForAi: "",
    relationshipStats: {},
  };
}

export function defaultSimpleForm(): SimpleWorldFormState {
  return {
    worldSlug: "seoul_national_university",
    worldStoryName: "서울대학교",
    description: "관악 캠퍼스. 수업과 동아리가 얽인 하루하루.",
    worldSetting: "",
    coverImageUrl: "",
    time: "개강 첫 주",
    resourceStats: [defaultResourceStatRow()],
    npcs: [],
  };
}

/** 영문·숫자 기반 id (한글만 있으면 타임스탬프 fallback) */
export function slugifyWorldId(input: string): string {
  const x = input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "_")
    .replace(/^[_-]+|[_-]+$/g, "");
  return x || `world_${Math.floor(Date.now() / 1000)}`;
}

function optionalNpcString(raw: Record<string, unknown>, key: string): string {
  const v = raw[key];
  return typeof v === "string" ? v.trim() : "";
}

function speakingStyleFromJson(o: Record<string, unknown>): string {
  const style = o.speaking_style ?? o.speech_style;
  if (typeof style === "string") return style.trim();
  if (style && typeof style === "object" && !Array.isArray(style)) {
    const d = style as Record<string, unknown>;
    const parts = [d.formality, d.default_mood].filter((x) => typeof x === "string" && x.trim());
    return parts.join(", ");
  }
  return "";
}

export function formToWorldPayload(s: SimpleWorldFormState): {
  world: Record<string, unknown>;
  characters: Record<string, unknown>;
} {
  const npcs = s.npcs.map((row, i) => {
    const id =
      row.id.trim() ||
      slugifyWorldId(row.name.replace(/\s+/g, "_")) ||
      `npc_${i + 1}`;
    const npc: Record<string, unknown> = {
      id,
      name: row.name.trim() || `이웃 ${i + 1}`,
      role: row.role.trim() || "등장인물",
    };
    const major = row.major.trim();
    if (major) npc.major = major;
    const personality = row.personality.trim();
    if (personality) npc.personality = personality;
    const background = row.background.trim();
    if (background) npc.background = background;
    const speaking = row.speakingStyle.trim();
    if (speaking) npc.speaking_style = speaking;
    const a = row.appearanceForAi.trim();
    if (a) {
      npc.appearance_for_ai = a;
    }
    const loc = typeof row.location === "string" ? row.location.trim() : "";
    if (loc) {
      npc.location = loc;
    }
    const p = typeof row.portraitImageUrl === "string" ? row.portraitImageUrl.trim() : "";
    if (p) {
      npc.portrait_image_url = p;
    }
    const rs = row.relationshipStats;
    if (rs && Object.keys(rs).length > 0) {
      npc.relationship_stats = { ...rs };
    }
    return npc;
  });

  const wid = s.worldSlug.trim() || slugifyWorldId(s.worldStoryName);

  const world: Record<string, unknown> = {
    id: wid,
    name: s.worldStoryName.trim() || "새 세계",
    description: s.description.trim(),
    world_setting: s.worldSetting.trim(),
    time: s.time.trim() || "Day 1",
    regions: [],
    facts: [],
    world_variables: {},
  };
  const cover = s.coverImageUrl.trim();
  if (cover) {
    world.cover_image_url = cover;
  }

  const resource: Record<string, unknown> = {};
  for (const row of s.resourceStats) {
    const key = row.key.trim();
    if (!key) continue;
    resource[key] = {
      label: row.label.trim() || key,
      min: 0,
      max: 100,
      default: 5,
    };
  }
  if (Object.keys(resource).length > 0) {
    world.stats_schema = { resource };
  }

  return {
    world,
    characters: {
      npcs,
    },
  };
}

/** JSON이 간편 폼으로 옮길 수 있는지 검사 후 파싱 (player 없음) */
export function tryImportSimpleFromJson(
  world: Record<string, unknown>,
  chars: Record<string, unknown>,
): SimpleWorldFormState | null {
  if (typeof world.id !== "string" || typeof world.name !== "string") return null;
  const rawNpcs = chars.npcs;
  if (!Array.isArray(rawNpcs)) return null;

  const npcs: SimpleNpcRow[] = rawNpcs.map((n, i) => {
    if (!n || typeof n !== "object" || Array.isArray(n)) {
      return { ...defaultSimpleNpcRow(), id: `npc_${i + 1}` };
    }
    const o = n as Record<string, unknown>;
    return {
      id: typeof o.id === "string" ? o.id : `npc_${i + 1}`,
      name: typeof o.name === "string" ? o.name : "",
      role: typeof o.role === "string" ? o.role : "",
      major: optionalNpcString(o, "major"),
      personality: optionalNpcString(o, "personality"),
      background: optionalNpcString(o, "background") || optionalNpcString(o, "description"),
      speakingStyle: speakingStyleFromJson(o),
      ...(typeof o.location === "string" && o.location.trim()
        ? { location: o.location.trim() }
        : {}),
      appearanceForAi: optionalNpcString(o, "appearance_for_ai"),
      portraitImageUrl:
        typeof o.portrait_image_url === "string" ? o.portrait_image_url : undefined,
      relationshipStats: parseRelationshipStatsFromNpcJson(o),
    };
  });

  let worldSetting = "";
  const ws = world.world_setting;
  if (typeof ws === "string" && ws.trim()) worldSetting = ws.trim();
  else if (typeof world.setting === "string" && world.setting.trim())
    worldSetting = world.setting.trim();

  return {
    worldSlug: world.id,
    worldStoryName: world.name,
    description: typeof world.description === "string" ? world.description : "",
    worldSetting,
    coverImageUrl:
      typeof world.cover_image_url === "string"
        ? world.cover_image_url
        : typeof world.hero_image_url === "string"
          ? world.hero_image_url
          : "",
    time: typeof world.time === "string" ? world.time : "Day 1",
    resourceStats: (() => {
      const parsed = parseResourceStatsFromWorld(world);
      return parsed.length > 0 ? parsed : [defaultResourceStatRow()];
    })(),
    npcs,
  };
}

/** NPC 2명이 있는 캠퍼스 샘플 */
export function campusSampleForm(): SimpleWorldFormState {
  return {
    worldSlug: "snu_campus_sample",
    worldStoryName: "서울대학교 · 시험 기간 전야",
    description: "과제와 시험이 겹치는 12주차. 도서관과 학생회관이 무대가 됩니다.",
    worldSetting:
      "무대는 관악 캠퍼스. 셔틀·지하철로 등하교가 오가고, 중앙도서관·학생회관·단과대·실험동이 하루의 축이다.\n\n" +
      "현실 기반 슬라이스 오브 라이프로 유지한다. 판타지·실존 비판·정치 선동은 넣지 않는다. 강의·팀플·조교·동아리 행사·취업 상담 같은 일상 단위로 전개한다.",
    coverImageUrl: "",
    time: "12주차 · 레포트 마감 전날",
    resourceStats: [
      { key: "focus", label: "집중력" },
      { key: "stress", label: "스트레스" },
    ],
    npcs: [
      {
        id: "kim_sunbae",
        name: "김선배",
        role: "동아리 선배",
        major: "경영학과",
        personality: "리더십 있고 후배를 잘 챙김. 완벽주의지만 따뜻함.",
        background: "동아리 회장 2년차. 대기업 인턴 경험.",
        speakingStyle: "존댓말, 명확하고 차분",
        appearanceForAi: "마른 편 체격, 검은 미디엄 헤어, 후드티, 펜슬 허깅 카고. 친근한 웃음·말 많은 타입.",
        relationshipStats: { affection: 55, trust: 60 },
      },
      {
        id: "lee_peer",
        name: "이동기",
        role: "같은 과 동기",
        major: "컴퓨터공학과",
        personality: "성실하고 조용함. 친해지면 유머러스.",
        background: "알고리즘 동아리 부회장. 해커톤 수상.",
        speakingStyle: "반말, 차분하고 진지",
        appearanceForAi: "안경 착용 반삭, 카키 자켓, 노트와 태블릿을 자주 들고 다님. 진지하지만 속은 여림.",
        relationshipStats: { affection: 45, trust: 50 },
      },
    ],
  };
}
