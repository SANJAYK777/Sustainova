from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
PRIMARY_DATASET_PATH = PROJECT_ROOT / "data" / "guest_dataset.csv"
FALLBACK_DATASET_PATH = BASE_DIR / "dataset" / "guest_dataset.csv"

REQUIRED_COLUMNS = {"Coming_From", "Distance_km", "RSVP_Status", "Total_Guests"}
CITY_COORDINATES = {
    "chennai": (13.0827, 80.2707),
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "coimbatore": (11.0168, 76.9558),
    "madurai": (9.9252, 78.1198),
    "hyderabad": (17.3850, 78.4867),
    "delhi": (28.6139, 77.2090),
    "trichy": (10.7905, 78.7047),
    "tiruchirappalli": (10.7905, 78.7047),
    "mumbai": (19.0760, 72.8777),
    "pune": (18.5204, 73.8567),
    "kolkata": (22.5726, 88.3639),
}
CITY_ALIASES = {
    "madras": "chennai",
    "blr": "bangalore",
    "new delhi": "delhi",
}


def _normalize_rsvp(value: str | None) -> str:
    return (value or "").strip().lower()


def _distance_probability(distance_km: float) -> float:
    if distance_km <= 30:
        return 0.95
    if distance_km <= 100:
        return 0.85
    return 0.70


def _distance_to_risk_level(distance_km: float) -> str:
    if distance_km <= 30:
        return "Low"
    if distance_km <= 100:
        return "Medium"
    return "High"


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def _city_coordinates(city: str | None) -> tuple[float, float] | None:
    key = " ".join((city or "").strip().lower().split())
    if not key:
        return None
    normalized = CITY_ALIASES.get(key, key)
    point = CITY_COORDINATES.get(normalized)
    if point:
        return point
    for token in normalized.replace(",", " ").split():
        token_norm = CITY_ALIASES.get(token, token)
        token_point = CITY_COORDINATES.get(token_norm)
        if token_point:
            return token_point
    return None


def load_travel_dataset(path: Path | None = None) -> pd.DataFrame:
    dataset_path = path or (PRIMARY_DATASET_PATH if PRIMARY_DATASET_PATH.exists() else FALLBACK_DATASET_PATH)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Travel risk dataset not found: {dataset_path}")

    dataset = pd.read_csv(dataset_path)
    missing_columns = sorted(REQUIRED_COLUMNS - set(dataset.columns))
    if missing_columns:
        raise ValueError(f"Travel risk dataset missing columns: {missing_columns}")
    return dataset


def calculate_travel_adjusted_attendance(dataset: pd.DataFrame) -> dict[str, int | str]:
    missing_columns = sorted(REQUIRED_COLUMNS - set(dataset.columns))
    if missing_columns:
        raise ValueError(f"Travel risk input missing columns: {missing_columns}")

    working = dataset.copy()
    working["Distance_km"] = pd.to_numeric(working["Distance_km"], errors="coerce").fillna(0.0)
    working["Total_Guests"] = pd.to_numeric(working["Total_Guests"], errors="coerce").fillna(0.0)
    working["RSVP_Status"] = working["RSVP_Status"].astype(str)

    # Exclude explicit declines from the adjusted attendance pool.
    active = working[working["RSVP_Status"].map(_normalize_rsvp) != "not attending"].copy()
    if active.empty:
        return {
            "Predicted_Attendance": 0,
            "Local_Guests_Count": 0,
            "Outstation_Guests_Count": 0,
            "Travel_Risk_Level": "Low",
        }

    active["Probability"] = active["Distance_km"].map(_distance_probability)
    adjusted_attendance = float((active["Total_Guests"] * active["Probability"]).sum())

    local_count = int(active.loc[active["Distance_km"] <= 30, "Total_Guests"].sum())
    outstation_count = int(active.loc[active["Distance_km"] > 30, "Total_Guests"].sum())
    total_guest_pool = float(active["Total_Guests"].sum())
    weighted_avg_distance = (
        float((active["Distance_km"] * active["Total_Guests"]).sum()) / total_guest_pool
        if total_guest_pool > 0
        else 0.0
    )

    return {
        "Predicted_Attendance": int(round(adjusted_attendance)),
        "Local_Guests_Count": local_count,
        "Outstation_Guests_Count": outstation_count,
        "Travel_Risk_Level": _distance_to_risk_level(weighted_avg_distance),
    }


def build_event_travel_dataset(
    guests: Iterable,
    event_lat: float | None,
    event_lng: float | None,
    reference_dataset: pd.DataFrame | None = None,
) -> pd.DataFrame:
    # Retained for backward compatibility; travel-risk distance now uses only coordinates.
    _ = reference_dataset

    if event_lat is None or event_lng is None:
        raise ValueError("Event coordinates are required for travel-risk distance calculation")

    base_lat = float(event_lat)
    base_lng = float(event_lng)

    rows: list[dict[str, object]] = []
    for guest in guests:
        coming_from_raw = (getattr(guest, "coming_from", None) or "").strip()
        city_point = _city_coordinates(coming_from_raw)
        if not city_point:
            # No known coordinates for this city, so skip instead of using static fallback distance.
            continue

        distance_km = _haversine_km(base_lat, base_lng, city_point[0], city_point[1])

        rows.append(
            {
                "Coming_From": coming_from_raw or "Unknown",
                "Distance_km": float(distance_km),
                "RSVP_Status": "Attending",
                "Total_Guests": max(1, int(getattr(guest, "number_of_people", 1) or 1)),
            }
        )

    return pd.DataFrame(rows, columns=["Coming_From", "Distance_km", "RSVP_Status", "Total_Guests"])
