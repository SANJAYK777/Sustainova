from collections import defaultdict

import anyio
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from dependencies.auth import get_current_user
from models.models import Announcement, Event, Guest
from schemas.schemas import AnnouncementCreate, AnnouncementOut
from utils.security import decode_access_token
from utils.phone import phone_candidates

router = APIRouter(prefix="/api/announcements", tags=["announcements"])
ws_router = APIRouter(tags=["announcements"])


class AnnouncementConnectionManager:
    def __init__(self):
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, event_id: int, websocket: WebSocket):
        await websocket.accept()
        self._connections[event_id].add(websocket)

    def disconnect(self, event_id: int, websocket: WebSocket):
        if event_id in self._connections and websocket in self._connections[event_id]:
            self._connections[event_id].remove(websocket)
            if not self._connections[event_id]:
                del self._connections[event_id]

    async def broadcast(self, event_id: int, payload: dict):
        dead_connections: list[WebSocket] = []
        for socket in self._connections.get(event_id, set()):
            try:
                await socket.send_json(payload)
            except Exception:
                dead_connections.append(socket)

        for socket in dead_connections:
            self.disconnect(event_id, socket)


manager = AnnouncementConnectionManager()


def _resolve_guest_for_token(db: Session, user_sub: str) -> Guest | None:
    guest = None
    if user_sub.isdigit():
        guest = db.query(Guest).filter(Guest.id == int(user_sub)).first()
    if guest:
        return guest

    candidates = phone_candidates(user_sub)
    return db.query(Guest).filter(Guest.phone.in_(candidates)).first()


@router.post("", response_model=AnnouncementOut)
def create_announcement(
    payload: AnnouncementCreate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.get("role") != "organizer":
        raise HTTPException(status_code=403, detail="Access forbidden")

    event = db.query(Event).filter(Event.id == payload.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.user_id != int(user.get("sub")):
        raise HTTPException(status_code=403, detail="Access forbidden")

    title = payload.title.strip()
    message = payload.message.strip()
    if not title or not message:
        raise HTTPException(status_code=422, detail="Title and message are required")

    row = Announcement(
        event_id=payload.event_id,
        title=title,
        message=message,
        created_by=int(user.get("sub")),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    ws_payload = {
        "type": "announcement_created",
        "announcement": {
            "id": row.id,
            "event_id": row.event_id,
            "title": row.title,
            "message": row.message,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "created_by": row.created_by,
        },
    }
    anyio.from_thread.run(manager.broadcast, payload.event_id, ws_payload)

    return row


@router.get("/{event_id}", response_model=list[AnnouncementOut])
def list_announcements(
    event_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    role = user.get("role")
    user_sub = str(user.get("sub") or "")

    if role == "organizer":
        if event.user_id != int(user_sub):
            raise HTTPException(status_code=403, detail="Access forbidden")
    elif role == "guest":
        guest = None
        if user_sub.isdigit():
            guest = db.query(Guest).filter(Guest.id == int(user_sub)).first()
        if not guest:
            candidates = phone_candidates(user_sub)
            guest = db.query(Guest).filter(Guest.phone.in_(candidates)).first()
        if not guest or guest.event_id != event_id:
            raise HTTPException(status_code=403, detail="Access forbidden")
    else:
        raise HTTPException(status_code=403, detail="Access forbidden")

    rows = (
        db.query(Announcement)
        .filter(Announcement.event_id == event_id)
        .order_by(Announcement.created_at.desc())
        .all()
    )
    return rows


@ws_router.websocket("/ws/announcements/{event_id}")
async def announcements_ws(
    websocket: WebSocket,
    event_id: int,
):
    token = websocket.query_params.get("token", "").strip()
    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=1008)
        return

    if payload.get("role") != "guest":
        await websocket.close(code=1008)
        return

    user_sub = str(payload.get("sub") or "")
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            await websocket.close(code=1008)
            return

        guest = _resolve_guest_for_token(db, user_sub)
        if not guest or guest.event_id != event_id:
            await websocket.close(code=1008)
            return
    finally:
        db.close()

    await manager.connect(event_id, websocket)
    try:
        while True:
            # Keep socket alive; clients are broadcast-only but this prevents disconnect loops.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(event_id, websocket)
    except Exception:
        manager.disconnect(event_id, websocket)
