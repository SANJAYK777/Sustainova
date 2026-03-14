from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path
from typing import Iterable

import joblib
import pandas as pd

from ml.trainer import FEATURE_COLUMNS, DATASET_PATH, MODEL_PATH, train_model


def ensure_model_exists() -> Path:
    if MODEL_PATH.exists():
        return MODEL_PATH

    train_model(dataset_path=DATASET_PATH, model_path=MODEL_PATH)
    return MODEL_PATH


def _load_model():
    model_path = ensure_model_exists()
    model = joblib.load(model_path)
    print("ML model loaded")
    return model


MODEL = None


def _get_model():
    global MODEL
    if MODEL is None:
        MODEL = _load_model()
    return MODEL


def predict_attendance(data: dict) -> int:
    print("Prediction input:", data)
    model = _get_model()
    df = pd.DataFrame([data])
    prediction = model.predict(df)
    print("Prediction output:", prediction)
    return int(max(0, round(float(prediction[0]))))


def _normalize_yes_no(value: str | None) -> str:
    return "yes" if (value or "").strip().lower() in {"yes", "y", "true", "1"} else "no"


def _normalize_transport(value: str | None) -> str:
    v = (value or "other").strip().lower()
    return v if v in {"car", "bike", "bus", "cab", "walk"} else "walk"


def _guest_distance_km(guest_id: int, transport_type: str) -> float:
    base_by_transport = {
        "car": 24.0,
        "bike": 14.0,
        "bus": 32.0,
        "cab": 20.0,
        "walk": 3.0,
    }
    wobble = (guest_id % 17) * 1.2
    return round(min(base_by_transport.get(transport_type, 8.0) + wobble, 320.0), 1)


def _day_of_week(event_date: datetime | None) -> str:
    return event_date.strftime("%A").lower() if event_date else "saturday"


def build_feature_rows(guests: Iterable, event_date: datetime | None, weather: str = "clear") -> list[dict]:
    rows: list[dict] = []
    day = _day_of_week(event_date)
    normalized_weather = (weather or "clear").strip().lower()
    if normalized_weather not in {"clear", "cloudy", "rain", "storm"}:
        normalized_weather = "clear"

    for guest in guests:
        transport = _normalize_transport(getattr(guest, "transport_type", None))
        parking_type = (getattr(guest, "parking_type", None) or "").strip().lower()
        parking_required = "yes" if parking_type in {"car", "bike"} else "no"
        rows.append(
            {
                "group_size": max(1, int(getattr(guest, "number_of_people", 1) or 1)),
                "transport_type": transport,
                "parking_required": parking_required,
                "room_required": _normalize_yes_no(getattr(guest, "needs_room", None)),
                "distance_km": _guest_distance_km(int(getattr(guest, "id")), transport),
                "day_of_week": day,
                "weather": normalized_weather,
            }
        )
    return rows


def predict_event_resources(guests: Iterable, event_date: datetime | None, weather: str = "clear") -> dict[str, int]:
    rows = build_feature_rows(guests, event_date, weather=weather)
    if not rows:
        return {
            "predicted_attendance": 0,
            "predicted_car_parking": 0,
            "predicted_bike_parking": 0,
            "predicted_rooms": 0,
            "food_estimate": 0,
        }

    predicted_groups = []
    for row in rows:
        prediction = predict_attendance(row)
        predicted_groups.append(max(0, min(prediction, int(row["group_size"]))))

    predicted_attendance = int(sum(predicted_groups))
    predicted_car_parking = 0
    predicted_bike_parking = 0
    predicted_rooms = 0

    for idx, row in enumerate(rows):
        attendance = predicted_groups[idx]
        if row["parking_required"] == "yes":
            if row["transport_type"] == "car":
                predicted_car_parking += int(math.ceil(attendance / 3.0))
            elif row["transport_type"] == "bike":
                predicted_bike_parking += int(math.ceil(attendance / 2.0))
        if row["room_required"] == "yes":
            predicted_rooms += int(math.ceil(attendance / 2.0))

    food_estimate = int(math.ceil(predicted_attendance * 1.1))

    return {
        "predicted_attendance": predicted_attendance,
        "predicted_car_parking": predicted_car_parking,
        "predicted_bike_parking": predicted_bike_parking,
        "predicted_rooms": predicted_rooms,
        "food_estimate": food_estimate,
    }
