

import re
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

CSV_PATH = "Courier Trip Schedule css.csv"
LOCAL_SHUTTLE_MAX_KM = 50

# ---------------------------------------------------------------------------
# 1. Macro-Zone mapping (origin hubs -> 4 zones)
# ---------------------------------------------------------------------------
MACRO_ZONE_MAP = {
    "PATNA": "EAST_ZONE",
    "PATNA (SALIMAR)": "EAST_ZONE",
    "KOLKATA": "EAST_ZONE",
    "DANKUNI": "EAST_ZONE",
    "ULUBERIA": "EAST_ZONE",
    "DHULAGARH": "EAST_ZONE",
    "SILIGURI": "EAST_ZONE",
    "GUWAHATI": "EAST_ZONE",
    "CHHEGAON GUW": "EAST_ZONE",
    "RAIPUR": "EAST_ZONE",

    "BENGALURU": "SOUTH_ZONE",
    "ANEKAL": "SOUTH_ZONE",
    "ANJANEYA": "SOUTH_ZONE",
    "TAVAREKERE": "SOUTH_ZONE",
    "COIMBATORE": "SOUTH_ZONE",
    "HYDERABAD": "SOUTH_ZONE",
    "VIJAYWADA": "SOUTH_ZONE",

    "NOIDA": "NORTH_ZONE",
    "DASNA": "NORTH_ZONE",
    "FARRUKHNAGAR": "NORTH_ZONE",
    "DEHRADUN": "NORTH_ZONE",
    "LUCKNOW": "NORTH_ZONE",
    "VARANASI": "NORTH_ZONE",
    "LUDHIANA": "NORTH_ZONE",
    "RAJPURA": "NORTH_ZONE",

    "JAIPUR": "WEST_CENTRAL_ZONE",
    "AHMEDABAD": "WEST_CENTRAL_ZONE",
    "SURAT": "WEST_CENTRAL_ZONE",
    "MUMBAI": "WEST_CENTRAL_ZONE",
    "TALOJA": "WEST_CENTRAL_ZONE",
    "PUNE": "WEST_CENTRAL_ZONE",
    "BHOPAL": "WEST_CENTRAL_ZONE",
    "NAGPUR": "WEST_CENTRAL_ZONE",
}


Z1_HILLY_OR_INTERIOR_DEADEND = {
    "GANGTOK", "SRINAGAR", "HALDWANI", "KASHIPUR", "KICHHA", "DEHRADUN",
    "SHIMLA", "MANALI", "NAINITAL", "ALMORA", "RISHIKESH",
}
Z2_INDUSTRIAL_COAL_BELT = {
    "DURGAPUR", "DHANBAD", "JAMSHEDPUR", "SALEM", "ASANSOL", "BOKARO",
    "HAZARIBAGH", "DEOGHAR", "DUMKA", "RANCHI", "KHARAGPUR", "KHAMMAM",
    "HOSUR",
}
Z3_RIVERINE_FEEDER = {
    "DARBHANGA", "BHAGALPUR", "PURNIA", "KATIHAR", "MADHUBANI", "BEGUSARAI",
    "KHAGARIA", "SAHARSA", "MUNGER", "KISANGANJ", "KHAGRA", "JALPAIGURI",
}


def tokenize_destination(dest: str) -> list[str]:
    """A Final_Destination cell may list several towns ('A / B / C').
    Split on '/' and normalize each token for keyword matching."""
    parts = re.split(r"[/,]", dest.upper())
    return [p.strip() for p in parts if p.strip()]


def classify_corridor(dest: str, distance_km: float) -> str:
    if pd.isna(distance_km):
        return np.nan
    if distance_km <= LOCAL_SHUTTLE_MAX_KM:
        return "Z0_LOCAL_SHUTTLE"
    if pd.isna(dest):
        return "Z4_EXPRESSWAY_TRUNK"

    tokens = tokenize_destination(dest)
    if any(t in Z1_HILLY_OR_INTERIOR_DEADEND for t in tokens):
        return "Z1_HILLY_OR_INTERIOR_DEADEND"
    if any(t in Z2_INDUSTRIAL_COAL_BELT for t in tokens):
        return "Z2_INDUSTRIAL_COAL_BELT"
    if any(t in Z3_RIVERINE_FEEDER for t in tokens):
        return "Z3_RIVERINE_FEEDER"
    return "Z4_EXPRESSWAY_TRUNK"


