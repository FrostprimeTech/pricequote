
DISTANCE_BANDS = ["0-199", "200-499", "500-799", "800+"]

RATE_CARD = {
    "8FT":  {"0-199": 72.6, "200-499": 68.4, "500-799": 54.0, "800+": 52.0},
    "9FT":  {"0-199": 75.6, "200-499": 67.4, "500-799": 56.0, "800+": 54.0},
    "10FT": {"0-199": 81.4, "200-499": 65.6, "500-799": 60.8, "800+": 56.0},
    "11FT": {"0-199": 84.0, "200-499": 60.0, "500-799": 60.4, "800+": 58.0},
    "12FT": {"0-199": 90.0, "200-499": 64.0, "500-799": 60.0, "800+": 59.0},
    "14FT": {"0-199": 100.0, "200-499": 70.0, "500-799": 64.0, "800+": 62.0},
}

# Floor-price guard: 10% below the rate card's own value for that same
# vehicle + distance band. If a final per-km rate ever drops below this
# (e.g. once a zone multiplier or other adjustment is layered on top),
# the quote is flagged rather than silently shown.
FLOOR_MARGIN_PCT = 0.10

FLOOR_RATE_CARD = {
    vehicle: {band: round(rate * (1 - FLOOR_MARGIN_PCT), 2) for band, rate in bands.items()}
    for vehicle, bands in RATE_CARD.items()
}


def get_floor_rate(vehicle: str, distance_km: float) -> float | None:
    """Return the floor Rs/km for this vehicle + distance band, or None if unsupported."""
    cat = normalize_rate_card_vehicle(vehicle)
    if cat is None:
        return None
    band = get_distance_band(distance_km)
    return FLOOR_RATE_CARD[cat][band]


def get_distance_band(distance_km: float) -> str:
    if distance_km < 200:
        return "0-199"
    if distance_km < 500:
        return "200-499"
    if distance_km < 800:
        return "500-799"
    return "800+"


def normalize_rate_card_vehicle(vehicle: str) -> str | None:
    """Map a raw vehicle string to a rate-card key, or None if unsupported."""
    if not vehicle:
        return None
    v = vehicle.strip().upper().replace(" ", "")
    v = v.lstrip("0") or "0"  # "08FT" -> "8FT", but guard against empty string
    if not v.endswith("FT"):
        return None
    return v if v in RATE_CARD else None


def lookup_rate(vehicle: str, distance_km: float) -> tuple[float, str] | tuple[None, None]:
    """Return (per_km_rate, distance_band) or (None, None) if vehicle is unsupported."""
    cat = normalize_rate_card_vehicle(vehicle)
    if cat is None:
        return None, None
    band = get_distance_band(distance_km)
    return RATE_CARD[cat][band], band
