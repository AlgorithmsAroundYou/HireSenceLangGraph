from fastapi import FastAPI
from app.api.routes import router as api_router
from app.models.db import engine


app = FastAPI(title="HireSence AI Agent")


@app.on_event("startup")
async def on_startup():
    # Run SQL init script for SQLite using raw DB-API connection
    raw_conn = engine.raw_connection()
    try:
        with open("sql/init.sql", "r") as f:
            sql_script = f.read()
        cursor = raw_conn.cursor()
        cursor.executescript(sql_script)
        raw_conn.commit()
    finally:
        raw_conn.close()


app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
