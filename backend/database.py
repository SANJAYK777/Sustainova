from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import settings

engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# utility: wait until database is accepting connections
# utility: wait until database is accepting connections
import time
from uuid import uuid4
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

def wait_for_db(retries: int = 10, delay: float = 1.0):
    """Block until the database is ready or raise after retries."""
    attempt = 0
    while attempt < retries:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("Database ready.")
            return
        except OperationalError:
            attempt += 1
            print(f"Database not ready. Retrying {attempt}/{retries}...")
            time.sleep(delay)

    # DO NOT raise OperationalError manually
    raise RuntimeError(f"Could not connect to database after {retries} attempts")


def ensure_runtime_schema():
    """
    Lightweight, idempotent schema sync for environments without migrations.
    Adds guest QR fields and attendance uniqueness if missing.
    """
    inspector = inspect(engine)
    if inspector.has_table("events"):
        existing_event_columns = {col["name"] for col in inspector.get_columns("events")}
        event_statements = []
        if "latitude" not in existing_event_columns:
            event_statements.append("ALTER TABLE events ADD COLUMN latitude FLOAT")
        if "longitude" not in existing_event_columns:
            event_statements.append("ALTER TABLE events ADD COLUMN longitude FLOAT")
        if event_statements:
            with engine.begin() as connection:
                for statement in event_statements:
                    connection.execute(text(statement))

    if inspector.has_table("guests"):
        existing_guest_columns = {col["name"] for col in inspector.get_columns("guests")}
        statements = []
        if "guest_qr_token" not in existing_guest_columns:
            statements.append("ALTER TABLE guests ADD COLUMN guest_qr_token VARCHAR")
        if "guest_qr_code_url" not in existing_guest_columns:
            statements.append("ALTER TABLE guests ADD COLUMN guest_qr_code_url VARCHAR")

        if statements:
            with engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))

        # Keep existing rows valid with UUID tokens.
        with engine.begin() as connection:
            guest_rows = connection.execute(
                text("SELECT id FROM guests WHERE guest_qr_token IS NULL")
            ).fetchall()
            for row in guest_rows:
                connection.execute(
                    text("UPDATE guests SET guest_qr_token = :token WHERE id = :guest_id"),
                    {"token": str(uuid4()), "guest_id": row[0]},
                )

        guest_indexes = {idx["name"] for idx in inspector.get_indexes("guests")}
        if "ix_guests_guest_qr_token" not in guest_indexes:
            with engine.begin() as connection:
                connection.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_guests_guest_qr_token ON guests (guest_qr_token)"
                ))

    if inspector.has_table("attendance"):
        with engine.begin() as connection:
            connection.execute(text(
                "DELETE FROM attendance WHERE id NOT IN (SELECT MIN(id) FROM attendance GROUP BY guest_id)"
            ))

        attendance_indexes = {idx["name"] for idx in inspector.get_indexes("attendance")}
        if "uq_attendance_guest_id" not in attendance_indexes:
            with engine.begin() as connection:
                connection.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_guest_id ON attendance (guest_id)"
                ))

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
