"""Local-only authentication helpers, with PBKDF2 password hashes and opaque sessions."""

import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException

from .db import connect

ITERATIONS = 350_000
SESSION_LIFETIME = 60 * 60 * 24 * 7
COOKIE_NAME = "nd_session"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, count, salt, digest = stored.split("$")
        if algorithm != "pbkdf2_sha256" or int(count) < 100_000:
            return False
        computed = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(count))
        return hmac.compare_digest(computed, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (int(time.time()),))
        db.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (hashlib.sha256(token.encode()).hexdigest(), user_id, int(time.time()) + SESSION_LIFETIME),
        )
    return token


def session_user(token: str | None):
    if not token:
        return None
    with connect() as db:
        user = db.execute("""
            SELECT users.id, users.username, users.role
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ? AND sessions.expires_at > ?
        """, (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
        return dict(user) if user else None


def require_user(token: str | None):
    user = session_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Войдите в учётную запись")
    return user


def delete_session(token: str | None):
    if token:
        with connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))