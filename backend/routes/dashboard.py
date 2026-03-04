from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import math
import os

from database import get_db
from models.models import Event, Guest, SOS, Attendance
from dependencies.auth import get_current_user
from ml.predict import predict_event_resources
from utils.phone import phone_candidates

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

def normalized_parking_type(value: str | None) -> str:
    return (value or "None").strip().lower()


def invitation_path_or_url(event: Event) -> tuple[str | None, str | None]:
    """Normalize invitation image path for legacy records and expose URL fallback."""
    image_path = event.invitation_image
    image_url = event.invitation_image_url

    if image_path:
        normalized = image_path.replace("\\", "/").lstrip("/")
        if normalized.startswith("uploads/"):
            image_path = normalized
        elif "uploads/" in normalized:
            image_path = "uploads/" + normalized.split("uploads/")[-1]
        elif os.path.basename(normalized):
            image_path = f"uploads/{os.path.basename(normalized)}"

    return image_path, image_url


# ========================================
# GUEST DASHBOARD
# ========================================
@router.get("/guest")
def guest_dashboard(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Guest sees event details (event info, location, transportation)"""

    if user.get("role") != "guest":
        raise HTTPException(status_code=403, detail="Access forbidden")

    sub = str(user.get("sub") or "")
    guest = None

    # Current token format uses guest id in "sub".
    if sub.isdigit():
        guest = db.query(Guest).filter(Guest.id == int(sub)).first()

    # Backward compatibility for older tokens that stored phone in "sub".
    if not guest:
        candidates = phone_candidates(sub)
        guest = db.query(Guest).filter(Guest.phone.in_(candidates)).first()

    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    
    # Get event details
    event = db.query(Event).filter(Event.id == guest.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Return only guest-relevant details (NOT QR, NOT stats, NOT other guests)
    invitation_image, invitation_image_url = invitation_path_or_url(event)

    return {
        "guest_qr_token": guest.guest_qr_token,
        "guest_qr_code_url": guest.guest_qr_code_url,
        "event_name": event.event_name,
        "event_date": event.event_date,
        "location": event.location,
        "hall_name": event.hall_name,
        "latitude": event.latitude,
        "longitude": event.longitude,
        "bus_routes": event.bus_routes,
        "bus_stops": event.bus_stops,
        "invitation_image": invitation_image,
        "invitation_image_url": invitation_image_url,
    }


# ========================================
# ORGANIZER DASHBOARD
# ========================================
@router.get("/organizer")
def organizer_dashboard(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Organizer sees event QR, guest stats, and guest lists for parking/rooms"""

    if user.get("role") != "organizer":
        raise HTTPException(status_code=403, detail="Access forbidden")

    # Get organizer's event
    event = db.query(Event).filter(Event.user_id == int(user.get("sub"))).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Get all guests for this event
    guests = db.query(Guest).filter(Guest.event_id == event.id).all()
    
    # Calculate totals
    total_guests = len(guests)
    total_people = sum(g.number_of_people for g in guests) if guests else 0
    attendance_rows = db.query(Attendance).filter(Attendance.event_id == event.id).all()
    checked_in_guests = len(attendance_rows)
    remaining_guests = max(total_guests - checked_in_guests, 0)
    real_present_count = sum(a.actual_people_count or 0 for a in attendance_rows)
    
    # Count parking and room needs
    total_car_parking = sum(
        1 for g in guests if normalized_parking_type(g.parking_type) == "car"
    )
    total_bike_parking = sum(
        1 for g in guests if normalized_parking_type(g.parking_type) == "bike"
    )
    total_rooms = sum(
        1 for g in guests 
        if g.needs_room and g.needs_room.lower() == "yes"
    )
    
    # Filter lists
    car_parking_guests = [
        {
            "id": g.id,
            "name": g.name,
            "phone": g.phone,
            "number_of_people": g.number_of_people,
            "transport_type": g.transport_type
        }
        for g in guests
        if normalized_parking_type(g.parking_type) == "car"
    ]

    bike_parking_guests = [
        {
            "id": g.id,
            "name": g.name,
            "phone": g.phone,
            "number_of_people": g.number_of_people,
            "transport_type": g.transport_type
        }
        for g in guests
        if normalized_parking_type(g.parking_type) == "bike"
    ]

    room_guests = [
        {
            "id": g.id,
            "name": g.name,
            "phone": g.phone,
            "number_of_people": g.number_of_people,
            "transport_type": g.transport_type
        }
        for g in guests
        if g.needs_room and g.needs_room.lower() == "yes"
    ]

    rooms_needed = db.query(Guest).filter(
        Guest.event_id == event.id,
        Guest.needs_room == "Yes"
    ).all()

    rooms_needed_guests = [
        {
            "name": g.name,
            "phone": g.phone,
            "number_of_people": g.number_of_people,
        }
        for g in rooms_needed
    ]

    parking_guests = [
        {
            "name": g.name,
            "phone": g.phone,
            "number_of_people": g.number_of_people,
            "parking_type": (g.parking_type or "None"),
        }
        for g in guests
        if normalized_parking_type(g.parking_type) in {"car", "bike"}
    ]

    expected_guests = total_people
    try:
        ml_prediction = predict_event_resources(
            guests=guests,
            event_date=event.event_date,
            weather="clear",
        )
    except Exception as exc:
        print(f"ML dashboard fallback used: {exc}")
        ml_prediction = {
            "predicted_attendance": int(expected_guests * 0.85),
            "predicted_car_parking": total_car_parking,
            "predicted_bike_parking": total_bike_parking,
            "predicted_rooms": total_rooms,
            "food_estimate": int(expected_guests * 0.95),
        }
    
    return {
        "event_id": event.id,
        "qr_code_url": event.qr_code_url,
        "actual": {
            "total_guests": total_guests,
            "checked_in_guests": checked_in_guests,
            "remaining_guests": remaining_guests,
            "real_present_count": real_present_count,
            "total_people": total_people,
            "total_car_parking": total_car_parking,
            "total_bike_parking": total_bike_parking,
            "total_rooms": total_rooms
        },
        "safety": {
            "safety_total_guests": math.ceil(total_guests * 1.2),
            "safety_total_people": math.ceil(total_people * 1.2),
            "safety_car_parking": math.ceil(total_car_parking * 1.2),
            "safety_bike_parking": math.ceil(total_bike_parking * 1.2),
            "safety_total_rooms": math.ceil(total_rooms * 1.2)
        },
        "expected_guests": expected_guests,
        "total_guests": total_guests,
        "total_people": total_people,
        "total_parking": total_car_parking + total_bike_parking,
        "total_rooms_needed": total_rooms,
        "predicted_attendance": ml_prediction["predicted_attendance"],
        "predicted_car_parking": ml_prediction["predicted_car_parking"],
        "predicted_bike_parking": ml_prediction["predicted_bike_parking"],
        "predicted_rooms": ml_prediction["predicted_rooms"],
        "food_estimate": ml_prediction["food_estimate"],
        "parking_guests": parking_guests,
        "rooms_needed_guests": rooms_needed_guests,
        "car_parking_guests": car_parking_guests,
        "bike_parking_guests": bike_parking_guests,
        "room_guests": room_guests
    }


@router.get("/organizer/sos")
def organizer_sos(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.get("role") != "organizer":
        raise HTTPException(status_code=403, detail="Access forbidden")

    event = db.query(Event).filter(Event.user_id == int(user.get("sub"))).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    alerts = (
        db.query(SOS, Guest)
        .join(Guest, Guest.id == SOS.guest_id)
        .filter(SOS.event_id == event.id, SOS.resolved.is_(False))
        .order_by(SOS.triggered_at.desc())
        .all()
    )

    return [
        {
            "id": sos.id,
            "guest_name": guest.name,
            "guest_phone": guest.phone,
            "triggered_at": sos.triggered_at
        }
        for sos, guest in alerts
    ]


