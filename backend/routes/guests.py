from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging
from uuid import uuid4
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


@router.post("/", response_model=GuestOut)
def add_guest(
    guest: GuestCreate,
    user = Depends(require_role("organizer")),
    db: Session = Depends(get_db)
):
    phone_clean = normalize_phone(guest.phone)
    parking_clean = normalize_parking_type(guest.parking_type)
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
        transport_type=guest.transport_type,
        parking_type=parking_clean,
        needs_room=guest.needs_room,
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
        transport_type=guest.transport_type,
        parking_type=parking_clean,
        needs_room=guest.needs_room,
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
