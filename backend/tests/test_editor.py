"""Editorial workflow and permission tests; uses isolated temporary DB."""
from fastapi.testclient import TestClient
from app.main import app
from app.db import connect

PAYLOAD = {
    "title": "Демонстрационная памятка для родителей",
    "category": "support",
    "summary": "Подготовка к разговору со специалистом в учебной версии.",
    "body": "Этот учебный материал показывает согласование и публикацию. Не является медицинской рекомендацией.",
    "reading_minutes": 2,
}


def make_user(client, name, role):
    assert client.post("/api/register", json={"username": name, "password": "Password987!"}).status_code == 201
    with connect() as db:
        db.execute("UPDATE users SET role=? WHERE username=?", (role, name))
    assert client.post("/api/login", json={"username": name, "password": "Password987!"}).status_code == 200


def test_roles_article_workflow(monkeypatch, tmp_path):
    monkeypatch.setenv("NAVIGATOR_DB_PATH", str(tmp_path / "workflow.sqlite3"))
    with TestClient(app) as client:
        make_user(client, "parent1", "parent")
        assert client.post("/api/editor/articles", json=PAYLOAD).status_code == 403
        assert client.get("/api/editor/articles").status_code == 403
        make_user(client, "editor1", "editor")
        response = client.post("/api/editor/articles", json=PAYLOAD)
        assert response.status_code == 201, response.text
        article_id = response.json()["id"]
        assert response.json()["status"] == "draft"
        assert client.post(f"/api/editor/articles/{article_id}/publish").status_code == 403
        assert client.put(f"/api/editor/articles/{article_id}", json=PAYLOAD).status_code == 200
        assert client.post(f"/api/editor/articles/{article_id}/submit").status_code == 200
        assert client.put(f"/api/editor/articles/{article_id}", json=PAYLOAD).status_code == 403
        assert client.post(f"/api/editor/articles/{article_id}/submit").status_code == 403
        assert not any(a["id"] == article_id for a in client.get("/api/articles").json())
        make_user(client, "medic1", "medic")
        assert client.post("/api/editor/articles", json=PAYLOAD).status_code == 403
        assert client.post(f"/api/editor/articles/{article_id}/publish").status_code == 200
        assert any(a["id"] == article_id for a in client.get("/api/articles").json())
        assert client.post(f"/api/editor/articles/{article_id}/publish").status_code == 409


def test_anonymous_and_unknown_category(monkeypatch, tmp_path):
    monkeypatch.setenv("NAVIGATOR_DB_PATH", str(tmp_path / "roles.sqlite3"))
    with TestClient(app) as client:
        assert client.get("/api/editor/articles").status_code == 401
        make_user(client, "editor2", "editor")
        assert client.post("/api/editor/articles", json={**PAYLOAD, "category": "bad"}).status_code == 422
        assert client.post("/api/editor/articles", json={**PAYLOAD, "title": "x"}).status_code == 422
