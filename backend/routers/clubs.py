from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..models import Club, Event, User, utcnow
from ..schemas import ClubIn, ReviewIn
from ..security import current_user, require_admin
from ..services import club_json, confirmed_counts, event_json

router = APIRouter(prefix="/api", tags=["clubs"])


@router.get("/clubs")
def list_clubs(q: str = "", category: str = "", db: DBSession = Depends(get_db)):
    query = select(Club).where(Club.status == "approved").order_by(Club.name)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.where(or_(Club.name.ilike(like), Club.short_name.ilike(like),
                                Club.description.ilike(like)))
    if category:
        query = query.where(Club.category == category)
    clubs = db.execute(query).scalars().all()

    upcoming = dict(db.execute(
        select(Event.club_id, func.count())
        .where(Event.status == "published", Event.starts_at > utcnow())
        .group_by(Event.club_id)
    ).all())
    return [club_json(c) | {"upcoming_events": upcoming.get(c.id, 0)} for c in clubs]


@router.get("/clubs/{club_id}")
def get_club(club_id: int, db: DBSession = Depends(get_db)):
    club = db.get(Club, club_id)
    if not club or club.status != "approved":
        raise HTTPException(404, "Club not found")
    events = db.execute(
        select(Event).where(Event.club_id == club.id, Event.status == "published")
        .order_by(Event.starts_at)
    ).scalars().all()
    counts = confirmed_counts(db, [e.id for e in events])
    now = utcnow()
    items = [event_json(e, counts[e.id]) for e in events]
    return club_json(club) | {
        "upcoming": [e for e, ev in zip(items, events) if ev.ends_at >= now],
        "past": [e for e, ev in zip(items, events) if ev.ends_at < now][::-1],
    }


@router.post("/clubs", status_code=201)
def apply_for_club(data: ClubIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    duplicate = db.scalar(
        select(Club.id).where(
            func.lower(Club.name) == data.name.lower(), Club.status != "rejected"
        )
    )
    if duplicate:
        raise HTTPException(409, "A club with this name is already listed or under review")
    club = Club(**data.model_dump(), owner_id=user.id, status="pending")
    db.add(club)
    db.commit()
    return club_json(club) | {"status": club.status}


@router.get("/me/clubs")
def my_clubs(user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    clubs = db.execute(
        select(Club).where(Club.owner_id == user.id).order_by(Club.created_at.desc())
    ).scalars().all()
    return [club_json(c) | {"status": c.status, "review_note": c.review_note} for c in clubs]


@router.get("/admin/clubs")
def review_queue(status: str = "pending", _: User = Depends(require_admin),
                 db: DBSession = Depends(get_db)):
    clubs = db.execute(
        select(Club).where(Club.status == status).order_by(Club.created_at)
    ).scalars().all()
    return [
        club_json(c) | {
            "status": c.status, "review_note": c.review_note,
            "contact_email": c.contact_email, "created_at": c.created_at.isoformat(),
            "applicant": {"name": c.owner.name, "email": c.owner.email, "reg_no": c.owner.reg_no},
        }
        for c in clubs
    ]


@router.post("/admin/clubs/{club_id}/review")
def review_club(club_id: int, data: ReviewIn, _: User = Depends(require_admin),
                db: DBSession = Depends(get_db)):
    club = db.get(Club, club_id)
    if not club:
        raise HTTPException(404, "Club not found")
    if club.status != "pending":
        raise HTTPException(400, "This application has already been reviewed")
    club.status = data.decision
    club.review_note = data.note.strip() if data.note else None
    db.commit()
    return {"id": club.id, "status": club.status}
