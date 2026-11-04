"""Seat counting, waitlist promotion and JSON helpers shared by the routers."""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from .models import Club, Event, Registration, utcnow
from .security import new_ticket_token


def confirmed_counts(db: DBSession, event_ids: list[int]) -> dict[int, dict[str, int]]:
    """Return {event_id: {"confirmed": n, "waitlisted": n}} from the registrations table."""
    counts = {eid: {"confirmed": 0, "waitlisted": 0} for eid in event_ids}
    if not event_ids:
        return counts
    rows = db.execute(
        select(Registration.event_id, Registration.status, func.count())
        .where(Registration.event_id.in_(event_ids),
               Registration.status.in_(["confirmed", "waitlisted"]))
        .group_by(Registration.event_id, Registration.status)
    ).all()
    for event_id, status, n in rows:
        counts[event_id][status] = n
    return counts


def lock_event(db: DBSession, event_id: int) -> Event | None:
    """Lock the event row so seat checks and updates happen one request at a time."""
    return db.execute(
        select(Event).where(Event.id == event_id).with_for_update()
    ).scalar_one_or_none()


def count_confirmed(db: DBSession, event_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(Registration)
        .where(Registration.event_id == event_id, Registration.status == "confirmed")
    )


def promote_waitlist(db: DBSession, event: Event) -> int:
    """Fill free seats from the waitlist in first-come order. Caller holds the event lock."""
    if event.status != "published" or utcnow() > event.registration_deadline:
        return 0
    db.flush()  # make the caller's pending changes (e.g. a cancellation) visible to the count
    free = event.capacity - count_confirmed(db, event.id)
    if free <= 0:
        return 0
    waiting = db.execute(
        select(Registration)
        .where(Registration.event_id == event.id, Registration.status == "waitlisted")
        .order_by(Registration.queued_at, Registration.id)
        .limit(free)
    ).scalars().all()
    for reg in waiting:
        reg.status = "confirmed"
        reg.ticket_token = new_ticket_token()
    return len(waiting)


def waitlist_position(db: DBSession, reg: Registration) -> int:
    ahead = db.scalar(
        select(func.count()).select_from(Registration).where(
            Registration.event_id == reg.event_id,
            Registration.status == "waitlisted",
            (Registration.queued_at < reg.queued_at)
            | ((Registration.queued_at == reg.queued_at) & (Registration.id < reg.id)),
        )
    )
    return ahead + 1


def phase(event: Event, now: datetime | None = None) -> str:
    now = now or utcnow()
    if event.status == "cancelled":
        return "cancelled"
    if now < event.starts_at:
        return "upcoming"
    if now <= event.ends_at:
        return "in_progress"
    return "past"


def availability(event: Event, confirmed: int) -> str:
    now = utcnow()
    if event.status == "cancelled":
        return "Cancelled"
    if now > event.ends_at:
        return "Ended"
    if now > event.registration_deadline:
        return "Registration closed"
    left = event.capacity - confirmed
    if left <= 0:
        return "Full · waitlist open"
    if left <= max(3, event.capacity // 10):
        return f"{left} seats left"
    return "Open"


def club_json(club: Club) -> dict:
    return {
        "id": club.id, "name": club.name, "short_name": club.short_name,
        "category": club.category, "description": club.description,
    }


def event_json(event: Event, counts: dict[str, int]) -> dict:
    confirmed = counts["confirmed"]
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "category": event.category,
        "venue": event.venue,
        "starts_at": event.starts_at.isoformat(),
        "ends_at": event.ends_at.isoformat(),
        "registration_deadline": event.registration_deadline.isoformat(),
        "capacity": event.capacity,
        "poster_style": event.poster_style,
        "status": event.status,
        "phase": phase(event),
        "confirmed": confirmed,
        "waitlisted": counts["waitlisted"],
        "seats_left": max(event.capacity - confirmed, 0),
        "availability": availability(event, confirmed),
        "club": {"id": event.club.id, "name": event.club.name, "short_name": event.club.short_name},
    }
