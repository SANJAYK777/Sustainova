from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging
from uuid import uuid4
import csv
import io
from database import get_db
from models.models import Guest, Event
from schemas.schemas import GuestCreate, GuestOut, GuestRSVPCreate
from dependencies.auth import require_role
from utils.security import get_password_hash
from utils.phone import normalize_phone
from utils.qr import generate_guest_qr

router = APIRouter(prefix="/guests", tags=["guests"])
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


@router.post("/", response_model=GuestOut)
def add_guest(
    guest: GuestCreate,
    user = Depends(require_role("organizer")),
    db: Session = Depends(get_db)
):
    phone_clean = normalize_phone(guest.phone)
    parking_clean = normalize_parking_type(guest.parking_type)
    coming_from_clean = normalize_coming_from(guest.coming_from)
    vehicle_number_clean = normalize_vehicle_number(guest.vehicle_number, parking_clean)
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
        vehicle_number=vehicle_number_clean,
        needs_room=guest.needs_room,
        aadhar_number=aadhar_number_clean,
        room_type=room_type_clean,
        event_id=guest.event_id,
        guest_qr_token=str(uuid4())
    )

    new_guest.guest_qr_code_url = generate_guest_qr(new_guest.guest_qr_token)

    db.add(new_guest)
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

    return new_guest


@router.post("/rsvp", response_model=GuestOut)
def add_guest_rsvp(
    guest: GuestRSVPCreate,
    db: Session = Depends(get_db)
):
    phone_clean = normalize_phone(guest.phone)
    parking_clean = normalize_parking_type(guest.parking_type)
    coming_from_clean = normalize_coming_from(guest.coming_from)
    vehicle_number_clean = normalize_vehicle_number(guest.vehicle_number, parking_clean)
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
        vehicle_number=vehicle_number_clean,
        needs_room=guest.needs_room,
        aadhar_number=aadhar_number_clean,
        room_type=room_type_clean,
        event_id=event.id,
        guest_qr_token=str(uuid4())
    )

    new_guest.guest_qr_code_url = generate_guest_qr(new_guest.guest_qr_token)

    db.add(new_guest)
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

    return new_guest


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

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Name",
        "Phone",
        "Number_of_people",
        "Coming_from",
        "Transport_type",
        "Parking_needed",
        "Vehicle_number",
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
            g.vehicle_number or "",
            g.needs_room or "No",
        ])

    csv_bytes = io.BytesIO(output.getvalue().encode("utf-8"))
    csv_bytes.seek(0)
    filename = f"guest_list_event_{event_id}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(csv_bytes, media_type="text/csv", headers=headers)
