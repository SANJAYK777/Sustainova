from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models.models import Guest, Attendance
from schemas.schemas import CheckinResponse

router = APIRouter(tags=["checkin"])


@router.get("/checkin/{guest_qr_token}", response_model=CheckinResponse)
def checkin_guest(guest_qr_token: str, db: Session = Depends(get_db)):
    guest = db.query(Guest).filter(Guest.guest_qr_token == guest_qr_token).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    existing_attendance = db.query(Attendance).filter(Attendance.guest_id == guest.id).first()
    if existing_attendance:
        checked_in_guests = db.query(func.count(Attendance.id)).filter(
            Attendance.event_id == guest.event_id
        ).scalar() or 0
        total_guests = db.query(func.count(Guest.id)).filter(
            Guest.event_id == guest.event_id
        ).scalar() or 0
        real_present_count = db.query(func.coalesce(func.sum(Attendance.actual_people_count), 0)).filter(
            Attendance.event_id == guest.event_id
        ).scalar() or 0

        return CheckinResponse(
            status="already_checked_in",
            message="Already checked in",
            guest_id=guest.id,
            guest_name=guest.name,
            event_id=guest.event_id,
            scanned_at=existing_attendance.scanned_at,
            checked_in_guests=checked_in_guests,
            remaining_guests=max(total_guests - checked_in_guests, 0),
            real_present_count=int(real_present_count),
        )

    scanned_at = datetime.utcnow()
    new_attendance = Attendance(
        event_id=guest.event_id,
        guest_id=guest.id,
        actual_people_count=guest.number_of_people or 1,
        scanned_at=scanned_at
    )
    db.add(new_attendance)
    db.commit()

    checked_in_guests = db.query(func.count(Attendance.id)).filter(
        Attendance.event_id == guest.event_id
    ).scalar() or 0
    total_guests = db.query(func.count(Guest.id)).filter(
        Guest.event_id == guest.event_id
    ).scalar() or 0
    real_present_count = db.query(func.coalesce(func.sum(Attendance.actual_people_count), 0)).filter(
        Attendance.event_id == guest.event_id
    ).scalar() or 0

    return CheckinResponse(
        status="checked_in",
        message="Check-in successful",
        guest_id=guest.id,
        guest_name=guest.name,
        event_id=guest.event_id,
        scanned_at=scanned_at,
        checked_in_guests=checked_in_guests,
        remaining_guests=max(total_guests - checked_in_guests, 0),
        real_present_count=int(real_present_count),
    )
