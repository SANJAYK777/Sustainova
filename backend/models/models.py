from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    role = Column(String, default="organizer")
    events = relationship("Event", back_populates="owner")
    announcements = relationship("Announcement", back_populates="organizer")


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    # secure token used in URLs instead of numeric id
    event_token = Column(String, unique=True, index=True)
    event_name = Column(String, nullable=False)
    location = Column(String, nullable=True)
    google_maps_link = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    expected_count = Column(Integer, nullable=True)
    invitation_image = Column(String, nullable=True)
    invitation_image_url = Column(String, nullable=True)
    qr_code_url = Column(String, nullable=True)
    event_date = Column(DateTime, default=datetime.utcnow)
    bus_routes = Column(String, nullable=True)
    bus_stops = Column(String, nullable=True)
    hall_name = Column(String, nullable=True)
    # prediction fields
    predicted_attendance = Column(Integer, nullable=True)
    predicted_food = Column(Integer, nullable=True)
    predicted_parking = Column(Integer, nullable=True)
    predicted_rooms = Column(Integer, nullable=True)

    owner = relationship("User", back_populates="events")
    guests = relationship("Guest", back_populates="event")
    attendance = relationship("Attendance", back_populates="event")
    sos = relationship("SOS", back_populates="event")
    announcements = relationship("Announcement", back_populates="event")


class Guest(Base):
    __tablename__ = "guests"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))

    name = Column(String, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True)  # OTP-only login, no password required
    number_of_people = Column(Integer, default=1)
    coming_from = Column(String, nullable=True)
    transport_type = Column(String, nullable=True)

    parking_type = Column(String, nullable=True)  # None / Car / Bike
    car_count = Column(Integer, default=0, nullable=False)
    bike_count = Column(Integer, default=0, nullable=False)
    vehicle_number = Column(String, nullable=True)
    needs_room = Column(String, nullable=True)      # YES / NO
    aadhar_number = Column(String(12), nullable=True)
    room_type = Column(String, nullable=True)
    guest_qr_token = Column(String, unique=True, index=True, nullable=True)
    guest_qr_code_url = Column(String, nullable=True)
    status = Column(String, default="registered", nullable=False)

    event = relationship("Event", back_populates="guests")
    attendance = relationship("Attendance", back_populates="guest")
    sos = relationship("SOS", back_populates="guest")
    vehicle_details = relationship(
        "VehicleDetail",
        back_populates="guest",
        cascade="all, delete-orphan",
    )
    room_allocation = relationship(
        "RoomAllocation",
        back_populates="guest",
        uselist=False,
        cascade="all, delete-orphan",
    )
    

class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("guest_id", name="uq_attendance_guest_id"),
    )
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    guest_id = Column(Integer, ForeignKey("guests.id"))
    actual_people_count = Column(Integer, default=0)
    scanned_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="attendance")
    guest = relationship("Guest", back_populates="attendance")


class SOS(Base):
    __tablename__ = "sos"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    guest_id = Column(Integer, ForeignKey("guests.id"))
    reason = Column(String, nullable=False)
    triggered_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    resolved = Column(Boolean, default=False, nullable=False)

    event = relationship("Event", back_populates="sos")
    guest = relationship("Guest", back_populates="sos")


class VehicleDetail(Base):
    __tablename__ = "vehicle_details"

    id = Column(Integer, primary_key=True, index=True)
    guest_id = Column(Integer, ForeignKey("guests.id"), nullable=False, index=True)
    vehicle_type = Column(String, nullable=False)  # "car" or "bike"
    vehicle_number = Column(String, nullable=False)

    guest = relationship("Guest", back_populates="vehicle_details")


class RoomAllocation(Base):
    __tablename__ = "room_allocations"
    __table_args__ = (
        UniqueConstraint("guest_id", name="uq_room_allocations_guest_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    guest_id = Column(Integer, ForeignKey("guests.id"), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    hotel_name = Column(String, nullable=False)
    room_number = Column(String, nullable=False)
    allocated_at = Column(DateTime, default=datetime.utcnow)

    guest = relationship("Guest", back_populates="room_allocation")
    event = relationship("Event")


class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    event = relationship("Event", back_populates="announcements")
    organizer = relationship("User", back_populates="announcements")
