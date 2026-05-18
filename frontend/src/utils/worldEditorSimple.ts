/** 월드 에디터 간편 모드 ↔ 엔진 JSON (world / characters.npcs만) — 플레이어는 입장 시 설정 */

export type SimpleNpcRow = {
  id: string;
  name: string;
  role: string;
  location: string;
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
  npcs: SimpleNpcRow[];
};

export function defaultSimpleForm(): SimpleWorldFormState {
  return {
    worldSlug: "seoul_national_university",
    worldStoryName: "서울대학교",
    description: "관악 캠퍼스. 수업과 동아리가 얽인 하루하루.",
    worldSetting: "",
    coverImageUrl: "",
    time: "개강 첫 주",
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

export function formToWorldPayload(s: SimpleWorldFormState): {
  world: Record<string, unknown>;
  characters: Record<string, unknown>;
} {
  const npcs = s.npcs.map((row, i) => {
    const id =
      row.id.trim() ||
      slugifyWorldId(row.name.replace(/\s+/g, "_")) ||
      `npc_${i + 1}`;
    return {
      id,
      name: row.name.trim() || `이웃 ${i + 1}`,
      role: row.role.trim() || "등장인물",
      location: row.location.trim() || "Unknown",
    };
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
      return { id: `npc_${i + 1}`, name: "", role: "", location: "" };
    }
    const o = n as Record<string, unknown>;
    return {
      id: typeof o.id === "string" ? o.id : `npc_${i + 1}`,
      name: typeof o.name === "string" ? o.name : "",
      role: typeof o.role === "string" ? o.role : "",
      location: typeof o.location === "string" ? o.location : "",
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
    npcs: [
      {
        id: "kim_sunbae",
        name: "김선배",
        role: "동아리 선배",
        location: "학생회관",
      },
      {
        id: "lee_peer",
        name: "이동기",
        role: "같은 과 동기",
        location: "중앙도서관",
      },
    ],
  };
}
