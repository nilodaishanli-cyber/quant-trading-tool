from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.analysis import router as analysis_router
from backend.api.auth import router as auth_router
from backend.api.health import router as health_router
from backend.api.watchlist import router as watchlist_router
from data.database import init_db


app = FastAPI(title="个人量化交易分析平台 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(watchlist_router)
app.include_router(analysis_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "这里是量化平台后端 API。网页前端请访问 http://127.0.0.1:8501/",
        "health": "http://127.0.0.1:8000/health",
        "docs": "http://127.0.0.1:8000/docs",
    }


@app.on_event("startup")
def on_startup() -> None:
    init_db()
