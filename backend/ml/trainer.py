from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import logging

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
import xgboost as xgb

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
DATASET_PATH = BASE_DIR / "data" / "guest_rsvp_dataset.csv"
MODEL_PATH = BASE_DIR / "xgb_model.pkl"
MODEL_META_PATH = BASE_DIR / "xgb_model.meta.json"
logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "group_size",
    "transport_type",
    "parking_required",
    "room_required",
    "distance_km",
    "day_of_week",
    "weather",
]
TARGET_COLUMN = "actual_attended"
CATEGORICAL_COLUMNS = ["transport_type", "parking_required", "room_required", "day_of_week", "weather"]
NUMERIC_COLUMNS = ["group_size", "distance_km"]
REQUIRED_COLUMNS = set(FEATURE_COLUMNS + [TARGET_COLUMN])
DATASET_CANDIDATES = [
    BASE_DIR / "data" / "guest_rsvp_dataset.csv",
    BASE_DIR / "dataset" / "guest_dataset.csv",
]
LEGACY_COLUMNS = {
    "Total_Guests",
    "Transport_Mode",
    "Parking_Required",
    "Room_Required",
    "Distance_km",
    "RSVP_Status",
}


def _normalize_transport(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in {"car", "bike", "bus", "cab", "walk"}:
        return raw
    if raw in {"taxi", "auto", "auto-rickshaw", "autorickshaw"}:
        return "cab"
    return "walk"


def _normalize_yes_no(value: object) -> str:
    text = str(value).strip().lower()
    return "yes" if text in {"1", "yes", "true", "y"} else "no"


def _rsvp_to_attendance_factor(value: object) -> float:
    text = str(value).strip().lower()
    if text in {"attending", "yes"}:
        return 0.92
    if text in {"maybe", "tentative"}:
        return 0.6
    if text in {"not attending", "no", "declined"}:
        return 0.05
    return 0.8


def _coerce_legacy_dataset(df: pd.DataFrame) -> pd.DataFrame | None:
    if not LEGACY_COLUMNS.issubset(set(df.columns)):
        return None

    working = df.copy()
    working["group_size"] = pd.to_numeric(working["Total_Guests"], errors="coerce").fillna(1).clip(lower=1)
    working["transport_type"] = working["Transport_Mode"].map(_normalize_transport)
    working["parking_required"] = working["Parking_Required"].map(_normalize_yes_no)
    working["room_required"] = working["Room_Required"].map(_normalize_yes_no)
    working["distance_km"] = pd.to_numeric(working["Distance_km"], errors="coerce").fillna(0.0).clip(lower=0.0)
    working["day_of_week"] = "saturday"
    working["weather"] = "clear"
    factors = working["RSVP_Status"].map(_rsvp_to_attendance_factor)
    working["actual_attended"] = (working["group_size"] * factors).clip(lower=0.0)

    return working[FEATURE_COLUMNS + [TARGET_COLUMN]]


def _load_and_validate_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Training dataset not found: {path}")
    df = pd.read_csv(path)
    missing_columns = sorted(REQUIRED_COLUMNS - set(df.columns))
    if not missing_columns:
        return df

    legacy_df = _coerce_legacy_dataset(df)
    if legacy_df is not None:
        logger.warning("Coerced legacy dataset into training format: %s", path)
        return legacy_df

    raise ValueError(f"Dataset is missing required columns: {missing_columns}")


def _load_training_dataset(dataset_path: Path) -> pd.DataFrame:
    candidates = [Path(dataset_path)]
    for candidate in DATASET_CANDIDATES:
        if candidate not in candidates:
            candidates.append(candidate)

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            df = _load_and_validate_dataset(candidate)
            if candidate != Path(dataset_path):
                logger.warning("Using fallback ML dataset: %s", candidate)
            return df
        except (FileNotFoundError, ValueError) as exc:
            last_error = exc
            continue

    if last_error:
        raise last_error
    raise FileNotFoundError("No valid ML training dataset available")


def train_model(dataset_path: Path = DATASET_PATH, model_path: Path = MODEL_PATH) -> dict[str, float]:
    df = _load_training_dataset(dataset_path)
    x = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=42)

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLUMNS),
            ("num", "passthrough", NUMERIC_COLUMNS),
        ]
    )

    model = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        tree_method="hist",
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )
    pipeline.fit(x_train, y_train)

    preds = pipeline.predict(x_test)
    metrics = {
        "mae": float(mean_absolute_error(y_test, preds)),
        "rmse": float(mean_squared_error(y_test, preds) ** 0.5),
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_path)
    try:
        metadata = {
            "xgboost_version": xgb.__version__,
            "sklearn_version": getattr(__import__("sklearn"), "__version__", "unknown"),
            "trained_at": datetime.utcnow().isoformat() + "Z",
            "dataset_path": str(dataset_path),
        }
        MODEL_META_PATH.write_text(json.dumps(metadata), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to write model metadata: %s", exc)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train RSVP XGBoost model and save to ml/xgb_model.pkl.")
    parser.add_argument("--dataset", type=str, default=str(DATASET_PATH))
    parser.add_argument("--model-out", type=str, default=str(MODEL_PATH))
    args = parser.parse_args()

    metrics = train_model(dataset_path=Path(args.dataset), model_path=Path(args.model_out))
    print(f"Model saved: {args.model_out}")
    print(f"MAE: {metrics['mae']:.4f}, RMSE: {metrics['rmse']:.4f}")


if __name__ == "__main__":
    main()
