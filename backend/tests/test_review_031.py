from fastapi.testclient import TestClient
from app.main import app
from app.db import connect

P = {"title":"Материал для проверки", "category":"support", "summary":"Описание учебного материала", "body":"Подробный демонстрационный текст для проверки публикации.", "reading_minutes":2}

def account(client, name, role):
    assert client.post("/api/register", json={"username":name,"password":"Password987!"}).status_code == 201
    with connect() as db:
        db.execute("UPDATE users SET role=? WHERE username=?", (role,name))
    assert client.post("/api/login", json={"username":name,"password":"Password987!"}).status_code == 200

def test_review_return_publish_and_order(monkeypatch,tmp_path):
    monkeypatch.setenv("NAVIGATOR_DB_PATH",str(tmp_path/"review.sqlite3"))
    with TestClient(app) as client:
        account(client,"editor031","editor")
        response=client.post("/api/editor/articles",json=P)
        assert response.status_code==201
        id=response.json()["id"]
        assert client.post(f"/api/editor/articles/{id}/submit").status_code==200
        account(client,"medic031","medic")
        articles=client.get("/api/editor/articles").json()
        assert next(x for x in articles if x["id"]==id)["body"]==P["body"]
        assert client.post(f"/api/editor/articles/{id}/return",json={"comment":"Исправьте формулировки"}).status_code==200
        assert client.post(f"/api/editor/articles/{id}/publish").status_code==409
        account(client,"editor031b","editor")
        assert client.put(f"/api/editor/articles/{id}",json=P).status_code==403
        assert client.post(f"/api/editor/articles/{id}/submit").status_code==403
        assert client.post("/api/login",json={"username":"editor031","password":"Password987!"}).status_code==200
        own=client.get("/api/editor/articles").json()
        assert next(x for x in own if x["id"]==id)["review_comment"]=="Исправьте формулировки"
        assert client.put(f"/api/editor/articles/{id}",json=P).status_code==200
        assert client.post(f"/api/editor/articles/{id}/submit").status_code==200
        assert client.post("/api/login",json={"username":"medic031","password":"Password987!"}).status_code==200
        assert client.post(f"/api/editor/articles/{id}/publish").status_code==200
        with connect() as db:
            published=db.execute("SELECT published_at FROM articles WHERE id=?",(id,)).fetchone()
            assert published["published_at"]
        public=client.get("/api/articles").json()
        assert public[0]["id"]==id
