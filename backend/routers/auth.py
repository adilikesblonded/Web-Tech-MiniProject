from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..models import Club, Session, User
from ..schemas import LoginIn, SignupIn
from ..security import (
    COOKIE_NAME, SESSION_DAYS, create_session, current_user_optional, hash_password,
    hash_token, verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def set_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax",
        secure=request.url.scheme == "https", path="/",
    )


def user_json(db: DBSession, user: User) -> dict:
    owns_club = db.scalar(
        select(Club.id).where(Club.owner_id == user.id, Club.status == "approved").limit(1)
    )
    return {
        "id": user.id, "name": user.name, "email": user.email, "reg_no": user.reg_no,
        "is_admin": user.is_admin, "is_organizer": owns_club is not None,
    }


@router.post("/signup", status_code=201)
def signup(data: SignupIn, request: Request, response: Response, db: DBSession = Depends(get_db)):
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise HTTPException(409, "An account with this email already exists")
    if db.scalar(select(User.id).where(User.reg_no == data.reg_no)):
        raise HTTPException(409, "This registration number is already in use")
    user = User(name=data.name, email=data.email, reg_no=data.reg_no,
                password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    set_cookie(response, request, create_session(db, user))
    return user_json(db, user)


@router.post("/login")
def login(data: LoginIn, request: Request, response: Response, db: DBSession = Depends(get_db)):
    user = db.execute(
        select(User).where(User.email == data.email.strip().lower())
    ).scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    set_cookie(response, request, create_session(db, user))
    return user_json(db, user)


@router.post("/logout")
def logout(request: Request, response: Response, db: DBSession = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        session = db.execute(
            select(Session).where(Session.token_hash == hash_token(token))
        ).scalar_one_or_none()
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User | None = Depends(current_user_optional), db: DBSession = Depends(get_db)):
    return {"user": user_json(db, user) if user else None}
