from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging
import re
from uuid import uuid4
import csv
import io
from database import get_db
from models.models import Guest, Event, VehicleDetail
from schemas.schemas import GuestCreate, GuestOut, GuestRSVPCreate, GuestRegistrationUpdate, GuestRegistrationStatusOut
from dependencies.auth import require_role, get_current_user
from utils.security import get_password_hash
from utils.phone import normalize_phone, phone_candidates
from utils.qr import generate_guest_qr

router = APIRouter(prefix="/guests", tags=["guests"])
management_router = APIRouter(prefix="/api/guest", tags=["guests"])
logger = logging.getLogger(__name__)

def normalize_parking_type(value: str | None) -> str:
    raw = (value or "None").strip().lower()
    if raw == "car":
        return "Car"
    if raw == "bike":
        return "Bike"
    return "None"


def normalize_coming_from(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def normalize_vehicle_number(value: str | None, parking_type: str) -> str | None:
    if parking_type == "None":
        return None
    cleaned = (value or "").strip()
    return cleaned or None


VEHICLE_NUMBER_PATTERN = re.compile(r"^[A-Z0-9]{6,12}$")


def normalize_vehicle_numbers(
    values: list[str] | None,
    expected_count: int,
    label: str,
) -> list[str]:
    if expected_count <= 0:
        return []
    if not values or len(values) != expected_count:
        raise HTTPException(
            status_code=400,
            detail=f"{label} numbers must contain exactly {expected_count} values",
        )
    cleaned: list[str] = []
    for idx, raw in enumerate(values, start=1):
        normalized = re.sub(r"[^A-Za-z0-9]", "", (raw or "")).upper()
        if not normalized or not VEHICLE_NUMBER_PATTERN.match(normalized):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {label} number at position {idx}",
            )
        cleaned.append(normalized)
    return cleaned


def normalize_parking_counts(
    car_count: int | None,
    bike_count: int | None,
) -> tuple[int, int]:
    car_value = int(car_count or 0)
    bike_value = int(bike_count or 0)
    if car_value < 0 or bike_value < 0:
        raise HTTPException(status_code=400, detail="car_count and bike_count cannot be negative")
    return car_value, bike_value


def derive_parking_type(car_count: int, bike_count: int) -> str:
    if car_count > 0 and bike_count == 0:
        return "Car"
    if bike_count > 0 and car_count == 0:
        return "Bike"
    if car_count == 0 and bike_count == 0:
        return "None"
    return "Car"


def normalize_room_details(
    needs_room: str | None,
    aadhar_number: str | None,
    room_type: str | None,
) -> tuple[str | None, str | None]:
    if (needs_room or "").strip().lower() != "yes":
        return None, None

    aadhar_digits = "".join(ch for ch in (aadhar_number or "") if ch.isdigit())
    if aadhar_digits and len(aadhar_digits) != 12:
        raise HTTPException(status_code=400, detail="Aadhar number must be exactly 12 digits")

    room_type_clean = (room_type or "").strip() or None
    allowed_room_types = {"Single Bed", "Double Bed", "Triple Bed"}
    if room_type_clean and room_type_clean not in allowed_room_types:
        raise HTTPException(status_code=400, detail="Invalid room type")
    return (aadhar_digits or None), room_type_clean


def resolve_guest_for_user(db: Session, user: dict) -> Guest | None:
    sub = str(user.get("sub") or "")
    guest = None
    if sub.isdigit():
        guest = db.query(Guest).filter(Guest.id == int(sub)).first()
    if guest:
        return guest
    candidates = phone_candidates(sub)
    return db.query(Guest).filter(Guest.phone.in_(candidates)).first()


