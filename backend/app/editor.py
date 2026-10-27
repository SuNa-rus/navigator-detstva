"""Local MVP editorial workflow: server-enforced role permissions."""
from fastapi import APIRouter, Cookie, HTTPException
from pydantic import BaseModel, Field
from .auth import require_user
from .db import connect

router = APIRouter(prefix="/api/editor", tags=["Редакция"])
ROLES = {"parent", "medic", "editor", "admin"}


def initialize_editor():
    with connect() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(articles)")}
        if "author_id" not in columns:
            db.execute("ALTER TABLE articles ADD COLUMN author_id INTEGER REFERENCES users(id)")
        if "published_at" not in columns:
            db.execute("ALTER TABLE articles ADD COLUMN published_at TEXT")
        if "review_comment" not in columns:
            db.execute("ALTER TABLE articles ADD COLUMN review_comment TEXT")
        # Legacy published entries retain a stable order without altering their content.
        db.execute("""UPDATE articles SET published_at =
            printf('2000-01-01 00:00:%02d', id % 60)
            WHERE status = 'published' AND published_at IS NULL""")


def authorized(token, roles):
    user = require_user(token)
    if user["role"] not in roles:
        raise HTTPException(403, "Недостаточно прав")
    return user


class ReviewFeedback(BaseModel):
    comment: str = Field(min_length=5, max_length=1000)


class ArticleInput(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    category: str = Field(min_length=1, max_length=50)
    summary: str = Field(min_length=10, max_length=500)
    body: str = Field(min_length=20, max_length=20000)
    reading_minutes: int = Field(ge=1, le=120)


@router.get("/articles")
def list_editor_articles(nd_session: str | None = Cookie(default=None)):
    user = authorized(nd_session, {"editor", "medic", "admin"})
    with connect() as db:
        if user["role"] == "editor":
            rows = db.execute("""SELECT a.*, u.username AS author FROM articles a
                LEFT JOIN users u ON u.id=a.author_id
                WHERE a.author_id=? ORDER BY a.id DESC""", (user["id"],))
        else:
            rows = db.execute("""SELECT a.*, u.username AS author FROM articles a
                LEFT JOIN users u ON u.id=a.author_id ORDER BY a.id DESC""")
        return [dict(row) for row in rows]


@router.post("/articles", status_code=201)
def create_article(data: ArticleInput, nd_session: str | None = Cookie(default=None)):
    user = authorized(nd_session, {"editor", "admin"})
    with connect() as db:
        if not db.execute("SELECT 1 FROM categories WHERE slug=?", (data.category,)).fetchone():
            raise HTTPException(422, "Неизвестная категория")
        cur = db.execute("""INSERT INTO articles
            (title,category,summary,body,reading_minutes,status,author_id)
            VALUES (?,?,?,?,?,'draft',?)""",
            (data.title, data.category, data.summary, data.body, data.reading_minutes, user["id"]))
        return {"id": cur.lastrowid, "status": "draft"}


@router.put("/articles/{article_id}")
def edit_article(article_id: int, data: ArticleInput, nd_session: str | None = Cookie(default=None)):
    user = authorized(nd_session, {"editor", "admin"})
    with connect() as db:
        article = db.execute("SELECT author_id,status FROM articles WHERE id=?", (article_id,)).fetchone()
        if not article:
            raise HTTPException(404, "Материал не найден")
        if user["role"] != "admin" and (article["author_id"] != user["id"] or article["status"] != "draft"):
            raise HTTPException(403, "Редактировать можно только свои черновики")
        if not db.execute("SELECT 1 FROM categories WHERE slug=?", (data.category,)).fetchone():
            raise HTTPException(422, "Неизвестная категория")
        db.execute("""UPDATE articles SET title=?,category=?,summary=?,body=?,reading_minutes=?,
            status='draft',review_comment=NULL,published_at=NULL WHERE id=?""", (data.title,data.category,data.summary,data.body,data.reading_minutes,article_id))
        return {"id": article_id, "status": "draft"}


@router.post("/articles/{article_id}/submit")
def submit_article(article_id: int, nd_session: str | None = Cookie(default=None)):
    user = authorized(nd_session, {"editor", "admin"})
    with connect() as db:
        article = db.execute("SELECT author_id,status FROM articles WHERE id=?", (article_id,)).fetchone()
        if not article:
            raise HTTPException(404, "Материал не найден")
        if article["status"] != "draft" or (user["role"] != "admin" and article["author_id"] != user["id"]):
            raise HTTPException(403, "Отправить можно только свой черновик")
        db.execute("UPDATE articles SET status='review',review_comment=NULL WHERE id=?", (article_id,))
        return {"id": article_id, "status": "review"}


@router.post("/articles/{article_id}/publish")
def publish_article(article_id: int, nd_session: str | None = Cookie(default=None)):
    authorized(nd_session, {"medic", "admin"})
    with connect() as db:
        article = db.execute("SELECT status FROM articles WHERE id=?", (article_id,)).fetchone()
        if not article:
            raise HTTPException(404, "Материал не найден")
        if article["status"] != "review":
            raise HTTPException(409, "Публиковать можно только после отправки на проверку")
        db.execute("""UPDATE articles SET status='published',
            published_at=strftime('%Y-%m-%d %H:%M:%f','now'), review_comment=NULL
            WHERE id=?""", (article_id,))
        return {"id": article_id, "status": "published"}


@router.post("/articles/{article_id}/return")
def return_article(article_id: int, feedback: ReviewFeedback, nd_session: str | None = Cookie(default=None)):
    authorized(nd_session, {"medic", "admin"})
    with connect() as db:
        article = db.execute("SELECT status FROM articles WHERE id=?", (article_id,)).fetchone()
        if not article:
            raise HTTPException(404, "Материал не найден")
        if article["status"] != "review":
            raise HTTPException(409, "Вернуть можно только материал на проверке")
        db.execute("UPDATE articles SET status='draft',review_comment=? WHERE id=?", (feedback.comment, article_id))
    return {"id": article_id, "status": "draft"}
