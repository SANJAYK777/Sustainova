from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import uuid4

from database import get_db
from models.models import Event
from schemas.schemas import EventCreate, EventOut
from dependencies.auth import require_role
from utils.qr import generate_event_qr

router = APIRouter(prefix="/events", tags=["events"])


# ==========================================================
# CREATE EVENT (Organizer Only)
# ==========================================================
@router.post("/", response_model=EventOut)
def create_event(
    event: EventCreate,
    user=Depends(require_role("organizer")),
    db: Session = Depends(get_db)
):
    # Generate secure event token
    token = str(uuid4())

    new_event = Event(
        user_id=int(user["sub"]),
        event_name=event.event_name,
        hall_name=event.hall_name,
        location=event.location,
        bus_routes=event.bus_routes,
        bus_stops=event.bus_stops,
        expected_count=event.expected_count,
        event_date=event.event_date,
        invitation_image=event.invitation_image,
        latitude=event.latitude,
        longitude=event.longitude,
        event_token=token
    )

    db.add(new_event)
    db.commit()
    db.refresh(new_event)

    # Generate QR Code
    qr_url = generate_event_qr(token)
    new_event.qr_code_url = qr_url
    db.commit()

    return new_event


# ==========================================================
# GET ALL EVENTS FOR ORGANIZER
# ==========================================================
@router.get("/", response_model=list[EventOut])
def get_my_events(
    user=Depends(require_role("organizer")),
    db: Session = Depends(get_db)
):
    return db.query(Event).filter(
        Event.user_id == int(user["sub"])
    ).all()


# ==========================================================
# GET SINGLE EVENT (Organizer Only)
# ==========================================================
@router.get("/{event_id}", response_model=EventOut)
def get_event(
    event_id: int,
    user=Depends(require_role("organizer")),
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.user_id == int(user["sub"])
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return event


# ==========================================================
# UPDATE EVENT (Organizer Only)
# ==========================================================
@router.put("/{event_id}", response_model=EventOut)
def update_event(
    event_id: int,
    updated_event: EventCreate,
    user=Depends(require_role("organizer")),
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.user_id == int(user["sub"])
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    event.event_name = updated_event.event_name
    event.hall_name = updated_event.hall_name
    event.location = updated_event.location
    event.bus_routes = updated_event.bus_routes
    event.bus_stops = updated_event.bus_stops
    event.expected_count = updated_event.expected_count
    event.event_date = updated_event.event_date
    event.latitude = updated_event.latitude
    event.longitude = updated_event.longitude

    db.commit()
    db.refresh(event)

    return event


# ==========================================================
# DELETE EVENT (Organizer Only)
# ==========================================================
@router.delete("/{event_id}")
def delete_event(
    event_id: int,
    user=Depends(require_role("organizer")),
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.user_id == int(user["sub"])
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    db.delete(event)
    db.commit()

    return {"message": "Event deleted successfully"}


# ==========================================================
# PUBLIC: GET EVENT BY TOKEN (QR SCAN)
# ==========================================================
@router.get("/token/{token}")
def get_event_by_token(
    token: str,
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(
        Event.event_token == token
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return {
        "id": event.id,
        "event_name": event.event_name,
        "event_date": event.event_date,
        "hall_name": event.hall_name,
        "location": event.location,
        "latitude": event.latitude,
        "longitude": event.longitude,
        "bus_routes": event.bus_routes,
        "bus_stops": event.bus_stops,
        "invitation_image": event.invitation_image
    }
