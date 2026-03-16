from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies.auth import get_current_user
from models.models import Event, Guest, SOS
from schemas.schemas import SOSOut, SOSTriggerIn

router = APIRouter(prefix="/sos", tags=["sos"])


@router.post("/trigger")
def trigger(
    payload: SOSTriggerIn,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.get("role") != "guest":
        raise HTTPException(status_code=403, detail="Access forbidden")

    guest = db.query(Guest).filter(Guest.id == int(user.get("sub"))).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    reason = (payload.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=422, detail="Reason is required")

    new_sos = SOS(
        event_id=guest.event_id,
        guest_id=guest.id,
        reason=reason,
        triggered_at=datetime.now(timezone.utc),
        resolved=False,
    )
    db.add(new_sos)
    db.commit()
    db.refresh(new_sos)

    return {"message": "SOS alert sent", "sos_id": new_sos.id}


@router.get("/active/{event_id}")
def active_sos(
    event_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.get("role") != "organizer":
        raise HTTPException(status_code=403, detail="Access forbidden")

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.user_id != int(user.get("sub")):
        raise HTTPException(status_code=403, detail="Access forbidden")

    alerts = (
        db.query(SOS, Guest, Event)
        .join(Guest, Guest.id == SOS.guest_id)
        .join(Event, Event.id == SOS.event_id)
        .filter(SOS.event_id == event_id, SOS.resolved.is_(False))
        .order_by(SOS.triggered_at.desc())
        .all()
    )

    return [
        {
            "id": sos.id,
            "guest_name": guest.name,
            "guest_phone": guest.phone,
            "event_name": event_row.event_name,
            "reason": sos.reason,
            "triggered_at": sos.triggered_at,
            "resolved": sos.resolved,
        }
        for sos, guest, event_row in alerts
    ]


@router.get("/event/{event_id}")
def event_sos_alerts(
    event_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.get("role") != "organizer":
        raise HTTPException(status_code=403, detail="Access forbidden")

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.user_id != int(user.get("sub")):
        raise HTTPException(status_code=403, detail="Access forbidden")

    alerts = (
        db.query(SOS, Guest, Event)
        .join(Guest, Guest.id == SOS.guest_id)
        .join(Event, Event.id == SOS.event_id)
        .filter(SOS.event_id == event_id)
        .order_by(SOS.triggered_at.desc())
        .all()
    )

    return [
        {
            "id": sos.id,
            "guest_name": guest.name,
            "guest_phone": guest.phone,
            "event_name": event_row.event_name,
            "reason": sos.reason,
            "triggered_at": sos.triggered_at,
            "resolved": sos.resolved,
        }
        for sos, guest, event_row in alerts
    ]


@router.put("/resolve/{sos_id}", response_model=SOSOut)
def resolve_sos(
    sos_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.get("role") != "organizer":
        raise HTTPException(status_code=403, detail="Access forbidden")

    record = db.query(SOS).filter(SOS.id == sos_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="SOS not found")

    event = db.query(Event).filter(Event.id == record.event_id).first()
    if not event or event.user_id != int(user.get("sub")):
        raise HTTPException(status_code=403, detail="Access forbidden")

    record.resolved = True
    db.commit()
    db.refresh(record)
    return record
