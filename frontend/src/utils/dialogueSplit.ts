import type { NpcSegment } from "../api/play";

const MAX_DISPLAY_SEGMENTS = 5;
const MAX_NARRATION_BLOCKS = 1;

const HR_LINE = /^---+\s*$|^\*{3}\s*$|^_{3,}\s*$/;
const DIALOGUE_START = /^["'…「]|^\.\.\./;
const ACTION_START = /^\([^)]*\)/;
const SPEAKER_HEADER = /^\*{0,2}([^*\n]{2,40}?)\*{0,2}\s*(?:\([^)]+\)|[:：])/;

const INVALID_SPEAKER_MARKERS = [
  "팟:",
  "플랍",
  "턴:",
  "턴 ",
  "리버",
  "보드",
  "차례",
  "카톡",
  "문자",
  "위치:",
  "핸드",
  "♠",
  "♥",
  "♦",
  "♣",
  " — ",
];

function isInvalidSpeakerLabel(name: string): boolean {
  const n = (name || "").trim();
  if (!n) return true;
  if (n === "내레이션" || n === "응답" || n === "모르는 번호") return false;
  if (INVALID_SPEAKER_MARKERS.some((m) => n.includes(m))) return true;
  if (/[♠♥♦♣]/.test(n)) return true;
  if (/^\d/.test(n)) return true;
  if (n.length > 36) return true;
  return false;
}

function isPlayerSpeaker(label: string, playerName: string | null | undefined): boolean {
  if (!playerName || !label) return false;
  const p = playerName.trim();
  const n = label.trim();
  return n === p || n.startsWith(p) || p.startsWith(n);
}

function filterSpeaker(
  label: string,
  names: string[],
  playerName?: string | null,
): string | null {
  const resolved = resolveSpeakerLabel(label, names);
  if (isPlayerSpeaker(resolved, playerName) || isPlayerSpeaker(label, playerName)) return null;
  if (isInvalidSpeakerLabel(resolved)) return null;
  return resolved;
}

export function normalizeAssistantText(text: string): string {
  let t = (text || "").trim();
  if (!t) return "";
  t = t.replace(/\n\s*---+\s*\n/g, "\n\n");
  t = t.replace(/(?:^\s*---+\s*\n|\n\s*---+\s*$)/g, "");
  t = t.replace(/\n{3,}/g, "\n\n");
  return t.trim();
}

function speakerHeaderName(line: string): string | null {
  const stripped = line.replace(/^\s+/, "");
  if (!stripped || isDialogueLine(stripped)) return null;
  const clean = stripped.replace(/\*\*/g, "").trim();
  const m = SPEAKER_HEADER.exec(clean) ?? SPEAKER_HEADER.exec(stripped);
  if (m) {
    const cand = m[1].trim();
    if (cand && !isDialogueLine(cand)) return cand;
  }
  const bold = stripped.match(/^\*\*([^*]+)\*\*/);
  if (bold) {
    const cand = bold[1].trim();
    if (cand) {
      const rest = stripped.slice(bold[0].length).trim();
      if (!rest || rest[0] === "(") return cand;
    }
  }
  return null;
}

function resolveSpeakerLabel(label: string, names: string[]): string {
  for (const name of names) {
    if (label === name || label.startsWith(name) || name.startsWith(label)) return name;
  }
  return label;
}

function discoverSpeakerNames(
  text: string,
  known: string[],
  playerName?: string | null,
): string[] {
  const found = new Set<string>();
  for (const n of known) {
    if (n && filterSpeaker(n, known, playerName)) {
      found.add(resolveSpeakerLabel(n, known));
    }
  }
  for (const line of text.split("\n")) {
    const cand = speakerHeaderName(line.trim());
    if (cand) {
      const acc = filterSpeaker(cand, [...found, ...known], playerName);
      if (acc) found.add(acc);
    }
  }
  return Array.from(found).sort((a, b) => b.length - a.length);
}

