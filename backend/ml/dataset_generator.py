from __future__ import annotations

import argparse
from pathlib import Path
import random

import pandas as pd


TRANSPORT_CHOICES = ["car", "bike", "bus", "cab", "walk"]
TRANSPORT_WEIGHTS = [0.32, 0.18, 0.28, 0.14, 0.08]
DAY_CHOICES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]
DAY_WEIGHTS = [0.1, 0.1, 0.1, 0.12, 0.16, 0.22, 0.2]
WEATHER_CHOICES = ["clear", "cloudy", "rain", "storm"]
WEATHER_WEIGHTS = [0.48, 0.25, 0.2, 0.07]


def _sample_group_size(rng: random.Random) -> int:
    base = rng.choices([1, 2, 3, 4, 5, 6, 7, 8], weights=[30, 26, 16, 11, 8, 5, 3, 1], k=1)[0]
    return int(base)


def _attendance_rate(transport: str, day: str, weather: str, distance_km: float, room_required: str) -> float:
    rate = 0.84

    if day in {"saturday", "sunday"}:
        rate += 0.06
    elif day in {"monday", "tuesday"}:
        rate -= 0.03

    if weather == "rain":
        rate -= 0.08
    elif weather == "storm":
        rate -= 0.2
    elif weather == "clear":
        rate += 0.03

    if transport == "walk":
        rate += 0.04
    elif transport == "bus":
        rate -= 0.02

    rate -= min(distance_km, 300.0) * 0.00035

    if room_required == "yes":
        rate += 0.03

    return max(0.25, min(rate, 1.0))


def generate_dataset(rows: int = 1200, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    records: list[dict[str, object]] = []

    for guest_id in range(1, rows + 1):
        group_size = _sample_group_size(rng)
        transport_type = rng.choices(TRANSPORT_CHOICES, weights=TRANSPORT_WEIGHTS, k=1)[0]
        weather = rng.choices(WEATHER_CHOICES, weights=WEATHER_WEIGHTS, k=1)[0]
        day_of_week = rng.choices(DAY_CHOICES, weights=DAY_WEIGHTS, k=1)[0]

        distance_km = round(min(rng.gammavariate(2.0, 18.0), 320.0), 1)

        parking_required = "yes" if transport_type in {"car", "bike"} else ("yes" if rng.random() < 0.08 else "no")
        room_required = "yes" if (distance_km > 120.0 and rng.random() < 0.75) or rng.random() < 0.1 else "no"

        rate = _attendance_rate(
            transport=transport_type,
            day=day_of_week,
            weather=weather,
            distance_km=distance_km,
            room_required=room_required,
        )
        noise = rng.uniform(-0.25, 0.25)
        attended = max(0.0, min(float(group_size), group_size * rate + noise))

        records.append(
            {
                "guest_id": guest_id,
                "group_size": group_size,
                "transport_type": transport_type,
                "parking_required": parking_required,
                "room_required": room_required,
                "distance_km": distance_km,
                "day_of_week": day_of_week,
                "weather": weather,
                "actual_attended": round(attended, 2),
            }
        )

    data = pd.DataFrame(records)
    if int(data["group_size"].sum()) <= 350:
        raise RuntimeError("Generated guest count must exceed 350 people.")

    return data


def save_dataset(path: Path, rows: int = 1200, seed: int = 42) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = generate_dataset(rows=rows, seed=seed)
    df.to_csv(path, index=False)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic RSVP training dataset.")
    parser.add_argument("--rows", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        type=str,
        default=str(Path(__file__).resolve().parent / "dataset" / "guest_dataset.csv"),
    )
    args = parser.parse_args()

    out_path = save_dataset(path=Path(args.out), rows=max(args.rows, 1000), seed=args.seed)
    print(f"Dataset saved: {out_path}")


if __name__ == "__main__":
    main()
