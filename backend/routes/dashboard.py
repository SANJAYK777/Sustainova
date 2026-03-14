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
analytics_router = APIRouter(prefix="/api", tags=["dashboard"])

CITY_COORDINATES = {
    "chennai": {"lat": 13.0827, "lng": 80.2707},
    "tambaram": {"lat": 12.9249, "lng": 80.1000},
    "chengalpattu": {"lat": 12.6819, "lng": 79.9835},
    "kanchipuram": {"lat": 12.8342, "lng": 79.7036},
    "pattabiram": {"lat": 13.1216, "lng": 80.0610},
    "sriperumbudur": {"lat": 12.9675, "lng": 79.9419},
    "poonamallee": {"lat": 13.0489, "lng": 80.1083},
    "tiruvallur": {"lat": 13.1439, "lng": 79.9086},
    "ramapuram": {"lat": 13.0317, "lng": 80.1767},
    "bangalore": {"lat": 12.9716, "lng": 77.5946},
    "bengaluru": {"lat": 12.9716, "lng": 77.5946},
    "coimbatore": {"lat": 11.0168, "lng": 76.9558},
    "madurai": {"lat": 9.9252, "lng": 78.1198},
    "trichy": {"lat": 10.7905, "lng": 78.7047},
    "tiruchirappalli": {"lat": 10.7905, "lng": 78.7047},
    "hyderabad": {"lat": 17.3850, "lng": 78.4867},
    "mumbai": {"lat": 19.0760, "lng": 72.8777},
    "delhi": {"lat": 28.6139, "lng": 77.2090},
    "pune": {"lat": 18.5204, "lng": 73.8567},
    "kolkata": {"lat": 22.5726, "lng": 88.3639},
}
CITY_ALIASES = {
    "blr": "bangalore",
    "bengaluru": "bangalore",
    "madras": "chennai",
    "trichy": "tiruchirappalli",
    "new delhi": "delhi",
    "poonthamallee": "poonamallee",
    "poonamalle": "poonamallee",
    "poonalmallee": "poonamallee",
    "thiruvallur": "tiruvallur",
    "sriperumbathur": "sriperumbudur",
    "pattabhiram": "pattabiram",
}
DEFAULT_COORDINATES = {"lat": 20.5937, "lng": 78.9629}  # India centroid fallback
TRAVEL_RISK_DEBUG = os.getenv("TRAVEL_RISK_DEBUG", "1") == "1"

def normalized_parking_type(value: str | None) -> str:
    raw = (value or "No Parking").strip().lower()
    if raw in {"car", "car parking"}:
        return "car"
    if raw in {"bike", "bike parking"}:
        return "bike"
    return "no parking"


