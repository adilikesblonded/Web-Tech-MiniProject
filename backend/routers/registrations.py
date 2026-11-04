import io
from datetime import timedelta

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..models import Event, Registration, User, utcnow
from ..schemas import CheckInIn, RegisterIn
from ..security import current_user, new_ticket_token, owned_approved_club
from ..services import (
    confirmed_counts, count_confirmed, event_json, lock_event, promote_waitlist,
    waitlist_position,
)

router = APIRouter(prefix="/api", tags=["registrations"])

CHECKIN_OPENS_BEFORE = timedelta(minutes=30)
CHECKIN_CLOSES_AFTER = timedelta(hours=2)


@router.post("/events/{event_id}/registrations")
def register(event_id: int, data: RegisterIn, user: User = Depends(current_user),
             db: DBSession = Depends(get_db)):
    event = lock_event(db, event_id)  # held until commit, so two requests cannot take one seat
    if not event or event.status != "published" or event.club.status != "approved":
        raise HTTPException(404, "This event is not open for registration")
    if utcnow() > event.registration_deadline:
        raise HTTPException(400, "Registration for this event has closed")

    reg = db.execute(
        select(Registration).where(Registration.event_id == event.id,
                                   Registration.user_id == user.id)
    ).scalar_one_or_none()
    if reg and reg.status in ("confirmed", "waitlisted"):
        db.rollback()
        return {"status": reg.status, "message": "You are already registered for this event"}

    if count_confirmed(db, event.id) < event.capacity:
        status, token = "confirmed", new_ticket_token()
    elif data.join_waitlist:
        status, token = "waitlisted", None
    else:
        db.rollback()
        return JSONResponse(status_code=409, content={
            "detail": "All seats are taken. You can join the waitlist instead.", "code": "full"})

    if reg:  # re-registering after a cancellation goes to the back of the queue
        reg.status, reg.ticket_token, reg.queued_at = status, token, utcnow()
        reg.checked_in_at = reg.checked_in_by = None
    else:
        reg = Registration(event_id=event.id, user_id=user.id, status=status, ticket_token=token)
        db.add(reg)
    db.commit()
    result = {"status": reg.status}
    if reg.status == "waitlisted":
        result["position"] = waitlist_position(db, reg)
    return result


