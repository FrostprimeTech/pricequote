"""
Real-time freight quote CLI.

Usage:
    .venv/bin/python quote.py --from Pune --to "Solapur / Latur" --vehicle "9 FT" --distance 385
"""

import argparse
import sys

import joblib
import pandas as pd

from freight_pipeline import (
    MACRO_ZONE_MAP,
    LOCAL_SHUTTLE_MAX_KM,
    classify_corridor,
    normalize_vehicle,
)

LOCAL_MODEL_PATH = "model_local_shuttle.joblib"
OUTSTATION_MODEL_PATH = "model_outstation_linehaul.joblib"


def quote(origin: str, destination: str, vehicle: str, distance_km: float) -> dict:
    if distance_km <= 0:
        return {"rate": 0.0, "per_km_rate": 0.0, "regime": "NONE"}

    origin_key = origin.strip().upper()
    macro_zone = MACRO_ZONE_MAP.get(origin_key)
    if macro_zone is None:
        raise ValueError(
            f"Unknown origin hub '{origin}'. Add it to MACRO_ZONE_MAP in freight_pipeline.py."
        )

    vehicle_norm = normalize_vehicle(vehicle)

    if distance_km <= LOCAL_SHUTTLE_MAX_KM:
        model = joblib.load(LOCAL_MODEL_PATH)
        X = pd.DataFrame(
            [{"Macro_Zone": macro_zone, "Vehicle Size": vehicle_norm, "Distance (km)": distance_km}]
        )
        regime = "LOCAL_SHUTTLE"
    else:
        corridor = classify_corridor(destination, distance_km)
        model = joblib.load(OUTSTATION_MODEL_PATH)
        X = pd.DataFrame(
            [
                {
                    "Macro_Zone": macro_zone,
                    "Corridor_Zone_4": corridor,
                    "Vehicle Size": vehicle_norm,
                    "Distance (km)": distance_km,
                }
            ]
        )
        regime = f"OUTSTATION_LINEHAUL ({corridor})"

    per_km_rate = float(model.predict(X)[0])
    rate = per_km_rate * distance_km
    return {"rate": round(rate, -1), "per_km_rate": round(per_km_rate, 2), "regime": regime}


def main():
    parser = argparse.ArgumentParser(description="Real-time freight rate quote")
    parser.add_argument("--from", dest="origin", required=True)
    parser.add_argument("--to", dest="destination", required=True)
    parser.add_argument("--vehicle", required=True)
    parser.add_argument("--distance", type=float, required=True)
    args = parser.parse_args()

    try:
        result = quote(args.origin, args.destination, args.vehicle, args.distance)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Regime:       {result['regime']}")
    print(f"Per-KM Rate:  Rs.{result['per_km_rate']}")
    print(f"Quoted Rate:  Rs.{result['rate']:,.0f}")


if __name__ == "__main__":
    main()