def normalized_room_type(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw.startswith("single"):
        return "Single"
    if raw.startswith("double"):
        return "Double"
    if raw.startswith("triple"):
        return "Triple"
    return "Unspecified"


def city_coordinates(city: str) -> tuple[float, float] | None:
    key = " ".join((city or "").strip().lower().split())
    if not key:
        return None

    normalized = CITY_ALIASES.get(key, key)
    point = CITY_COORDINATES.get(normalized)
    if not point:
        # Fuzzy fallback: try each token in location text.
        for token in normalized.replace(",", " ").split():
            token_key = CITY_ALIASES.get(token, token)
            token_point = CITY_COORDINATES.get(token_key)
            if token_point:
                point = token_point
                break
    if not point:
        return None
    return float(point["lat"]), float(point["lng"])


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
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


def compute_travel_risk_from_guests(
    guests: list[Guest],
    event_lat: float | None,
    event_lng: float | None,
    event_location: str | None = None,
) -> dict[str, int | str]:
    local_guests = 0
    outstation_guests = 0
    predicted_attendance_value = 0.0
    resolved_distances: list[float] = []

    base_lat = float(event_lat) if event_lat is not None else None
    base_lng = float(event_lng) if event_lng is not None else None

    for guest in guests:
        coming_from = (getattr(guest, "coming_from", None) or "").strip()
        if not coming_from:
            continue

        guest_coords = city_coordinates(coming_from)
        if base_lat is not None and base_lng is not None and guest_coords:
            distance = haversine_km(base_lat, base_lng, guest_coords[0], guest_coords[1])
            if TRAVEL_RISK_DEBUG:
                print(
                    "TravelRisk Debug | "
                    f"Guest: {coming_from} | Event: {(event_location or 'Unknown').strip() or 'Unknown'} | "
                    f"Guest Coordinates: ({guest_coords[0]:.4f}, {guest_coords[1]:.4f}) | "
                    f"Event Coordinates: ({base_lat:.4f}, {base_lng:.4f}) | "
                    f"Calculated Distance: {distance:.2f} km"
                )
            resolved_distances.append(distance)
            if distance <= 250:
                local_guests += 1
                predicted_attendance_value += 0.95
            else:
                outstation_guests += 1
                predicted_attendance_value += 0.75
        else:
            # If distance cannot be derived from coordinates, treat as outstation.
            if TRAVEL_RISK_DEBUG:
                print(
                    "TravelRisk Debug | "
                    f"Guest: {coming_from} | Event: {(event_location or 'Unknown').strip() or 'Unknown'} | "
                    f"Guest Coordinates: {guest_coords} | "
                    f"Event Coordinates: ({base_lat}, {base_lng}) | "
                    "Calculated Distance: unavailable (missing coordinates)"
                )
            outstation_guests += 1
            predicted_attendance_value += 0.75

    total_guests = local_guests + outstation_guests
    predicted_attendance = int(round(predicted_attendance_value))
    if total_guests == 0:
        risk_level = "Low"
    else:
        avg_distance = (sum(resolved_distances) / len(resolved_distances)) if resolved_distances else 251.0
        risk_level = "Low" if avg_distance <= 250 else "High"

    return {
        "predicted_attendance": predicted_attendance,
        "local_guests": local_guests,
        "outstation_guests": outstation_guests,
        "risk_level": risk_level,
        # Backward-compatible keys used by existing dashboard UI.
        "Predicted_Attendance": predicted_attendance,
        "Local_Guests_Count": local_guests,
        "Outstation_Guests_Count": outstation_guests,
        "Travel_Risk_Level": risk_level,
    }


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
        "event_id": event.id,
        "qr_code_url": event.qr_code_url,
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
@analytics_router.get("/dashboard-analytics")
@router.get("/analytics")
def organizer_dashboard_analytics(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.get("role") != "organizer":
        raise HTTPException(status_code=403, detail="Access forbidden")

    event = db.query(Event).filter(Event.user_id == int(user.get("sub"))).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    guests = db.query(Guest).filter(Guest.event_id == event.id).all()
    attendance_rows = db.query(Attendance).filter(Attendance.event_id == event.id).all()
    checked_in_guest_ids = {row.guest_id for row in attendance_rows}

    locations: dict[str, int] = {}
    vehicle_types = {"Car": 0, "Bike": 0, "No Vehicle": 0}
    room_types = {"Single": 0, "Double": 0, "Triple": 0}

    for guest in guests:
        location = (guest.coming_from or "Unknown").strip() or "Unknown"
        locations[location] = locations.get(location, 0) + 1

        parking_type = normalized_parking_type(guest.parking_type)
        if parking_type == "car":
            vehicle_types["Car"] += 1
        elif parking_type == "bike":
            vehicle_types["Bike"] += 1
        else:
            vehicle_types["No Vehicle"] += 1

        room_bucket = normalized_room_type(guest.room_type)
        if room_bucket in room_types and (guest.needs_room or "").strip().lower() == "yes":
            room_types[room_bucket] += 1

    checkin_status = {
        "Checked-in": len(checked_in_guest_ids),
        "Not checked-in": max(len(guests) - len(checked_in_guest_ids), 0),
    }

    return {
        "event_id": event.id,
        "locations": locations,
        "vehicle_types": vehicle_types,
        "room_types": room_types,
        "checkin_status": checkin_status,
    }


@analytics_router.get("/guest-location-distribution")
def organizer_guest_location_distribution(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.get("role") != "organizer":
        raise HTTPException(status_code=403, detail="Access forbidden")

    event = db.query(Event).filter(Event.user_id == int(user.get("sub"))).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    grouped_rows = (
        db.query(Guest.coming_from, func.count(Guest.id))
        .filter(Guest.event_id == event.id)
        .group_by(Guest.coming_from)
        .all()
    )

    return [
        {
            "location": (location_raw or "Unknown").strip() or "Unknown",
            "guests": int(count or 0),
        }
        for location_raw, count in grouped_rows
    ]


@analytics_router.get("/guest-travel-map")
def organizer_guest_travel_map(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.get("role") != "organizer":
        raise HTTPException(status_code=403, detail="Access forbidden")

    event = db.query(Event).filter(Event.user_id == int(user.get("sub"))).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    grouped_rows = (
        db.query(Guest.coming_from, func.count(Guest.id))
        .filter(Guest.event_id == event.id)
        .group_by(Guest.coming_from)
        .all()
    )

    rows = []
    for city_raw, count in grouped_rows:
        city = (city_raw or "Unknown").strip() or "Unknown"
        coords = city_coordinates(city)
        if not coords:
            coords = (DEFAULT_COORDINATES["lat"], DEFAULT_COORDINATES["lng"])
        rows.append(
            {
                "city": city,
                "guests": int(count or 0),
                "lat": coords[0],
                "lng": coords[1],
            }
        )

    return rows


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
    
    # Count parking using explicit DB filters (exclude "No Parking")
    car_parking = db.query(Guest).filter(
        Guest.event_id == event.id,
        Guest.parking_type.in_(["Car Parking", "Car"])
    ).count()
    bike_parking = db.query(Guest).filter(
        Guest.event_id == event.id,
        Guest.parking_type.in_(["Bike Parking", "Bike"])
    ).count()
    print("Car parking:", car_parking)
    print("Bike parking:", bike_parking)

    total_car_parking = car_parking
    total_bike_parking = bike_parking
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
            "coming_from": g.coming_from,
            "transport_type": g.transport_type,
            "vehicle_number": g.vehicle_number,
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
            "coming_from": g.coming_from,
            "transport_type": g.transport_type,
            "vehicle_number": g.vehicle_number,
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
            "transport_type": g.transport_type,
            "room_required": "Yes",
            "room_type": g.room_type,
            "aadhar_number": g.aadhar_number,
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
            "room_required": "Yes" if g.needs_room and g.needs_room.lower() == "yes" else "No",
            "room_type": g.room_type,
            "aadhar_number": g.aadhar_number,
        }
        for g in rooms_needed
    ]

    parking_guests = [
        {
            "name": g.name,
            "phone": g.phone,
            "number_of_people": g.number_of_people,
            "parking_type": (g.parking_type or "None"),
            "vehicle_number": g.vehicle_number,
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

    travel_risk = compute_travel_risk_from_guests(
        guests=guests,
        event_lat=event.latitude,
        event_lng=event.longitude,
        event_location=event.location,
    )
    
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
            "safety_total_guests": total_guests,
            "safety_total_people": total_people,
            "safety_car_parking": total_car_parking,
            "safety_bike_parking": total_bike_parking,
            "safety_total_rooms": total_rooms
        },
        "expected_guests": expected_guests,
        "total_guests": total_guests,
        "total_people": total_people,
        "total_parking": total_car_parking + total_bike_parking,
        "total_rooms_needed": total_rooms,
        "car_parking_needed": total_car_parking,
        "bike_parking_needed": total_bike_parking,
        "predicted_attendance": ml_prediction["predicted_attendance"],
        "predicted_car_parking": ml_prediction["predicted_car_parking"],
        "predicted_bike_parking": ml_prediction["predicted_bike_parking"],
        "predicted_rooms": ml_prediction["predicted_rooms"],
        "food_estimate": ml_prediction["food_estimate"],
        "travel_risk": travel_risk,
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


