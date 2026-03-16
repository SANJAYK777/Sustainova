import logging
import os
import time
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import settings

# -------------------
# Configuration
# -------------------
database_url = settings.DATABASE_URL
logger = logging.getLogger(__name__)

DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_CONNECT_RETRIES = int(os.getenv("DB_CONNECT_RETRIES", "10"))
DB_CONNECT_DELAY = float(os.getenv("DB_CONNECT_DELAY", "1.0"))

ALLOWED_SCHEMA_TABLES = {
    "events", "guests", "attendance", "sos", "vehicle_details", "room_allocations"
}

# -------------------
# Safe DB URL
# -------------------
def _safe_database_target(url: str) -> str:
    """
    Returns a safe version of the database URL for logging without crashing on hostnames.
    Handles SQLite, Postgres, and hostnames.
    """
    if url.startswith("sqlite"):
        return url
    parsed = urlparse(url)
    host = parsed.hostname or "unknown-host"
    port = parsed.port or ""
    user = parsed.username or ""
    path = parsed.path or ""
    # Skip IP parsing; Supabase hostnames will fail ipaddress.ip_address()
    return f"{parsed.scheme}://{user}@{host}:{port}{path}"

logger.info("Database target: %s", _safe_database_target(database_url))

# -------------------
# SQLAlchemy Engine
# -------------------
engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

if database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_use_lifo"] = True
    engine_kwargs["connect_args"] = {
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
        "connect_timeout": DB_CONNECT_TIMEOUT,
        "sslmode": "require",  # <-- add this line
    }
    engine_kwargs["pool_size"] = DB_POOL_SIZE
    engine_kwargs["max_overflow"] = DB_MAX_OVERFLOW

engine = create_engine(database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# -------------------
# Helper Functions
# -------------------
def _safe_table_name(table_name: str) -> str:
    if table_name not in ALLOWED_SCHEMA_TABLES:
        raise ValueError(f"Unsupported table name: {table_name}")
    return table_name

def _table_exists(connection, table_name: str) -> bool:
    table_name = _safe_table_name(table_name)
    dialect = connection.engine.dialect.name

    if dialect == "postgresql":
        exists = connection.execute(
            text("SELECT to_regclass(:table_name) IS NOT NULL"), {"table_name": table_name}
        ).scalar()
        return bool(exists)

    if dialect == "sqlite":
        exists = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name"),
            {"table_name": table_name},
        ).scalar()
        return exists is not None

    return False

def _get_columns(connection, table_name: str) -> set[str]:
    table_name = _safe_table_name(table_name)
    dialect = connection.engine.dialect.name

    if dialect == "postgresql":
        rows = connection.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = :table_name
                """
            ),
            {"table_name": table_name},
        ).fetchall()
        return {row[0] for row in rows}

    if dialect == "sqlite":
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return {row[1] for row in rows}

    return set()

# -------------------
# Wait for DB
# -------------------
def wait_for_db(retries: int | None = None, delay: float | None = None):
    """Block until the database is ready or raise after retries."""
    if retries is None:
        retries = DB_CONNECT_RETRIES
    if delay is None:
        delay = DB_CONNECT_DELAY
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

    raise RuntimeError(f"Could not connect to database after {retries} attempts")

# -------------------
# Ensure Schema
# -------------------
def ensure_runtime_schema():
    """
    Lightweight, idempotent schema sync for environments without migrations.
    Adds missing columns, indices, and tables if necessary.
    """
    try:
        with engine.begin() as connection:
            # Events table
            if _table_exists(connection, "events"):
                existing_event_columns = _get_columns(connection, "events")
                event_statements = []
                if "latitude" not in existing_event_columns:
                    event_statements.append("ALTER TABLE events ADD COLUMN latitude FLOAT")
                if "longitude" not in existing_event_columns:
                    event_statements.append("ALTER TABLE events ADD COLUMN longitude FLOAT")
                for statement in event_statements:
                    connection.execute(text(statement))

            # Guests table
            if _table_exists(connection, "guests"):
                existing_guest_columns = _get_columns(connection, "guests")
                statements = []
                guest_columns_to_add = {
                    "guest_qr_token": "VARCHAR",
                    "guest_qr_code_url": "VARCHAR",
                    "coming_from": "TEXT",
                    "vehicle_number": "TEXT",
                    "car_count": "INTEGER DEFAULT 0",
                    "bike_count": "INTEGER DEFAULT 0",
                    "aadhar_number": "VARCHAR(12)",
                    "room_type": "TEXT",
                    "status": "VARCHAR DEFAULT 'registered'",
                }
                for col, typ in guest_columns_to_add.items():
                    if col not in existing_guest_columns:
                        statements.append(f"ALTER TABLE guests ADD COLUMN {col} {typ}")
                for statement in statements:
                    connection.execute(text(statement))

                # Backfill UUID tokens
                guest_rows = connection.execute(
                    text("SELECT id FROM guests WHERE guest_qr_token IS NULL")
                ).fetchall()
                for row in guest_rows:
                    connection.execute(
                        text("UPDATE guests SET guest_qr_token = :token WHERE id = :guest_id"),
                        {"token": str(uuid4()), "guest_id": row[0]},
                    )

                connection.execute(
                    text("CREATE UNIQUE INDEX IF NOT EXISTS ix_guests_guest_qr_token ON guests (guest_qr_token)")
                )

            # Attendance table
            if _table_exists(connection, "attendance"):
                connection.execute(
                    text(
                        "DELETE FROM attendance WHERE id NOT IN (SELECT MIN(id) FROM attendance GROUP BY guest_id)"
                    )
                )
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_guest_id ON attendance (guest_id)"
                    )
                )

            # Vehicle and Room tables creation handled here for Postgres and SQLite
            for table_name, table_sql_list in {
                "vehicle_details": [
                    """
                    CREATE TABLE IF NOT EXISTS vehicle_details (
                        id SERIAL PRIMARY KEY,
                        guest_id INTEGER NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
                        vehicle_type VARCHAR NOT NULL,
                        vehicle_number VARCHAR NOT NULL
                    )
                    """,
                    "CREATE INDEX IF NOT EXISTS ix_vehicle_details_guest_id ON vehicle_details (guest_id)",
                    "CREATE INDEX IF NOT EXISTS ix_vehicle_details_vehicle_type ON vehicle_details (vehicle_type)",
                ],
                "room_allocations": [
                    """
                    CREATE TABLE IF NOT EXISTS room_allocations (
                        id SERIAL PRIMARY KEY,
                        guest_id INTEGER NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
                        event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                        hotel_name VARCHAR NOT NULL,
                        room_number VARCHAR NOT NULL,
                        allocated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                        CONSTRAINT uq_room_allocations_guest_id UNIQUE (guest_id)
                    )
                    """,
                    "CREATE INDEX IF NOT EXISTS ix_room_allocations_event_id ON room_allocations (event_id)",
                ],
            }.items():
                if not _table_exists(connection, table_name) and connection.engine.dialect.name == "postgresql":
                    for sql in table_sql_list:
                        connection.execute(text(sql))

            # SOS table
            if _table_exists(connection, "sos"):
                existing_sos_columns = _get_columns(connection, "sos")
                if "reason" not in existing_sos_columns:
                    connection.execute(text("ALTER TABLE sos ADD COLUMN reason TEXT"))
                connection.execute(text("UPDATE sos SET reason = 'Emergency assistance needed' WHERE reason IS NULL"))

    except SQLAlchemyError as exc:
        print(f"Schema sync skipped due to database compatibility issue: {exc}")

# -------------------
# Dependency
# -------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
