from __future__ import annotations

from datetime import datetime
import json
import math
import os
import logging
import time
from pathlib import Path
from typing import Iterable

import joblib
import pandas as pd
import xgboost as xgb

from ml.trainer import FEATURE_COLUMNS, DATASET_PATH, MODEL_PATH, MODEL_META_PATH, train_model

logger = logging.getLogger(__name__)
ML_DEBUG = os.getenv("ML_DEBUG", "0") == "1"
RETRAIN_COOLDOWN_SECONDS = int(os.getenv("ML_RETRAIN_COOLDOWN_SECONDS", "300"))

LAST_RETRAIN_AT = 0.0
LAST_RETRAIN_ERROR: Exception | None = None


def ensure_model_exists() -> Path:
    if MODEL_PATH.exists():
        return MODEL_PATH

    train_model(dataset_path=DATASET_PATH, model_path=MODEL_PATH)
    return MODEL_PATH


def _load_model():
    model_path = ensure_model_exists()
    try:
        model = joblib.load(model_path)
    except Exception as exc:
        logger.warning("ML model load failed, retraining model: %s", exc)
        train_model(dataset_path=DATASET_PATH, model_path=model_path)
        model = joblib.load(model_path)

    logger.info("ML model loaded")
    return model


MODEL = None


def _get_model():
    global MODEL
    if MODEL is None:
        if _model_needs_retrain():
            _retrain_and_reload_model()
        MODEL = _load_model()
    return MODEL


def _retrain_and_reload_model():
    global MODEL
    global LAST_RETRAIN_AT
    global LAST_RETRAIN_ERROR
    now = time.time()
    if (now - LAST_RETRAIN_AT) < RETRAIN_COOLDOWN_SECONDS:
        raise RuntimeError(
            f"ML retrain skipped due to cooldown. Last error: {LAST_RETRAIN_ERROR}"
        )
    logger.warning("Rebuilding ML model due to incompatible serialized artifact")
    LAST_RETRAIN_AT = now
    try:
        train_model(dataset_path=DATASET_PATH, model_path=MODEL_PATH)
        MODEL = _load_model()
        LAST_RETRAIN_ERROR = None
        return MODEL
    except Exception as exc:
        LAST_RETRAIN_ERROR = exc
        logger.warning("ML retrain failed: %s", exc)
        raise


def _read_model_meta() -> dict | None:
    if not MODEL_META_PATH.exists():
        return None
    try:
        return json.loads(MODEL_META_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read model metadata: %s", exc)
        return None


def _model_needs_retrain() -> bool:
    meta = _read_model_meta()
    if not meta:
        return False
    return meta.get("xgboost_version") != xgb.__version__


def predict_attendance(data: dict) -> int:
    if ML_DEBUG:
        logger.info("Prediction input: %s", data)
    model = _get_model()
    df = pd.DataFrame([data])
    try:
        prediction = model.predict(df)
    except Exception as exc:
        # Handles cross-version xgboost pickle issues (e.g. missing gpu_id attr).
        logger.warning("ML predict failed, retrying with rebuilt model: %s", exc)
        try:
            model = _retrain_and_reload_model()
            prediction = model.predict(df)
        except Exception as retrain_exc:
            logger.warning("ML prediction fallback used after retrain failure: %s", retrain_exc)
            fallback = max(0, int(data.get("group_size", 0) or 0))
            return fallback
    if ML_DEBUG:
        logger.info("Prediction output: %s", prediction)
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
