from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .routers import auth, clubs, events, registrations

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="Eventify API", version="1.0")
Base.metadata.create_all(bind=engine)


@app.exception_handler(RequestValidationError)
async def friendly_validation_errors(_: Request, exc: RequestValidationError):
    """Turn Pydantic's error list into one readable message for the form."""
    first = exc.errors()[0]
    field = str(first["loc"][-1]).replace("_", " ") if first.get("loc") else "input"
    message = first["msg"].removeprefix("Value error, ")
    if first["type"] in ("string_too_short", "string_too_long", "missing", "greater_than"):
        message = f"{field.capitalize()}: {message.lower()}"
    return JSONResponse(status_code=422, content={"detail": message})


for module in (auth, clubs, events, registrations):
    app.include_router(module.router)

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
