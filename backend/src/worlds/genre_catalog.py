"""공개 월드 장르 — 슬러그·한글 라벨. DB ``worlds.genres`` JSON 배열에 슬러그만 저장."""

from __future__ import annotations

# (slug, 한글 라벨) — 프론트/API 노출 순서
GENRE_DEFINITIONS: list[tuple[str, str]] = [
    ("academy", "학원"),
    ("romance", "로맨스"),
    ("fantasy", "판타지"),
    ("adventure", "모험"),
    ("sf", "SF"),
    ("drama", "드라마"),
    ("horror", "호러"),
    ("comedy", "코미디"),
    ("mystery", "미스터리"),
    ("slice_of_life", "일상"),
    ("historical", "사극·시대"),
    ("action", "액션"),
]

ALLOWED_GENRE_SLUGS: frozenset[str] = frozenset(s for s, _ in GENRE_DEFINITIONS)


def normalize_genres(genres: list[str], *, min_count: int = 1) -> list[str]:
    """공백 제거 · 중복 제거 · 허용 슬러그만 유지. ``min_count`` 미만이면 ValueError."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in genres:
        if not isinstance(raw, str):
            continue
        g = raw.strip().lower().replace(" ", "_")
        if not g or g not in ALLOWED_GENRE_SLUGS or g in seen:
            continue
        seen.add(g)
        out.append(g)
    if len(out) < min_count:
        raise ValueError("genres_min")
    return out


def genre_label(slug: str) -> str | None:
    for s, label in GENRE_DEFINITIONS:
        if s == slug:
            return label
    return None
