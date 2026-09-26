import json

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.schemas import CandleOut, Ticker
from app.db.cache import cache, ticker_key
from app.db.models import Candle
from app.db.session import SessionLocal


router = APIRouter(prefix="/api", tags=["market"])

TIMEOUT = 10.0


@router.get("/ticker", response_model=Ticker)
def get_ticker(symbol: str = "BTCUSDT"):
    raw = cache.get(ticker_key(symbol))
    # Sin clave: el worker está caído, atrasado o no sigue este símbolo
    if raw is None:
        raise HTTPException(status_code=503, detail=f"No recent ticker for {symbol}")
    return Ticker(**json.loads(raw))


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