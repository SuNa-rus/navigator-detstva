from fastapi import FastAPI

app = FastAPI(
    title="Навигатор детства",
    version="0.1.0",
)

@app.get("/api/health")
def health_check():
    return {"status": "ok"}
