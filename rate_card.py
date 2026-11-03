
DISTANCE_BANDS = ["0-199", "200-499", "500-799", "800+"]

# Base rate card is for FREEZER vehicles. CHILLER uses the same vehicle +
# distance band structure, at Rs.10/km less across every cell (flat
# subtraction, not a percentage), floored at 0 so it can never go negative.
FREEZER_RATE_CARD = {
    "8FT":  {"0-199": 100.0, "200-499": 60.0, "500-799": 56.0, "800+": 54.0},
    "9FT":  {"0-199": 100.0, "200-499": 60.0, "500-799": 56.0, "800+": 54.0},
    "10FT": {"0-199": 104.0, "200-499": 64.0, "500-799": 60.0, "800+": 58.0},
    "11FT": {"0-199": 104.0, "200-499": 64.0, "500-799": 60.0, "800+": 58.0},
    "12FT": {"0-199": 0.0, "200-499": 0.0, "500-799": 0.0, "800+": 0.0},
    "14FT": {"0-199": 110.0, "200-499": 70.0, "500-799": 64.0, "800+": 62.0},
}

CHILLER_RATE_DIFF = 10.0

CHILLER_RATE_CARD = {
    vehicle: {band: max(0.0, rate - CHILLER_RATE_DIFF) for band, rate in bands.items()}
    for vehicle, bands in FREEZER_RATE_CARD.items()
}

RATE_CARDS = {
    "FREEZER": FREEZER_RATE_CARD,
    "CHILLER": CHILLER_RATE_CARD,
}

VEHICLE_TYPES = list(RATE_CARDS.keys())

# Kept for backward compatibility with any code still importing RATE_CARD directly.
RATE_CARD = FREEZER_RATE_CARD


FLOOR_MARGIN_PCT = 0.10

FLOOR_RATE_CARDS = {
    vtype: {
        vehicle: {band: round(rate * (1 - FLOOR_MARGIN_PCT), 2) for band, rate in bands.items()}
        for vehicle, bands in card.items()
    }
    for vtype, card in RATE_CARDS.items()
}


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
    return v if v in FREEZER_RATE_CARD else None


def normalize_vehicle_type(vehicle_type: str) -> str | None:
    if not vehicle_type:
        return None
    v = vehicle_type.strip().upper()
    return v if v in RATE_CARDS else None


def get_floor_rate(vehicle: str, distance_km: float, vehicle_type: str = "FREEZER") -> float | None:
    """Return the floor Rs/km for this vehicle + distance band + type, or None if unsupported."""
    cat = normalize_rate_card_vehicle(vehicle)
    vtype = normalize_vehicle_type(vehicle_type)
    if cat is None or vtype is None:
        return None
    band = get_distance_band(distance_km)
    return FLOOR_RATE_CARDS[vtype][cat][band]


def lookup_rate(
    vehicle: str, distance_km: float, vehicle_type: str = "FREEZER"
) -> tuple[float, str] | tuple[None, None]:
    """Return (per_km_rate, distance_band) or (None, None) if vehicle/type is unsupported."""
    cat = normalize_rate_card_vehicle(vehicle)
    vtype = normalize_vehicle_type(vehicle_type)
    if cat is None or vtype is None:
        return None, None
    band = get_distance_band(distance_km)
    return RATE_CARDS[vtype][cat][band], band