function preprocessSpeakerLineBreaks(text: string): string {
  const lines = text.split("\n");
  const out: string[] = [];
  for (const line of lines) {
    const stripped = line.trim();
    if (out.length && stripped && speakerHeaderName(stripped)) {
      if (out[out.length - 1].trim()) out.push("");
    }
    out.push(line);
  }
  return out.join("\n");
}

function speakerForFirstLine(
  firstLine: string,
  names: string[],
  playerName?: string | null,
): string | null {
  const stripped = firstLine.replace(/^\s+/, "");
  const header = speakerHeaderName(stripped);
  if (header) return filterSpeaker(header, names, playerName);
  const bold = stripped.match(/^\*\*([^*]+)\*\*/);
  if (bold) return filterSpeaker(bold[1].trim(), names, playerName);
  for (const name of names) {
    if (stripped.startsWith(name)) {
      const rest = stripped.slice(name.length);
      if (rest.length === 0 || rest[0] === " " || rest[0] === "\t" || rest[0] === "(") {
        return filterSpeaker(name, names, playerName);
      }
    }
  }
  return null;
}

function speakerForBlock(block: string, names: string[], playerName?: string | null): string | null {
  const first = block.split("\n", 1)[0];
  return speakerForFirstLine(first, names, playerName);
}

function firstLine(block: string): string {
  return block.trim().split("\n", 1)[0].trim();
}

function isDialogueLine(line: string): boolean {
  return DIALOGUE_START.test(line);
}

function isActionLine(line: string): boolean {
  return ACTION_START.test(line);
}

function blockHasDialogue(block: string): boolean {
  for (const line of block.split("\n")) {
    if (isDialogueLine(line.trim())) return true;
  }
  return false;
}

function stripNpcPrefix(line: string, names: string[]): string {
  const stripped = line.replace(/^\s+/, "");
  const bold = stripped.match(/^\*\*([^*]+)\*\*/);
  if (bold) return stripped.replace(/^\*\*[^*]+\*\*/, "").trim();
  for (const name of names) {
    if (stripped.startsWith(name)) return stripped.slice(name.length).trim();
  }
  return stripped;
}

function isNpcHeaderOnly(block: string, names: string[]): boolean {
  if (speakerForBlock(block, names) === null || blockHasDialogue(block)) return false;
  const lines = block.split("\n").map((l) => l.trim()).filter(Boolean);
  if (lines.length !== 1) return false;
  let rest = stripNpcPrefix(lines[0], names);
  rest = rest.replace(/^\([^)]*\)/, "").trim();
  return !rest;
}

function compactAssistantSegments(
  segments: NpcSegment[],
  maxTotal = MAX_DISPLAY_SEGMENTS,
  maxNarrationBlocks = MAX_NARRATION_BLOCKS,
): NpcSegment[] {
  if (!segments.length) return [];

  const merged: NpcSegment[] = [];
  for (const seg of segments) {
    const text = (seg.text || "").trim();
    if (!text) continue;
    const last = merged[merged.length - 1];
    if (last && last.speaker === "내레이션" && seg.speaker === "내레이션") {
      last.text = `${last.text}\n\n${text}`;
    } else {
      merged.push({ speaker: seg.speaker, text });
    }
  }

  const narrIndices = merged
    .map((s, i) => (s.speaker === "내레이션" ? i : -1))
    .filter((i) => i >= 0);
  let compacted = merged;
  if (narrIndices.length > maxNarrationBlocks) {
    const allNarr = narrIndices.map((i) => merged[i].text).join("\n\n");
    const out: NpcSegment[] = [];
    let inserted = false;
    for (let i = 0; i < merged.length; i++) {
      if (merged[i].speaker === "내레이션") {
        if (!inserted && i === narrIndices[0]) {
          out.push({ speaker: "내레이션", text: allNarr });
          inserted = true;
        }
        continue;
      }
      out.push(merged[i]);
    }
    compacted = out;
  }

  if (compacted.length <= maxTotal) return compacted;

  const narrOnly = compacted.filter((s) => s.speaker === "내레이션");
  const npcOnly = compacted.filter((s) => s.speaker !== "내레이션");
  const narrSlot = narrOnly.length ? 1 : 0;
  const keepNpcs = Math.max(1, maxTotal - narrSlot);

  if (npcOnly.length <= keepNpcs) {
    return [...npcOnly, ...narrOnly].slice(0, maxTotal);
  }

  const kept = npcOnly.slice(0, keepNpcs - 1);
  const overflow = npcOnly.slice(keepNpcs - 1);
  kept.push({
    speaker: overflow[0].speaker,
    text: overflow.map((s) => s.text).join("\n\n"),
  });
  if (narrOnly.length) {
    kept.push({ speaker: "내레이션", text: narrOnly[0].text });
  }
  return kept.slice(0, maxTotal);
}

