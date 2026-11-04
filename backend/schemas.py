import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

CATEGORIES = ["Music", "Theatre", "Dance", "Photography", "Literary", "Technology", "Other"]
POSTER_STYLES = ["ember", "noir", "cobalt", "sage", "mustard", "mint", "terminal", "navy"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def clean(text: str) -> str:
    return " ".join(text.split())


class SignupIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=120)
    reg_no: str = Field(min_length=5, max_length=20)
    password: str = Field(min_length=8, max_length=100)

    @field_validator("name", "reg_no")
    @classmethod
    def strip_spaces(cls, v: str) -> str:
        return clean(v)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("reg_no")
    @classmethod
    def digits_only(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Registration number should contain digits only")
        return v


class LoginIn(BaseModel):
    email: str
    password: str


class ClubIn(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    short_name: str = Field(min_length=2, max_length=40)
    category: str
    description: str = Field(min_length=20, max_length=600)
    contact_email: str = Field(max_length=120)

    @field_validator("name", "short_name", "description")
    @classmethod
    def strip_spaces(cls, v: str) -> str:
        return clean(v)

    @field_validator("category")
    @classmethod
    def valid_category(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError("Choose a category from the list")
        return v

    @field_validator("contact_email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Enter a valid contact email")
        return v


class ReviewIn(BaseModel):
    decision: str
    note: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def check(self):
        if self.decision not in ("approved", "rejected"):
            raise ValueError("Decision must be approved or rejected")
        if self.decision == "rejected" and not (self.note and self.note.strip()):
            raise ValueError("Give a short reason when rejecting")
        return self


class EventIn(BaseModel):
    club_id: int
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=20, max_length=2000)
    category: str
    venue: str = Field(min_length=2, max_length=120)
    starts_at: datetime
    ends_at: datetime
    registration_deadline: datetime
    capacity: int = Field(gt=0, le=2000)
    poster_style: str = "ember"

    @field_validator("title", "venue")
    @classmethod
    def strip_spaces(cls, v: str) -> str:
        return clean(v)

    @field_validator("category")
    @classmethod
    def valid_category(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError("Choose a category from the list")
        return v

    @field_validator("poster_style")
    @classmethod
    def valid_style(cls, v: str) -> str:
        if v not in POSTER_STYLES:
            raise ValueError("Choose a poster style from the list")
        return v

    @field_validator("starts_at", "ends_at", "registration_deadline")
    @classmethod
    def needs_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Date and time must include a time zone")
        return v

    @model_validator(mode="after")
    def check_dates(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("End time must be after the start time")
        if self.registration_deadline > self.starts_at:
            raise ValueError("Registration must close before the event starts")
        return self


class RegisterIn(BaseModel):
    join_waitlist: bool = False


class CheckInIn(BaseModel):
    token: str = Field(min_length=10, max_length=64)

    @field_validator("token")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()
