import base64
import json
import re
from datetime import datetime, timezone
from typing import Optional

import urllib.error
import urllib.request

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator
import sqlite3

from .config import MINIMOTH_API_KEY, MINIMOTH_BASE_URL
from .database import get_db, init_db

app = FastAPI(title="Daily Journal API")


class SendOtpRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) == 10 and digits[0] in "6789":
            return f"+91{digits}"
        if re.fullmatch(r"\+91[6-9]\d{9}", value):
            return value
        raise ValueError("Enter a valid Indian 10-digit mobile number")


class VerifyOtpRequest(BaseModel):
    phone: str
    code: str = Field(min_length=6, max_length=6)
    name: Optional[str] = Field(default=None, max_length=50)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("OTP must contain 6 digits")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) == 10 and digits[0] in "6789":
            return f"+91{digits}"
        if re.fullmatch(r"\+91[6-9]\d{9}", value):
            return value
        raise ValueError("Enter a valid Indian 10-digit mobile number")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must be at least 2 characters")
        return value


class EntryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=5000)

    @field_validator("title", "content")
    @classmethod
    def trim_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty")
        return value


class EntryUpdate(EntryCreate):
    pass


def minimoth_request(path: str, method: str, payload: Optional[dict] = None):
    if not MINIMOTH_API_KEY:
        raise HTTPException(500, "MINIMOTH_API_KEY is missing in backend .env")

    body = None
    headers = {
        "X-Api-Key": MINIMOTH_API_KEY,
        "Content-Type": "application/json",
        "User-Agent": "DailyJournal/1.0 (FastAPI/Backend)",
    }
    if payload is not None:
        body = json.dumps(payload).encode()

    request = urllib.request.Request(
        f"{MINIMOTH_BASE_URL}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raw_body = ""
        try:
            raw_body = exc.read().decode()
            detail = json.loads(raw_body)
            message = detail.get("message") or detail.get("error") or raw_body
        except Exception:
            message = raw_body or "MiniMoth request failed"
        raise HTTPException(exc.code, message)
    except urllib.error.URLError:
        raise HTTPException(503, "MiniMoth is temporarily unreachable")


def decode_jwt_payload(token: str) -> dict:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid access token")


def current_user(authorization: Optional[str], db: sqlite3.Connection):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_jwt_payload(token)
    session_id = payload.get("session_id") or payload.get("sid")
    if not session_id:
        raise HTTPException(status_code=401, detail="Invalid session")

    minimoth_request("/v1/session/validate", "POST", {"access_token": token})
    user = db.execute("SELECT * FROM users WHERE session_id = ?", (session_id,)).fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="Session is not linked to a journal user")
    return user


@app.on_event("startup")
def startup():
    init_db()


@app.post("/api/auth/send-otp")
def send_otp(request: SendOtpRequest):
    _, data = minimoth_request("/v1/otp/send", "POST", {"phone": request.phone})
    return {"message": "OTP sent", "otp_id": data.get("otp_id"), "expires_at": data.get("expires_at")}


@app.post("/api/auth/verify-otp")
def verify_otp(request: VerifyOtpRequest, db: sqlite3.Connection = Depends(get_db)):
    _, data = minimoth_request(
        "/v1/otp/verify",
        "POST",
        {"phone": request.phone, "code": request.code},
    )

    access_token = data.get("access_token")
    identity_id = data.get("identity_id")
    if not access_token or not identity_id:
        raise HTTPException(502, "MiniMoth returned an incomplete verification response")

    payload = decode_jwt_payload(access_token)
    session_id = payload.get("session_id") or payload.get("sid")
    if not session_id:
        raise HTTPException(502, "MiniMoth token did not include a session id")

    existing = db.execute("SELECT id, name FROM users WHERE phone = ?", (request.phone,)).fetchone()
    if existing:
        db.execute(
            "UPDATE users SET identity_id = ?, session_id = ? WHERE id = ?",
            (identity_id, session_id, existing["id"]),
        )
        user_name = existing["name"]
    else:
        name = (request.name or "Journalist").strip()
        db.execute(
            "INSERT INTO users (phone, name, identity_id, session_id) VALUES (?, ?, ?, ?)",
            (request.phone, name, identity_id, session_id),
        )
        user_name = name
    db.commit()

    return {
        "message": "Login successful",
        "access_token": access_token,
        "expires_at": data.get("expires_at"),
        "user": {"name": user_name, "phone": request.phone},
    }


@app.get("/api/entries")
def list_entries(
    authorization: Optional[str] = Header(default=None),
    db: sqlite3.Connection = Depends(get_db),
):
    user = current_user(authorization, db)
    rows = db.execute(
        "SELECT id, title, content, created_at, updated_at FROM journal_entries WHERE user_id = ? ORDER BY updated_at DESC",
        (user["id"],),
    ).fetchall()
    return {"user": {"name": user["name"], "phone": user["phone"]}, "entries": [dict(row) for row in rows]}


@app.post("/api/entries")
def create_entry(
    entry: EntryCreate,
    authorization: Optional[str] = Header(default=None),
    db: sqlite3.Connection = Depends(get_db),
):
    user = current_user(authorization, db)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cursor = db.execute(
        "INSERT INTO journal_entries (user_id, title, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (user["id"], entry.title, entry.content, now, now),
    )
    db.commit()
    row = db.execute("SELECT id, title, content, created_at, updated_at FROM journal_entries WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


@app.put("/api/entries/{entry_id}")
def update_entry(
    entry_id: int,
    entry: EntryUpdate,
    authorization: Optional[str] = Header(default=None),
    db: sqlite3.Connection = Depends(get_db),
):
    user = current_user(authorization, db)
    existing = db.execute(
        "SELECT id FROM journal_entries WHERE id = ? AND user_id = ?",
        (entry_id, user["id"]),
    ).fetchone()
    if not existing:
        raise HTTPException(404, "Journal entry not found")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db.execute(
        "UPDATE journal_entries SET title = ?, content = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (entry.title, entry.content, now, entry_id, user["id"]),
    )
    db.commit()
    row = db.execute("SELECT id, title, content, created_at, updated_at FROM journal_entries WHERE id = ?", (entry_id,)).fetchone()
    return dict(row)