@router.post("/", response_model=GuestOut)
def add_guest(
    guest: GuestCreate,
    user = Depends(require_role("organizer")),
    db: Session = Depends(get_db)
):
    phone_clean = normalize_phone(guest.phone)
    car_count_clean, bike_count_clean = normalize_parking_counts(
        guest.car_count, guest.bike_count
    )
    parking_clean = derive_parking_type(car_count_clean, bike_count_clean)
    coming_from_clean = normalize_coming_from(guest.coming_from)
    car_numbers_clean = normalize_vehicle_numbers(
        guest.car_numbers, car_count_clean, "Car"
    )
    bike_numbers_clean = normalize_vehicle_numbers(
        guest.bike_numbers, bike_count_clean, "Bike"
    )
    vehicle_number_clean = normalize_vehicle_number(
        guest.vehicle_number, parking_clean
    ) or (car_numbers_clean[0] if car_numbers_clean else (bike_numbers_clean[0] if bike_numbers_clean else None))
    aadhar_number_clean, room_type_clean = normalize_room_details(
        guest.needs_room, guest.aadhar_number, guest.room_type
    )
    print("Parking type received:", guest.parking_type)

    event = db.query(Event).filter(
        Event.id == guest.event_id,
        Event.user_id == int(user["sub"])
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    existing_guest = db.query(Guest).filter(
        Guest.phone == phone_clean,
        Guest.event_id == guest.event_id
    ).first()

    if existing_guest:
        raise HTTPException(
            status_code=400,
            detail="Guest with this phone already exists"
        )

    # The current DB schema keeps guest phone globally unique (not per-event).
    # Return an explicit message before hitting IntegrityError.
    global_existing_guest = db.query(Guest).filter(
        Guest.phone == phone_clean
    ).first()
    if global_existing_guest and global_existing_guest.event_id != guest.event_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "This phone is already used in another event. "
                "Current database schema enforces global unique guest phones."
            )
        )

    new_guest = Guest(
        name=guest.name,
        phone=phone_clean,
        password_hash=get_password_hash(str(uuid4())),
        number_of_people=guest.number_of_people,
        coming_from=coming_from_clean,
        transport_type=guest.transport_type,
        parking_type=parking_clean,
        car_count=car_count_clean,
        bike_count=bike_count_clean,
        vehicle_number=vehicle_number_clean,
        needs_room=guest.needs_room,
        aadhar_number=aadhar_number_clean,
        room_type=room_type_clean,
        event_id=guest.event_id,
        guest_qr_token=str(uuid4()),
        status="registered",
    )

    new_guest.guest_qr_code_url = generate_guest_qr(new_guest.guest_qr_token)

    db.add(new_guest)
    db.flush()

    vehicle_rows = [
        VehicleDetail(guest_id=new_guest.id, vehicle_type="car", vehicle_number=number)
        for number in car_numbers_clean
    ] + [
        VehicleDetail(guest_id=new_guest.id, vehicle_type="bike", vehicle_number=number)
        for number in bike_numbers_clean
    ]
    if vehicle_rows:
        db.add_all(vehicle_rows)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        constraint = getattr(getattr(e.orig, "diag", None), "constraint_name", None)
        logger.exception("Guest insert failed. constraint=%s", constraint)
        raise HTTPException(
            status_code=400,
            detail=(
                "Guest create failed due to a database constraint"
                + (f" ({constraint})" if constraint else "")
            )
        )
    db.refresh(new_guest)
    print("Guest created:", new_guest.phone)
    print("Saved parking_type:", new_guest.parking_type)

    response = GuestOut.model_validate(new_guest)
    response.car_numbers = car_numbers_clean
    response.bike_numbers = bike_numbers_clean
    return response


