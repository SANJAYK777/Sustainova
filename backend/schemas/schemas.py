from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


# ---------------- USER ----------------

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str


class OrganizerRegister(BaseModel):
    name: str
    email: EmailStr
    phone: str
    event_name: str
    event_date: Optional[datetime] = None
    location: str
    hall_name: str
    bus_routes: str
    bus_stops: str
    expected_count: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    invitation_image_url: Optional[str] = None


class OTPRequest(BaseModel):
    phone: str


class OTPVerify(BaseModel):
    phone: str
    otp: str


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: Optional[str]

    class Config:
        from_attributes = True


# ---------------- EVENT ----------------

class EventCreate(BaseModel):
    event_name: str
    location: Optional[str] = None
    hall_name: Optional[str] = None
    bus_routes: Optional[str] = None
    bus_stops: Optional[str] = None
    expected_count: Optional[int] = None
    event_date: Optional[datetime] = None
    invitation_image: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class EventOut(BaseModel):
    id: int
    user_id: int
    event_token: str
    event_name: str
    event_date: Optional[datetime]
    location: str
    hall_name: str
    bus_routes: Optional[str]
    bus_stops: Optional[str]
    expected_count: int
    invitation_image: Optional[str]
    invitation_image_url: Optional[str]
    qr_code_url: Optional[str]
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True


# ---------------- GUEST ----------------

class GuestCreate(BaseModel):
    name: str
    phone: str
    number_of_people: int = 1
    transport_type: Optional[str] = None
    parking_type: Optional[str] = "None"
    needs_room: Optional[str] = None
    event_id: int


class GuestRSVPCreate(BaseModel):
    name: str
    phone: str
    number_of_people: int = 1
    transport_type: Optional[str] = None
    parking_type: Optional[str] = "None"
    needs_room: Optional[str] = None
    event_token: str


class GuestOut(BaseModel):
    id: int
    event_id: int
    name: str
    phone: str
    number_of_people: int
    transport_type: Optional[str] = None
    parking_type: str
    needs_room: Optional[str] = None
    guest_qr_token: Optional[str] = None
    guest_qr_code_url: Optional[str] = None

    class Config:
        from_attributes = True
# ---------------- ATTENDANCE ----------------

class AttendanceCreate(BaseModel):
    event_id: int
    guest_id: int
    actual_people_count: int


class AttendanceOut(BaseModel):
    id: int
    event_id: int
    guest_id: int
    actual_people_count: int
    scanned_at: datetime

    class Config:
        from_attributes = True


class CheckinResponse(BaseModel):
    status: str
    message: str
    guest_id: int
    guest_name: str
    event_id: int
    scanned_at: datetime
    checked_in_guests: int
    remaining_guests: int
    real_present_count: int
# ---------------- SOS ----------------

class SOSCreate(BaseModel):
    event_id: int
    guest_id: int


class SOSOut(BaseModel):
    id: int
    event_id: int
    guest_id: int
    triggered_at: datetime
    resolved: bool

    class Config:
        from_attributes = True


# ---------------- ML ----------------

class MLPredictRequest(BaseModel):
    event_id: Optional[int] = None
    weather: Optional[str] = "clear"
    group_size: Optional[int] = None
    transport_type: Optional[str] = None
    parking_required: Optional[str] = None
    room_required: Optional[str] = None
    distance_km: Optional[float] = None
    day_of_week: Optional[str] = None


class MLPredictResponse(BaseModel):
    predicted_attendance: int
    predicted_car_parking: int
    predicted_bike_parking: int
    predicted_rooms: int
    food_estimate: int
