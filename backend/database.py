import logging
import os
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import settings

database_url = settings.DATABASE_URL
logger = logging.getLogger(__name__)

DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_CONNECT_RETRIES = int(os.getenv("DB_CONNECT_RETRIES", "10"))
DB_CONNECT_DELAY = float(os.getenv("DB_CONNECT_DELAY", "1.0"))


def _safe_database_target(url: str) -> str:
    if url.startswith("sqlite"):
        return url
    parsed = urlparse(url)
    host = parsed.hostname or "unknown-host"
    port = parsed.port or ""
    user = parsed.username or ""
    path = parsed.path or ""
    return f"{parsed.scheme}://{user}@{host}:{port}{path}"

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
    }
    engine_kwargs["pool_size"] = DB_POOL_SIZE
    engine_kwargs["max_overflow"] = DB_MAX_OVERFLOW

logger.info("Database target: %s", _safe_database_target(database_url))
engine = create_engine(database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# utility: wait until database is accepting connections
# utility: wait until database is accepting connections
import time
from uuid import uuid4
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import text

ALLOWED_SCHEMA_TABLES = {"events", "guests", "attendance", "sos", "vehicle_details"}


def _safe_table_name(table_name: str) -> str:
    if table_name not in ALLOWED_SCHEMA_TABLES:
        raise ValueError(f"Unsupported table name: {table_name}")
    return table_name


def _table_exists(connection, table_name: str) -> bool:
    table_name = _safe_table_name(table_name)
    dialect = connection.engine.dialect.name

    if dialect == "postgresql":
        exists = connection.execute(
            text("SELECT to_regclass(:table_name) IS NOT NULL"),
            {"table_name": table_name},
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

    # DO NOT raise OperationalError manually
    raise RuntimeError(f"Could not connect to database after {retries} attempts")


def ensure_runtime_schema():
    """
    Lightweight, idempotent schema sync for environments without migrations.
    Adds guest QR fields and attendance uniqueness if missing.
    """
    try:
        with engine.begin() as connection:
            if _table_exists(connection, "events"):
                existing_event_columns = _get_columns(connection, "events")
                event_statements = []
                if "latitude" not in existing_event_columns:
                    event_statements.append("ALTER TABLE events ADD COLUMN latitude FLOAT")
                if "longitude" not in existing_event_columns:
                    event_statements.append("ALTER TABLE events ADD COLUMN longitude FLOAT")
                for statement in event_statements:
                    connection.execute(text(statement))

            if _table_exists(connection, "guests"):
                existing_guest_columns = _get_columns(connection, "guests")
                statements = []
                if "guest_qr_token" not in existing_guest_columns:
                    statements.append("ALTER TABLE guests ADD COLUMN guest_qr_token VARCHAR")
                if "guest_qr_code_url" not in existing_guest_columns:
                    statements.append("ALTER TABLE guests ADD COLUMN guest_qr_code_url VARCHAR")
                if "coming_from" not in existing_guest_columns:
                    statements.append("ALTER TABLE guests ADD COLUMN coming_from TEXT")
                if "vehicle_number" not in existing_guest_columns:
                    statements.append("ALTER TABLE guests ADD COLUMN vehicle_number TEXT")
                if "car_count" not in existing_guest_columns:
                    statements.append("ALTER TABLE guests ADD COLUMN car_count INTEGER DEFAULT 0")
                if "bike_count" not in existing_guest_columns:
                    statements.append("ALTER TABLE guests ADD COLUMN bike_count INTEGER DEFAULT 0")
                if "aadhar_number" not in existing_guest_columns:
                    statements.append("ALTER TABLE guests ADD COLUMN aadhar_number VARCHAR(12)")
                if "room_type" not in existing_guest_columns:
                    statements.append("ALTER TABLE guests ADD COLUMN room_type TEXT")
                if "status" not in existing_guest_columns:
                    statements.append("ALTER TABLE guests ADD COLUMN status VARCHAR DEFAULT 'registered'")

                for statement in statements:
                    connection.execute(text(statement))

                connection.execute(
                    text("UPDATE guests SET status = 'registered' WHERE status IS NULL OR TRIM(status) = ''")
                )

                # Backfill historical rows that predate explicit parking counts.
                connection.execute(
                    text(
                        """
                        UPDATE guests
                        SET car_count = CASE
                            WHEN LOWER(COALESCE(parking_type, '')) IN ('car', 'car parking')
                                AND COALESCE(car_count, 0) = 0 THEN 1
                            ELSE COALESCE(car_count, 0)
                        END
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        UPDATE guests
                        SET bike_count = CASE
                            WHEN LOWER(COALESCE(parking_type, '')) IN ('bike', 'bike parking')
                                AND COALESCE(bike_count, 0) = 0 THEN 1
                            ELSE COALESCE(bike_count, 0)
                        END
                        """
                    )
                )

                # Keep existing rows valid with UUID tokens.
                guest_rows = connection.execute(
                    text("SELECT id FROM guests WHERE guest_qr_token IS NULL")
                ).fetchall()
                for row in guest_rows:
                    connection.execute(
                        text("UPDATE guests SET guest_qr_token = :token WHERE id = :guest_id"),
                        {"token": str(uuid4()), "guest_id": row[0]},
                    )

                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_guests_guest_qr_token ON guests (guest_qr_token)"
                    )
                )

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

            if not _table_exists(connection, "vehicle_details"):
                if connection.engine.dialect.name == "postgresql":
                    connection.execute(
                        text(
                            """
                            CREATE TABLE IF NOT EXISTS vehicle_details (
                                id SERIAL PRIMARY KEY,
                                guest_id INTEGER NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
                                vehicle_type VARCHAR NOT NULL,
                                vehicle_number VARCHAR NOT NULL
                            )
                            """
                        )
                    )
                    connection.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_vehicle_details_guest_id ON vehicle_details (guest_id)"
                        )
                    )
                    connection.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_vehicle_details_vehicle_type ON vehicle_details (vehicle_type)"
                        )
                    )
                elif connection.engine.dialect.name == "sqlite":
                    connection.execute(
                        text(
                            """
                            CREATE TABLE IF NOT EXISTS vehicle_details (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                guest_id INTEGER NOT NULL,
                                vehicle_type TEXT NOT NULL,
                                vehicle_number TEXT NOT NULL,
                                FOREIGN KEY (guest_id) REFERENCES guests(id) ON DELETE CASCADE
                            )
                            """
                        )
                    )
                    connection.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_vehicle_details_guest_id ON vehicle_details (guest_id)"
                        )
                    )
                    connection.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_vehicle_details_vehicle_type ON vehicle_details (vehicle_type)"
                        )
                    )

            if _table_exists(connection, "sos"):
                existing_sos_columns = _get_columns(connection, "sos")
                if "reason" not in existing_sos_columns:
                    connection.execute(text("ALTER TABLE sos ADD COLUMN reason TEXT"))
                connection.execute(
                    text("UPDATE sos SET reason = 'Emergency assistance needed' WHERE reason IS NULL")
                )
    except SQLAlchemyError as exc:
        print(f"Schema sync skipped due to database compatibility issue: {exc}")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
