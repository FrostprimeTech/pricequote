"""
Shared quoting logic used by both the form UI and the free-text chat UI.

Pricing is a direct lookup against rate_card.RATE_CARD (vehicle x distance
band -> one-way Rs/km), not an ML model.
"""

import difflib

from freight_pipeline import MACRO_ZONE_MAP
from rate_card import get_floor_rate, lookup_rate

# Chat Quote only — applied on top of the rate-card base rate, keyed by
# the ORIGIN's macro zone. Not used by Form Quote.
ZONE_MULTIPLIERS = {
    "SOUTH_ZONE": 1.430,
    "EAST_ZONE": 1.324,
    "NORTH_ZONE": 1.180,
    "WEST_CENTRAL_ZONE": 1.000,
}

DISTANCE_DIVERGENCE_WARN_THRESHOLD = 0.20


def fuzzy_match(value: str, choices: list[str], cutoff: float = 0.5) -> str | None:
    """Best case-insensitive fuzzy match of `value` against `choices`, or None."""
    if not value:
        return None
    value_u = value.strip().upper()
    choice_map = {c.strip().upper(): c for c in choices}
    if value_u in choice_map:
        return choice_map[value_u]
    matches = difflib.get_close_matches(value_u, list(choice_map.keys()), n=1, cutoff=cutoff)
    return choice_map[matches[0]] if matches else None


def match_origin(text: str) -> str | None:
    return fuzzy_match(text, list(MACRO_ZONE_MAP.keys()), cutoff=0.6)


def match_vehicle(text: str, known_vehicles: list[str]) -> str | None:
    return fuzzy_match(text, known_vehicles, cutoff=0.4)


def resolve_distance(origin: str, destination: str, dist_lookup: dict, llm_distance_km: float = 0.0) -> tuple[float, str]:
    """Prefer historical median distance for the exact lane; fall back to
    whatever distance the LLM pulled out of the free text; else 0.
    Used by Form Quote only."""
    key = (origin, destination)
    if key in dist_lookup and dist_lookup[key] > 0:
        return float(dist_lookup[key]), "historical lane average"
    if llm_distance_km and llm_distance_km > 0:
        return float(llm_distance_km), "stated in query"
    return 0.0, "unknown"


def resolve_chat_distance(origin: str, destination: str, dist_lookup: dict, llm_distance_km: float) -> dict:
    """Chat Quote distance resolution: LLM estimate is primary. If a
    historical median exists for this exact lane and diverges from the
    LLM estimate by more than DISTANCE_DIVERGENCE_WARN_THRESHOLD, flag it
    so the dispatcher can sanity-check before confirming."""
    key = (origin, destination)
    historical = dist_lookup.get(key)
    result = {
        "distance": float(llm_distance_km),
        "historical_distance": float(historical) if historical else None,
        "diverges": False,
    }
    if historical:
        diff_ratio = abs(llm_distance_km - historical) / historical
        result["diverges"] = diff_ratio > DISTANCE_DIVERGENCE_WARN_THRESHOLD
    return result


def get_quote(origin: str, destination: str, vehicle: str, distance: float) -> dict:
    if distance <= 0:
        raise ValueError("Distance must be greater than 0.")
    if origin not in MACRO_ZONE_MAP:
        raise ValueError(f"Unknown origin hub '{origin}'.")

    per_km_rate, band = lookup_rate(vehicle, distance)
    if per_km_rate is None:
        raise ValueError(
            f"No rate card entry for vehicle '{vehicle}'. "
            "Only 8FT, 9FT, 10FT, 11FT, 12FT, 14FT are supported."
        )

    rate = round(per_km_rate * distance, -1)
    floor_rate = get_floor_rate(vehicle, distance)
    below_floor = per_km_rate < floor_rate

    return {
        "rate": rate,
        "per_km_rate": per_km_rate,
        "distance": distance,
        "distance_display": distance * 2,
        "distance_band": band,
        "vehicle": vehicle,
        "floor_rate": floor_rate,
        "below_floor": below_floor,
    }


def get_chat_quote(origin: str, destination: str, vehicle: str, distance: float) -> dict:
    """Chat Quote pricing: same rate-card lookup as get_quote, plus the
    origin's macro-zone multiplier applied on top of the base rate."""
    base = get_quote(origin, destination, vehicle, distance)

    zone = MACRO_ZONE_MAP[origin]
    multiplier = ZONE_MULTIPLIERS[zone]
    final_rate = round(base["rate"] * multiplier, -1)

    base.update(
        {
            "zone": zone,
            "zone_multiplier": multiplier,
            "base_rate": base["rate"],
            "rate": final_rate,
        }
    )
    return base