@router.delete("/events/{event_id}/registrations/me")
def cancel_registration(event_id: int, user: User = Depends(current_user),
                        db: DBSession = Depends(get_db)):
    event = lock_event(db, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    reg = db.execute(
        select(Registration).where(Registration.event_id == event.id,
                                   Registration.user_id == user.id)
    ).scalar_one_or_none()
    if not reg or reg.status == "cancelled":
        raise HTTPException(404, "You do not have a registration for this event")
    if reg.checked_in_at:
        raise HTTPException(400, "You have already checked in to this event")
    if utcnow() >= event.starts_at:
        raise HTTPException(400, "Registrations cannot be cancelled after the event starts")

    was_confirmed = reg.status == "confirmed"
    reg.status, reg.ticket_token = "cancelled", None
    promoted = promote_waitlist(db, event) if was_confirmed else 0
    db.commit()
    return {"status": "cancelled", "promoted": promoted}


@router.get("/me/registrations")
def my_registrations(user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    regs = db.execute(
        select(Registration).join(Event)
        .where(Registration.user_id == user.id, Registration.status != "cancelled")
        .order_by(Event.starts_at)
    ).scalars().all()
    counts = confirmed_counts(db, [r.event_id for r in regs])
    now = utcnow()
    items = []
    for r in regs:
        closed = now > r.event.registration_deadline
        items.append({
            "id": r.id,
            "status": r.status,
            "position": waitlist_position(db, r) if r.status == "waitlisted" and not closed else None,
            "waitlist_closed": r.status == "waitlisted" and closed,
            "checked_in_at": r.checked_in_at.isoformat() if r.checked_in_at else None,
            "event": event_json(r.event, counts[r.event_id]),
        })
    return items


def own_active_ticket(db: DBSession, user: User, reg_id: int) -> Registration:
    reg = db.get(Registration, reg_id)
    if not reg or reg.user_id != user.id:
        raise HTTPException(404, "Ticket not found")
    if reg.status != "confirmed" or not reg.ticket_token or reg.event.status != "published":
        raise HTTPException(400, "Only confirmed registrations have a ticket")
    return reg


@router.get("/registrations/{reg_id}/ticket")
def ticket(reg_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    reg = own_active_ticket(db, user, reg_id)
    return {"token": reg.ticket_token, "event_title": reg.event.title,
            "name": user.name, "reg_no": user.reg_no,
            "checked_in": reg.checked_in_at is not None}


@router.get("/registrations/{reg_id}/qr.svg")
def ticket_qr(reg_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    reg = own_active_ticket(db, user, reg_id)
    image = qrcode.make(reg.ticket_token, image_factory=qrcode.image.svg.SvgPathImage, border=2)
    buffer = io.BytesIO()
    image.save(buffer)
    return Response(buffer.getvalue(), media_type="image/svg+xml",
                    headers={"Cache-Control": "no-store"})


@router.get("/events/{event_id}/participants")
def participants(event_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    owned_approved_club(db, user, event.club_id)
    regs = db.execute(
        select(Registration).where(Registration.event_id == event.id,
                                   Registration.status != "cancelled")
        .order_by(Registration.status, Registration.queued_at, Registration.id)
    ).scalars().all()
    confirmed = [r for r in regs if r.status == "confirmed"]
    checked_in = sum(1 for r in confirmed if r.checked_in_at)
    position = 0
    rows = []
    for r in regs:
        if r.status == "waitlisted":
            position += 1
        rows.append({
            "name": r.user.name, "email": r.user.email, "reg_no": r.user.reg_no,
            "status": r.status, "position": position if r.status == "waitlisted" else None,
            "checked_in_at": r.checked_in_at.isoformat() if r.checked_in_at else None,
        })
    counts = confirmed_counts(db, [event.id])[event.id]
    return {
        "event": event_json(event, counts),
        "summary": {
            "confirmed": len(confirmed),
            "waitlisted": counts["waitlisted"],
            "checked_in": checked_in,
            "seats_left": max(event.capacity - len(confirmed), 0),
            "attendance_pct": round(100 * checked_in / len(confirmed)) if confirmed else 0,
        },
        "participants": rows,
    }


@router.post("/events/{event_id}/check-in")
def check_in(event_id: int, data: CheckInIn, user: User = Depends(current_user),
             db: DBSession = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    owned_approved_club(db, user, event.club_id)
    if event.status == "cancelled":
        raise HTTPException(400, "This event was cancelled")
    now = utcnow()
    if now < event.starts_at - CHECKIN_OPENS_BEFORE:
        raise HTTPException(400, "Check-in opens 30 minutes before the event starts")
    if now > event.ends_at + CHECKIN_CLOSES_AFTER:
        raise HTTPException(400, "Check-in for this event has closed")

    reg = db.execute(
        select(Registration).where(Registration.ticket_token == data.token)
    ).scalar_one_or_none()
    if not reg or reg.event_id != event.id:
        raise HTTPException(404, "This ticket is not valid for this event")
    if reg.status != "confirmed":
        raise HTTPException(400, "This ticket is not confirmed")

    # Only the first scan updates the row, so a ticket is never counted twice.
    result = db.execute(
        update(Registration)
        .where(Registration.id == reg.id, Registration.checked_in_at.is_(None))
        .values(checked_in_at=now, checked_in_by=user.id)
    )
    db.commit()
    if result.rowcount == 0:
        return {"result": "already", "name": reg.user.name, "reg_no": reg.user.reg_no}
    return {"result": "checked_in", "name": reg.user.name, "reg_no": reg.user.reg_no}
