from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.market import router as market_router
from app.core.config import settings


app = FastAPI(title="Crypto Tracker API")

"""
origins = [
    "http://localhost:5173",
    "http://localhost:8000",
]
"""
app.include_router(market_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}