"""Functional tests for the first interactive prototype."""

import sqlite3

from fastapi.testclient import TestClient

from app.db import database_path
from app.main import app


def test_public_catalog_and_search(monkeypatch, tmp_path):
    monkeypatch.setenv("NAVIGATOR_DB_PATH", str(tmp_path / "test.sqlite3"))
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/health").json() == {"status": "ok"}
        categories = client.get("/api/categories").json()
        assert len(categories) == 4
        articles = client.get("/api/articles").json()
        assert len(articles) == 6
        assert len(client.get("/api/articles", params={"q": "визиту"}).json()) >= 1
        assert len(client.get("/api/articles", params={"category": "support"}).json()) == 1
        assert len(client.get("/api/stages").json()) == 5
        assert client.get("/api/progress").status_code == 401
        with sqlite3.connect(database_path()) as db:
            db.execute("UPDATE articles SET status='draft' WHERE id=1")
        assert len(client.get("/api/articles").json()) == 5


def test_registration_login_progress_logout(monkeypatch, tmp_path):
    monkeypatch.setenv("NAVIGATOR_DB_PATH", str(tmp_path / "test.sqlite3"))
    with TestClient(app) as client:
        credentials = {"username": "demo_parent", "password": "SafePass123!"}
        register = client.post("/api/register", json=credentials)
        assert register.status_code == 201
        assert register.json()["user"]["role"] == "parent"
        assert client.get("/api/me").json()["user"]["username"] == "demo_parent"
        assert client.post("/api/register", json=credentials).status_code == 409
        assert client.put("/api/progress/1", json={"completed": True}).status_code == 200
        assert client.get("/api/progress").json() == {"completed": [1]}
        assert client.put("/api/progress/999", json={"completed": True}).status_code == 404
        with sqlite3.connect(database_path()) as db:
            password_hash = db.execute("SELECT password_hash FROM users LIMIT 1").fetchone()[0]
            assert "SafePass123!" not in password_hash
        assert client.post("/api/logout").status_code == 200
        assert client.get("/api/progress").status_code == 401
        assert client.post("/api/login", json={"username": "demo_parent", "password": "WrongPass99"}).status_code == 401
        assert client.post("/api/login", json=credentials).status_code == 200
        assert client.get("/api/progress").json() == {"completed": [1]}
        assert client.put("/api/progress/1", json={"completed": False}).status_code == 200
        assert client.get("/api/progress").json() == {"completed": []}


def test_invalid_registration(monkeypatch, tmp_path):
    monkeypatch.setenv("NAVIGATOR_DB_PATH", str(tmp_path / "test.sqlite3"))
    with TestClient(app) as client:
        assert client.post("/api/register", json={"username": "hi", "password": "123"}).status_code == 422
        assert client.get("/api/articles", params={"q": "x" * 101}).status_code == 422