def normalize_vehicle(v):
    if pd.isna(v):
        return np.nan
    v = str(v).upper().replace(" ", "")
    v = v.replace("TATA407", "TATA_407")
    return v


def load_and_engineer(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    df["Distance (km)"] = (
        df["Distance (km)"].astype(str).str.replace(",", "", regex=False)
    )
    df["Distance (km)"] = pd.to_numeric(df["Distance (km)"], errors="coerce")
    df["Rate"] = pd.to_numeric(df["Rate"], errors="coerce")

    df["From"] = df["From"].astype(str).str.strip().str.upper()
    df["Vehicle Size"] = df["Vehicle Size"].apply(normalize_vehicle)

    # Drop rows missing the essentials for training.
    df = df.dropna(subset=["Distance (km)", "Rate", "From"])
    df = df[df["Distance (km)"] > 0]  # zero-distance rows carry no rate signal

    df["Macro_Zone"] = df["From"].map(MACRO_ZONE_MAP)
    unmapped = df[df["Macro_Zone"].isna()]["From"].unique()
    if len(unmapped):
        print(f"WARNING: unmapped origin hubs (dropped): {sorted(unmapped)}")
    df = df.dropna(subset=["Macro_Zone"])

    df["Corridor_Zone_4"] = df.apply(
        lambda r: classify_corridor(r["Final_Destination"], r["Distance (km)"]),
        axis=1,
    )

    df["Per_KM_Rate"] = df["Rate"] / df["Distance (km)"]

    return df


def build_model_pipeline(categorical_cols: list[str]) -> Pipeline:
    pre = ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore"),
                categorical_cols,
            ),
        ],
        remainder="passthrough",
    )
    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=None,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
    return Pipeline([("pre", pre), ("rf", model)])


def train_regime(df: pd.DataFrame, feature_cols: list[str], categorical_cols: list[str], label: str):
    X = df[feature_cols]
    y = df["Per_KM_Rate"]
    weights = df["Distance (km)"] ** 2

    X_train, X_test, y_train, y_test, w_train, w_test = train_test_split(
        X, y, weights, test_size=0.2, random_state=42
    )

    pipe = build_model_pipeline(categorical_cols)
    pipe.fit(X_train, y_train, rf__sample_weight=w_train)

    pred_per_km = pipe.predict(X_test)
    pred_rate = pred_per_km * X_test["Distance (km)"]
    actual_rate = y_test * X_test["Distance (km)"]

    mae_rate = mean_absolute_error(actual_rate, pred_rate)
    print(f"[{label}] rows={len(df)} test_MAE_on_total_Rate=Rs.{mae_rate:,.0f}")

    return pipe


def main():
    df = load_and_engineer(CSV_PATH)
    print(f"Engineered dataset: {len(df)} usable rows")
    print(df["Corridor_Zone_4"].value_counts())
    print(df["Macro_Zone"].value_counts())

    local_df = df[df["Distance (km)"] <= LOCAL_SHUTTLE_MAX_KM].copy()
    outstation_df = df[df["Distance (km)"] > LOCAL_SHUTTLE_MAX_KM].copy()

    local_features = ["Macro_Zone", "Vehicle Size", "Distance (km)"]
    local_categorical = ["Macro_Zone", "Vehicle Size"]
    local_df = local_df.dropna(subset=local_features)

    outstation_features = ["Macro_Zone", "Corridor_Zone_4", "Vehicle Size", "Distance (km)"]
    outstation_categorical = ["Macro_Zone", "Corridor_Zone_4", "Vehicle Size"]
    outstation_df = outstation_df.dropna(subset=outstation_features)

    local_model = train_regime(local_df, local_features, local_categorical, "LOCAL_SHUTTLE")
    outstation_model = train_regime(
        outstation_df, outstation_features, outstation_categorical, "OUTSTATION_LINEHAUL"
    )

    joblib.dump(local_model, "model_local_shuttle.joblib")
    joblib.dump(outstation_model, "model_outstation_linehaul.joblib")
    print("Saved model_local_shuttle.joblib and model_outstation_linehaul.joblib")


if __name__ == "__main__":
    main()
