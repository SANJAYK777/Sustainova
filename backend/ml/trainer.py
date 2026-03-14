from __future__ import annotations

import argparse
from pathlib import Path

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
DATASET_PATH = PROJECT_ROOT / "data" / "guest_dataset.csv"
MODEL_PATH = BASE_DIR / "xgb_model.pkl"

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


def _load_training_dataset(dataset_path: Path) -> pd.DataFrame:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Training dataset not found: {dataset_path}")

    df = pd.read_csv(dataset_path)
    required_columns = set(FEATURE_COLUMNS + [TARGET_COLUMN])
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {missing_columns}")

    return df


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
