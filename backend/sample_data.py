from database import SessionLocal, engine, Base
from models.models import User, Event
from utils import security
from datetime import datetime

# create tables
Base.metadata.create_all(bind=engine)


def create_sample():
    db = SessionLocal()
    try:
        # create a user
        # create user with hashed password; if hashing fails, store plain (not secure)
        try:
            pwd = security.get_password_hash("password")
        except Exception:
            pwd = "password"
        user = User(
            name="Organizer",
            email="organizer@example.com",
            password_hash=pwd,
            phone="1234567890",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        # create event
        import uuid
        from utils import qr as qrutil
        token = uuid.uuid4().hex
        qrimg = qrutil.generate_event_qr(token)
        event = Event(
            user_id=user.id,
            event_token=token,
            event_name="Sample Event",
            location="Park",
            expected_count=100,
            event_date=datetime.utcnow(),
            qr_code_url=qrimg,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        # add some guest RSVPs
        from random import randint, choice
        transports = ["car", "bus", "train", "foot"]
        for i in range(5):
            from models.models import Guest
            g = Guest(
                event_id=event.id,
                name=f"Guest{i}",
                phone="000",
                number_of_people=randint(1,4),
                transport_type=choice(transports),
                distance_km=randint(1,50),
                needs_room="yes" if randint(0,1) else "no",
                attendance_probability=randint(0,100)/100.0,
            )
            db.add(g)
        db.commit()
        print("Sample user and event created with id", event.id)
    finally:
        db.close()

if __name__ == "__main__":
    create_sample()

