"""Navigator detstva: local educational MVP API and web frontend."""

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Cookie, FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import COOKIE_NAME, SESSION_LIFETIME, create_session, delete_session, hash_password, require_user, session_user, verify_password
from .db import connect, initialize
from .editor import initialize_editor, router as editor_router

ROOT = Path(__file__).resolve().parents[2]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize()
    initialize_editor()
    yield


app = FastAPI(title="Навигатор детства", version="0.2.0", lifespan=lifespan)
app.mount("/assets", StaticFiles(directory=ROOT / "frontend" / "assets"), name="assets")


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=24, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)


class ProgressChange(BaseModel):
    completed: bool


def attach_session(response: Response, user_id: int):
    response.set_cookie(
        COOKIE_NAME, create_session(user_id), max_age=SESSION_LIFETIME,
        httponly=True, secure=False, samesite="lax", path="/",
    )


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(ROOT / "frontend" / "index.html")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/categories")
def categories():
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT slug, title, icon FROM categories ORDER BY rowid")]


@app.get("/api/articles")
def articles(q: str = Query(default="", max_length=100), category: str = Query(default="", max_length=50)):
    with connect() as db:
        return [dict(r) for r in db.execute("""
            SELECT a.id, a.title, a.category, c.title AS category_title,
                   a.summary, a.body, a.reading_minutes
            FROM articles a JOIN categories c ON c.slug = a.category
            WHERE a.status = 'published'
              AND (? = '' OR a.category = ?)
              AND (? = '' OR a.title LIKE ? OR a.summary LIKE ?)
            ORDER BY COALESCE(a.published_at, '2000-01-01 00:00:00') DESC, a.id DESC
        """, (category, category, q, f"%{q}%", f"%{q}%"))]


@app.get("/api/stages")
def stages():
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT id, title, age, description FROM stages ORDER BY id")]


@app.get("/api/me")
def me(nd_session: str | None = Cookie(default=None)):
    return {"user": session_user(nd_session)}


@app.post("/api/register", status_code=201)
def register(payload: Credentials, response: Response):
    try:
        with connect() as db:
            cursor = db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'parent')",
                (payload.username.lower(), hash_password(payload.password)),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Такой логин уже занят") from None
    attach_session(response, user_id)
    return {"user": {"id": user_id, "username": payload.username.lower(), "role": "parent"}}


@app.post("/api/login")
def login(payload: Credentials, response: Response):
    with connect() as db:
        user = db.execute("SELECT id, username, role, password_hash FROM users WHERE username = ?", (payload.username,)).fetchone()
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    attach_session(response, user["id"])
    return {"user": {"id": user["id"], "username": user["username"], "role": user["role"]}}


@app.post("/api/logout")
def logout(response: Response, nd_session: str | None = Cookie(default=None)):
    delete_session(nd_session)
    response.delete_cookie(COOKIE_NAME, path="/", samesite="lax")
    return {"ok": True}


@app.get("/api/progress")
def get_progress(nd_session: str | None = Cookie(default=None)):
    user = require_user(nd_session)
    with connect() as db:
        rows = db.execute("SELECT stage_id FROM progress WHERE user_id = ? ORDER BY stage_id", (user["id"],))
        return {"completed": [r["stage_id"] for r in rows]}


@app.put("/api/progress/{stage_id}")
def set_progress(stage_id: int, payload: ProgressChange, nd_session: str | None = Cookie(default=None)):
    user = require_user(nd_session)
    with connect() as db:
        exists = db.execute("SELECT 1 FROM stages WHERE id = ?", (stage_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Раздел маршрута не найден")
        if payload.completed:
            db.execute("INSERT OR IGNORE INTO progress (user_id, stage_id) VALUES (?, ?)", (user["id"], stage_id))
        else:
            db.execute("DELETE FROM progress WHERE user_id = ? AND stage_id = ?", (user["id"], stage_id))
    return {"ok": True, "stage_id": stage_id, "completed": payload.completed}
app.include_router(editor_router)
