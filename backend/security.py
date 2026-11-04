import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from .database import get_db
from .models import Club, Session, User, utcnow

COOKIE_NAME = "eventify_session"
SESSION_DAYS = 7
PBKDF2_ROUNDS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, rounds, salt, expected = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds))
    return hmac.compare_digest(digest.hex(), expected)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: DBSession, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(Session(user_id=user.id, token_hash=hash_token(token),
                   expires_at=utcnow() + timedelta(days=SESSION_DAYS)))
    db.commit()
    return token


def new_ticket_token() -> str:
    return secrets.token_urlsafe(18)


def current_user_optional(request: Request, db: DBSession = Depends(get_db)) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    session = db.execute(
        select(Session).where(Session.token_hash == hash_token(token))
    ).scalar_one_or_none()
    if not session or session.expires_at < utcnow():
        return None
    return session.user


def current_user(user: User | None = Depends(current_user_optional)) -> User:
    if user is None:
        raise HTTPException(401, "Please log in to continue")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Only the administrator can do this")
    return user


def owned_approved_club(db: DBSession, user: User, club_id: int) -> Club:
    club = db.get(Club, club_id)
    if not club or club.owner_id != user.id or club.status != "approved":
        raise HTTPException(403, "You can only manage events for your own approved clubs")
    return club
