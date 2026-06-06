"""이벤트 API 직렬화."""

from types import SimpleNamespace

from backend.src.api.event_response import format_events_for_client
from backend.src.constants.stat_labels import resolve_stat_label_ko


def test_resolve_stat_label_ko_prefers_world_schema():
    world = {
        "stats_schema": {
            "resource": {
                "producing": {"label": "프로듀싱 스킬", "min": 0, "max": 100},
            }
        }
    }
    assert resolve_stat_label_ko("producing", world) == "프로듀싱 스킬"
    assert resolve_stat_label_ko("rap", world) == "랩"


def test_format_events_for_client_maps_delta_and_label():
    engine = SimpleNamespace(
        state=SimpleNamespace(world={"stats_schema": {"resource": {}}}),
    )
    out = format_events_for_client(engine, [{
        "event_id": "e1",
        "name": "영감",
        "description": "멜로디가 떠올랐다",
        "narrative_hint": "hint",
        "applied_effects": [
            {"type": "resource_stat", "key": "producing", "change": 10, "before": 5, "after": 15},
        ],
    }])
    assert len(out) == 1
    eff = out[0]["applied_effects"][0]
    assert eff["delta"] == 10
    assert eff["label_ko"] == "프로듀싱"
    assert out[0]["name"] == "영감"