@router.post("/rsvp", response_model=GuestOut)
def add_guest_rsvp(
    guest: GuestRSVPCreate,
    db: Session = Depends(get_db)
):
    phone_clean = normalize_phone(guest.phone)
    car_count_clean, bike_count_clean = normalize_parking_counts(
        guest.car_count, guest.bike_count
    )
    parking_clean = derive_parking_type(car_count_clean, bike_count_clean)
    coming_from_clean = normalize_coming_from(guest.coming_from)
    car_numbers_clean = normalize_vehicle_numbers(
        guest.car_numbers, car_count_clean, "Car"
    )
    bike_numbers_clean = normalize_vehicle_numbers(
        guest.bike_numbers, bike_count_clean, "Bike"
    )
    vehicle_number_clean = normalize_vehicle_number(
        guest.vehicle_number, parking_clean
    ) or (car_numbers_clean[0] if car_numbers_clean else (bike_numbers_clean[0] if bike_numbers_clean else None))
    aadhar_number_clean, room_type_clean = normalize_room_details(
        guest.needs_room, guest.aadhar_number, guest.room_type
    )
    print("Parking type received:", guest.parking_type)

    event = db.query(Event).filter(
        Event.event_token == guest.event_token
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    existing_guest = db.query(Guest).filter(
        Guest.phone == phone_clean,
        Guest.event_id == event.id
    ).first()

    if existing_guest:
        raise HTTPException(
            status_code=400,
            detail="Guest with this phone already exists for this event"
        )

    # The current DB schema keeps guest phone globally unique (not per-event).
    # Return an explicit message before hitting IntegrityError.
    global_existing_guest = db.query(Guest).filter(
        Guest.phone == phone_clean
    ).first()
    if global_existing_guest and global_existing_guest.event_id != event.id:
        raise HTTPException(
            status_code=400,
            detail=(
                "This phone is already used in another event. "
                "Current database schema enforces global unique guest phones."
            )
        )

    new_guest = Guest(
        name=guest.name,
        phone=phone_clean,
        password_hash=get_password_hash(str(uuid4())),
        number_of_people=guest.number_of_people,
        coming_from=coming_from_clean,
        transport_type=guest.transport_type,
        parking_type=parking_clean,
        car_count=car_count_clean,
        bike_count=bike_count_clean,
        vehicle_number=vehicle_number_clean,
        needs_room=guest.needs_room,
        aadhar_number=aadhar_number_clean,
        room_type=room_type_clean,
        event_id=event.id,
        guest_qr_token=str(uuid4()),
        status="registered",
    )

    new_guest.guest_qr_code_url = generate_guest_qr(new_guest.guest_qr_token)

    db.add(new_guest)
    db.flush()

    vehicle_rows = [
        VehicleDetail(guest_id=new_guest.id, vehicle_type="car", vehicle_number=number)
        for number in car_numbers_clean
    ] + [
        VehicleDetail(guest_id=new_guest.id, vehicle_type="bike", vehicle_number=number)
        for number in bike_numbers_clean
    ]
    if vehicle_rows:
        db.add_all(vehicle_rows)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        constraint = getattr(getattr(e.orig, "diag", None), "constraint_name", None)
        logger.exception("Guest RSVP insert failed. constraint=%s", constraint)
        raise HTTPException(
            status_code=400,
            detail=(
                "Guest RSVP failed due to a database constraint"
                + (f" ({constraint})" if constraint else "")
            )
        )
    db.refresh(new_guest)
    print("Guest created:", new_guest.phone)
    print("Saved parking_type:", new_guest.parking_type)

    response = GuestOut.model_validate(new_guest)
    response.car_numbers = car_numbers_clean
    response.bike_numbers = bike_numbers_clean
    return response


@router.get("/event/{event_id}", response_model=list[GuestOut])
def list_guests(
    event_id: int,
    user = Depends(require_role("organizer")),
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.user_id == int(user["sub"])
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return db.query(Guest).filter(
        Guest.event_id == event_id
    ).all()


@router.get("/export/{event_id}")
def export_guests_csv(
    event_id: int,
    user = Depends(require_role("organizer")),
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.user_id == int(user["sub"])
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    guests = db.query(Guest).filter(Guest.event_id == event_id).all()
    vehicle_rows = db.query(VehicleDetail).filter(VehicleDetail.guest_id.in_([g.id for g in guests])).all()
    vehicle_map: dict[int, dict[str, list[str]]] = {g.id: {"car": [], "bike": []} for g in guests}
    for row in vehicle_rows:
        bucket = vehicle_map.setdefault(row.guest_id, {"car": [], "bike": []})
        if row.vehicle_type in {"car", "bike"}:
            bucket[row.vehicle_type].append(row.vehicle_number)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Name",
        "Phone",
        "Number_of_people",
        "Coming_from",
        "Transport_type",
        "Parking_needed",
        "Car_count",
        "Bike_count",
        "Car_numbers",
        "Bike_numbers",
        "Needs_room",
    ])

    for g in guests:
        writer.writerow([
            g.name,
            g.phone,
            g.number_of_people,
            g.coming_from or "",
            g.transport_type or "",
            g.parking_type or "None",
            g.car_count or 0,
            g.bike_count or 0,
            ", ".join(vehicle_map.get(g.id, {}).get("car", [])),
            ", ".join(vehicle_map.get(g.id, {}).get("bike", [])),
            g.needs_room or "No",
        ])

    csv_bytes = io.BytesIO(output.getvalue().encode("utf-8"))
    csv_bytes.seek(0)
    filename = f"guest_list_event_{event_id}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(csv_bytes, media_type="text/csv", headers=headers)


@management_router.put("/update/{guest_id}", response_model=GuestOut)
def update_guest_registration(
    guest_id: int,
    payload: GuestRegistrationUpdate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.get("role") != "guest":
        raise HTTPException(status_code=403, detail="Access forbidden")

    current_guest = resolve_guest_for_user(db, user)
    if not current_guest or current_guest.id != guest_id:
        raise HTTPException(status_code=403, detail="Access forbidden")
    if (current_guest.status or "registered").strip().lower() == "cancelled":
        raise HTTPException(status_code=400, detail="Cancelled registration cannot be updated")

    if payload.number_of_people is not None:
        if int(payload.number_of_people) < 1:
            raise HTTPException(status_code=400, detail="number_of_people must be at least 1")
        current_guest.number_of_people = int(payload.number_of_people)

    if payload.vehicle_type is not None:
        parking_clean = normalize_parking_type(payload.vehicle_type)
        current_guest.parking_type = parking_clean

        if parking_clean == "None":
            current_guest.car_count = 0
            current_guest.bike_count = 0
            current_guest.vehicle_number = None
        else:
            vehicle_count = int(payload.vehicle_count or 0)
            if vehicle_count < 1:
                raise HTTPException(status_code=400, detail="vehicle_count must be at least 1")
            if parking_clean == "Car":
                current_guest.car_count = vehicle_count
                current_guest.bike_count = 0
            elif parking_clean == "Bike":
                current_guest.bike_count = vehicle_count
                current_guest.car_count = 0
            if payload.vehicle_number is not None:
                current_guest.vehicle_number = normalize_vehicle_number(payload.vehicle_number, parking_clean)
    elif payload.vehicle_count is not None:
        vehicle_count = int(payload.vehicle_count or 0)
        if vehicle_count < 1:
            raise HTTPException(status_code=400, detail="vehicle_count must be at least 1")
        current_type = normalize_parking_type(current_guest.parking_type)
        if current_type == "Car":
            current_guest.car_count = vehicle_count
        elif current_type == "Bike":
            current_guest.bike_count = vehicle_count
        else:
            raise HTTPException(status_code=400, detail="Select vehicle_type before setting vehicle_count")

    if payload.vehicle_number is not None and payload.vehicle_type is None:
        current_type = normalize_parking_type(current_guest.parking_type)
        if current_type == "None":
            raise HTTPException(status_code=400, detail="Select vehicle_type before setting vehicle_number")
        current_guest.vehicle_number = normalize_vehicle_number(payload.vehicle_number, current_type)

    db.commit()
    db.refresh(current_guest)
    return current_guest


@management_router.put("/cancel/{guest_id}", response_model=GuestRegistrationStatusOut)
def cancel_guest_registration(
    guest_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.get("role") != "guest":
        raise HTTPException(status_code=403, detail="Access forbidden")

    current_guest = resolve_guest_for_user(db, user)
    if not current_guest or current_guest.id != guest_id:
        raise HTTPException(status_code=403, detail="Access forbidden")

    current_guest.status = "cancelled"
    current_guest.parking_type = "None"
    current_guest.car_count = 0
    current_guest.bike_count = 0
    current_guest.vehicle_number = None
    db.commit()
    db.refresh(current_guest)
    return {"guest_id": current_guest.id, "status": current_guest.status}
