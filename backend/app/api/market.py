import httpx
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.schemas import CandleOut, Ticker
from app.core.config import settings
from app.db.models import Candle
from app.db.session import SessionLocal


router = APIRouter(prefix="/api", tags=["market"])

TIMEOUT = 10.0


async def _binance_get(path: str, params: dict):
    async with httpx.AsyncClient(
        base_url=settings.binance_rest_url, timeout=TIMEOUT
    ) as client:
        response = await client.get(path, params=params)

    # Propagamos el status de Binance tal cual. Un 429 o un 418 tienen que
    # llegar al navegador como 429 o 418, no disfrazados de 500 genérico.
    if response.is_error:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return response.json()


@router.get("/klines", response_model=list[CandleOut])
def get_klines(
    symbol: str = "BTCUSDT",
    interval: str = "1m",
    limit: int = Query(default=500, le=1000),
):
    stmt = (
        select(Candle)
        .where(Candle.symbol == symbol, Candle.interval == interval)
        .order_by(Candle.open_time.desc())
        .limit(limit)
    )

    with SessionLocal() as session:
        candles = session.scalars(stmt).all()
        # DESC para quedarnos con las más recientes; lightweight-charts exige ASC
        return [
            CandleOut(
                time=int(c.open_time.timestamp()),
                open=float(c.open),
                high=float(c.high),
                low=float(c.low),
                close=float(c.close),
                volume=float(c.volume),
            )
            for c in reversed(candles)
        ]

@router.get("/ticker", response_model=Ticker)
async def get_ticker(symbol: str = "BTCUSDT"):
    data = await _binance_get("/api/v3/ticker/24hr", {"symbol": symbol})
    return Ticker(
        symbol=data["symbol"],
        last_price=data["lastPrice"],
        price_change_percent=data["priceChangePercent"],
    )