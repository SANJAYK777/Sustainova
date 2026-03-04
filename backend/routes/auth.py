from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime
import os
import shutil

from database import get_db
from models.models import User, Guest, Event
from schemas.schemas import OTPRequest, OTPVerify
from utils.security import create_access_token, get_password_hash
from utils.otp import generate_otp, store_otp, verify_otp
from utils.qr import generate_event_qr
from utils.phone import normalize_phone, phone_candidates

router = APIRouter(prefix="/auth", tags=["auth"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/register")
def register_organizer(
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    event_name: str = Form(...),
    event_date: str | None = Form(None),
    location: str = Form(...),
    hall_name: str = Form(...),
    bus_routes: str = Form(...),
    bus_stops: str = Form(...),
    expected_count: int = Form(...),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    invitation_image: UploadFile | None = File(None),
    db: Session = Depends(get_db)
):
    """Register a new organizer and create their event."""

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    existing_phone = db.query(User).filter(User.phone == phone).first()
    if existing_phone:
        raise HTTPException(status_code=400, detail="Phone already registered")

    parsed_event_date = None
    if event_date:
        try:
            parsed_event_date = datetime.fromisoformat(event_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid event_date format")

    image_path = None
    if invitation_image:
        safe_original_name = os.path.basename(invitation_image.filename or "invitation.jpg")
        filename = f"{uuid4()}_{safe_original_name}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(invitation_image.file, buffer)
        image_path = f"uploads/{filename}".replace("\\", "/")

    password_hash = get_password_hash(str(uuid4()))

    new_user = User(
        name=name,
        email=email,
        phone=phone,
        password_hash=password_hash,
        role="organizer"
    )
    db.add(new_user)
    db.flush()

    event_token = str(uuid4())
    new_event = Event(
        user_id=new_user.id,
        event_name=event_name,
        event_date=parsed_event_date,
        event_token=event_token,
        hall_name=hall_name,
        location=location,
        bus_routes=bus_routes,
        bus_stops=bus_stops,
        expected_count=expected_count,
        latitude=latitude,
        longitude=longitude,
        invitation_image=image_path,
        invitation_image_url=None,
    )

    db.add(new_event)
    db.flush()

    qr_url = generate_event_qr(event_token)
    new_event.qr_code_url = qr_url

    db.commit()
    db.refresh(new_event)

    return {"qr_code_url": qr_url}


@router.post("/request-otp")
def request_otp(data: OTPRequest, db: Session = Depends(get_db)):
    phone_clean = normalize_phone(data.phone)
    candidates = phone_candidates(data.phone)

    user = db.query(User).filter(User.phone.in_(candidates)).first()
    guest = db.query(Guest).filter(Guest.phone.in_(candidates)).first()

    if not user and not guest:
        raise HTTPException(status_code=404, detail="Phone not registered")

    otp = generate_otp()
    store_otp(phone_clean, otp)
    print(f"DEV OTP for {phone_clean}: {otp}")

    return {"message": "OTP sent successfully", "dev_otp": otp}


@router.post("/verify-otp")
def verify_user_otp(data: OTPVerify, db: Session = Depends(get_db)):
    phone_clean = normalize_phone(data.phone)
    candidates = phone_candidates(data.phone)

    if not verify_otp(phone_clean, data.otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    user = db.query(User).filter(User.phone.in_(candidates)).first()
    if user:
        token = create_access_token({
            "sub": str(user.id),
            "role": "organizer"
        })
        return {"access_token": token, "role": "organizer"}

    guest = db.query(Guest).filter(Guest.phone.in_(candidates)).first()
    if guest:
        token = create_access_token({
            "sub": str(guest.id),
            "role": "guest",
            "event_id": guest.event_id
        })
        return {"access_token": token, "role": "guest"}

    raise HTTPException(status_code=404, detail="User not found")
