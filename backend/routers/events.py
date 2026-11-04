from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..models import Club, Event, Registration, User, utcnow
from ..schemas import EventIn
from ..security import current_user, current_user_optional, owned_approved_club
from ..services import (
    confirmed_counts, count_confirmed, event_json, lock_event, promote_waitlist,
    waitlist_position,
)

router = APIRouter(prefix="/api", tags=["events"])
IST = timezone(timedelta(hours=5, minutes=30))


@router.get("/events")
def list_events(q: str = "", category: str = "", club_id: int | None = None,
                from_date: date | None = None, to_date: date | None = None,
                db: DBSession = Depends(get_db)):
    query = (
        select(Event).join(Club)
        .where(Event.status == "published", Club.status == "approved")
        .order_by(Event.starts_at)
    )
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.where(or_(Event.title.ilike(like), Event.description.ilike(like),
                                Club.name.ilike(like), Club.short_name.ilike(like)))
    if category:
        query = query.where(Event.category == category)
    if club_id:
        query = query.where(Event.club_id == club_id)
    if from_date:
        query = query.where(Event.starts_at >= datetime.combine(from_date, time.min, IST))
    else:
        query = query.where(Event.ends_at >= utcnow())
    if to_date:
        query = query.where(Event.starts_at < datetime.combine(to_date + timedelta(days=1), time.min, IST))
    events = db.execute(query).scalars().all()
    counts = confirmed_counts(db, [e.id for e in events])
    return [event_json(e, counts[e.id]) for e in events]


@router.get("/events/{event_id}")
def get_event(event_id: int, user: User | None = Depends(current_user_optional),
              db: DBSession = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event or event.club.status != "approved":
        raise HTTPException(404, "Event not found")
    mine = None
    if user:
        reg = db.execute(
            select(Registration).where(Registration.event_id == event.id,
                                       Registration.user_id == user.id)
        ).scalar_one_or_none()
        if reg and reg.status != "cancelled":
            mine = {"id": reg.id, "status": reg.status,
                    "checked_in": reg.checked_in_at is not None,
                    "position": waitlist_position(db, reg) if reg.status == "waitlisted" else None}
    # A cancelled event stays visible only to students who had registered for it.
    if event.status == "cancelled" and mine is None and not (user and event.club.owner_id == user.id):
        raise HTTPException(404, "Event not found")
    data = event_json(event, confirmed_counts(db, [event.id])[event.id])
    return data | {"my_registration": mine,
                   "is_owner": bool(user and event.club.owner_id == user.id)}


@router.get("/organizer/clubs")
def organizer_clubs(user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    clubs = db.execute(
        select(Club).where(Club.owner_id == user.id, Club.status == "approved").order_by(Club.name)
    ).scalars().all()
    return [{"id": c.id, "name": c.name, "short_name": c.short_name, "category": c.category}
            for c in clubs]


@router.get("/organizer/events")
def organizer_events(club_id: int, user: User = Depends(current_user),
                     db: DBSession = Depends(get_db)):
    owned_approved_club(db, user, club_id)
    events = db.execute(
        select(Event).where(Event.club_id == club_id).order_by(Event.starts_at.desc())
    ).scalars().all()
    counts = confirmed_counts(db, [e.id for e in events])
    return [event_json(e, counts[e.id]) for e in events]


@router.post("/events", status_code=201)
def create_event(data: EventIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    owned_approved_club(db, user, data.club_id)
    if data.starts_at <= utcnow():
        raise HTTPException(400, "The event must start in the future")
    event = Event(**data.model_dump(), status="published")
    db.add(event)
    db.commit()
    return event_json(event, {"confirmed": 0, "waitlisted": 0})


@router.put("/events/{event_id}")
def update_event(event_id: int, data: EventIn, user: User = Depends(current_user),
                 db: DBSession = Depends(get_db)):
    event = lock_event(db, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    owned_approved_club(db, user, event.club_id)
    if data.club_id != event.club_id:
        raise HTTPException(400, "An event cannot be moved to another club")
    if event.status == "cancelled":
        raise HTTPException(400, "Cancelled events cannot be edited")
    if utcnow() >= event.starts_at:
        raise HTTPException(400, "Events cannot be edited after they start")

    confirmed = count_confirmed(db, event.id)
    if data.capacity < confirmed:
        raise HTTPException(400, f"Capacity cannot be lower than the {confirmed} confirmed seats")
    has_registrations = db.scalar(
        select(Registration.id).where(Registration.event_id == event.id,
                                      Registration.status != "cancelled").limit(1)
    )
    times_changed = (data.starts_at != event.starts_at or data.ends_at != event.ends_at
                     or data.registration_deadline != event.registration_deadline)
    if has_registrations and times_changed:
        raise HTTPException(400, "Dates and times are fixed once students have registered")

    for field, value in data.model_dump(exclude={"club_id"}).items():
        setattr(event, field, value)
    promote_waitlist(db, event)  # a larger capacity frees seats for the waitlist
    db.commit()
    return event_json(event, confirmed_counts(db, [event.id])[event.id])


@router.post("/events/{event_id}/cancel")
def cancel_event(event_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    event = lock_event(db, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    owned_approved_club(db, user, event.club_id)
    if event.status == "cancelled":
        raise HTTPException(400, "This event is already cancelled")
    if utcnow() > event.ends_at:
        raise HTTPException(400, "Past events cannot be cancelled")
    event.status = "cancelled"
    db.commit()
    return {"id": event.id, "status": event.status}
