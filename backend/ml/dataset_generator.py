from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ml.trainer import DATASET_PATH, FEATURE_COLUMNS, TARGET_COLUMN


def load_external_dataset(dataset_path: Path = DATASET_PATH) -> pd.DataFrame:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    df = pd.read_csv(dataset_path)
    required_columns = set(FEATURE_COLUMNS + [TARGET_COLUMN])
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {missing_columns}")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and load external Sustainova dataset CSV.")
    parser.add_argument("--dataset", type=str, default=str(DATASET_PATH))
    args = parser.parse_args()

    df = load_external_dataset(Path(args.dataset))
    print(f"Loaded dataset rows: {len(df)}")
    print(f"Loaded dataset path: {args.dataset}")


if __name__ == "__main__":
    main()