function appendNarration(out: NpcSegment[], block: string): void {
  const last = out[out.length - 1];
  if (last && last.speaker === "내레이션") {
    last.text = `${last.text}\n\n${block}`;
  } else {
    out.push({ speaker: "내레이션", text: block });
  }
}

function splitByUtterances(
  blocks: string[],
  names: string[],
  playerName?: string | null,
): NpcSegment[] {
  const out: NpcSegment[] = [];
  let activeNpc: string | null = null;
  let pendingPrefix = "";

  const flushPrefixToLast = () => {
    if (!pendingPrefix) return;
    const last = out[out.length - 1];
    if (last && last.speaker !== "내레이션") {
      last.text = `${last.text}\n\n${pendingPrefix}`;
    } else if (activeNpc) {
      out.push({ speaker: activeNpc, text: pendingPrefix });
    } else {
      out.push({ speaker: "내레이션", text: pendingPrefix });
    }
    pendingPrefix = "";
  };

  for (const block of blocks) {
    if (!block || HR_LINE.test(block)) continue;

    const first = firstLine(block);
    const headerName = speakerHeaderName(first);
    if (headerName && filterSpeaker(headerName, names, playerName) === null) {
      flushPrefixToLast();
      activeNpc = null;
      appendNarration(out, block);
      continue;
    }

    const named = speakerForBlock(block, names, playerName);

    if (named) {
      activeNpc = named;
      if (isNpcHeaderOnly(block, names)) {
        pendingPrefix = pendingPrefix ? `${pendingPrefix}\n\n${block}` : block;
        continue;
      }
      const text = pendingPrefix ? `${pendingPrefix}\n\n${block}` : block;
      out.push({ speaker: named, text });
      pendingPrefix = "";
      continue;
    }

    if (isActionLine(first) && !blockHasDialogue(block)) {
      pendingPrefix = pendingPrefix ? `${pendingPrefix}\n\n${block}` : block;
      continue;
    }

    if (isDialogueLine(first) || blockHasDialogue(block)) {
      const speaker = activeNpc || "내레이션";
      const text = pendingPrefix ? `${pendingPrefix}\n\n${block}` : block;
      out.push({ speaker, text });
      pendingPrefix = "";
      continue;
    }

    flushPrefixToLast();
    activeNpc = null;
    appendNarration(out, block);
  }

  flushPrefixToLast();
  return out;
}

/**
 * 백엔드 dialogue_split.py 와 동일 — 멘트(따옴표 대사) 단위 카드, 최대 5개.
 */
export function splitAssistantIntoSegments(
  text: string,
  npcNames: string[],
  playerName?: string | null,
): NpcSegment[] {
  const trimmed = normalizeAssistantText(text);
  if (!trimmed) return [];

  const known = npcNames.map((n) => (n || "").trim()).filter(Boolean);
  const names = discoverSpeakerNames(trimmed, known, playerName);

  if (names.length === 0) {
    return [{ speaker: "응답", text: trimmed }];
  }

  const preprocessed = preprocessSpeakerLineBreaks(trimmed);
  const rawBlocks = preprocessed.split(/\n\s*\n+/);
  const blocks = rawBlocks
    .map((b) => b.replace(/^\s+|\s+$/g, ""))
    .filter((b) => b.length > 0 && !HR_LINE.test(b));

  return compactAssistantSegments(splitByUtterances(blocks, names, playerName));
}
