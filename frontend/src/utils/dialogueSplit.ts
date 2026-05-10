import type { NpcSegment } from "../api/play";

/**
 * 백엔드 backend/src/engine/dialogue_split.py 와 동일 알고리즘.
 * 빈 줄로 화자 블록을 구분하고, 첫 줄이 NPC 이름으로 시작하면 그 NPC, 아니면 "내레이션".
 *
 * 스트리밍 중에는 누적된 텍스트를 매 델타마다 이 함수로 다시 분할해서 화자별 박스로 보여준다.
 * 불완전한 마지막 블록도 그대로 한 segment 로 노출 (사용자가 글자 흐름을 본다).
 */
export function splitAssistantIntoSegments(
  text: string,
  npcNames: string[],
): NpcSegment[] {
  const trimmed = (text || "").replace(/^\s+/, "");
  if (!trimmed) return [];

  const names = Array.from(new Set(npcNames.map((n) => (n || "").trim()).filter(Boolean))).sort(
    (a, b) => b.length - a.length,
  );

  if (names.length === 0) {
    return [{ speaker: "응답", text: trimmed }];
  }

  const rawBlocks = trimmed.split(/\n\s*\n+/);
  const blocks = rawBlocks.map((b) => b.replace(/^\s+|\s+$/g, "")).filter((b) => b.length > 0);

  const speakerForFirstLine = (firstLine: string): string | null => {
    const stripped = firstLine.replace(/^\s+/, "");
    for (const name of names) {
      if (stripped.startsWith(name)) {
        const rest = stripped.slice(name.length);
        if (rest.length === 0 || rest[0] === " " || rest[0] === "\t" || rest[0] === "(") {
          return name;
        }
      }
    }
    return null;
  };

  const segments: NpcSegment[] = [];
  for (const block of blocks) {
    const first = block.split("\n", 1)[0];
    const sp = speakerForFirstLine(first);
    if (sp) segments.push({ speaker: sp, text: block });
    else segments.push({ speaker: "내레이션", text: block });
  }
  return segments;
}
