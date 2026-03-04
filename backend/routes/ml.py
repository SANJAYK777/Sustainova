from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import math

from database import get_db
from dependencies.auth import get_current_user
from ml.predict import predict_attendance as predict_single_attendance, predict_event_resources
from models.models import Event, Guest
from schemas.schemas import MLPredictRequest, MLPredictResponse

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/predict", response_model=MLPredictResponse)
def predict_attendance_endpoint(
    payload: MLPredictRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    direct_feature_mode = all(
        value is not None
        for value in [
            payload.group_size,
            payload.transport_type,
            payload.parking_required,
            payload.room_required,
            payload.distance_km,
            payload.day_of_week,
            payload.weather,
        ]
    )

    if direct_feature_mode:
        try:
            value = predict_single_attendance(
                {
                    "group_size": int(payload.group_size or 1),
                    "transport_type": str(payload.transport_type),
                    "parking_required": str(payload.parking_required),
                    "room_required": str(payload.room_required),
                    "distance_km": float(payload.distance_km or 0.0),
                    "day_of_week": str(payload.day_of_week),
                    "weather": str(payload.weather),
                }
            )
            return {
                "predicted_attendance": value,
                "predicted_car_parking": 0,
                "predicted_bike_parking": 0,
                "predicted_rooms": 0,
                "food_estimate": int(math.ceil(value * 1.1)),
            }
        except Exception as exc:
            print(f"ML direct prediction fallback used: {exc}")
            return {
                "predicted_attendance": int(payload.group_size or 0),
                "predicted_car_parking": 0,
                "predicted_bike_parking": 0,
                "predicted_rooms": 0,
                "food_estimate": int(payload.group_size or 0),
            }

    if user.get("role") != "organizer":
        raise HTTPException(status_code=403, detail="Access forbidden")

    event = None
    if payload.event_id:
        event = db.query(Event).filter(Event.id == payload.event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        if event.user_id != int(user.get("sub")):
            raise HTTPException(status_code=403, detail="Access forbidden")
    else:
        event = db.query(Event).filter(Event.user_id == int(user.get("sub"))).first()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

    guests = db.query(Guest).filter(Guest.event_id == event.id).all()
    try:
        prediction = predict_event_resources(
            guests=guests,
            event_date=event.event_date,
            weather=payload.weather or "clear",
        )
        return prediction
    except Exception as exc:
        print(f"ML prediction fallback used: {exc}")
        return {
            "predicted_attendance": int(sum(g.number_of_people for g in guests) * 0.85),
            "predicted_car_parking": sum(1 for g in guests if (g.parking_type or "").strip().lower() == "car"),
            "predicted_bike_parking": sum(1 for g in guests if (g.parking_type or "").strip().lower() == "bike"),
            "predicted_rooms": sum(1 for g in guests if (g.needs_room or "").strip().lower() == "yes"),
            "food_estimate": int(sum(g.number_of_people for g in guests) * 0.95),
        }
