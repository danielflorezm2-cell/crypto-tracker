import httpx
from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import Candle, Ticker
from app.core.config import settings

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


@router.get("/klines", response_model=list[Candle])
async def get_klines(
    symbol: str = "BTCUSDT",
    interval: str = "1m",
    limit: int = Query(default=500, le=1000),
):
    raw = await _binance_get(
        "/api/v3/klines",
        {"symbol": symbol, "interval": interval, "limit": limit},
    )
    return [
        Candle(
            time=row[0] // 1000,
            open=row[1],
            high=row[2],
            low=row[3],
            close=row[4],
            volume=row[5],
        )
        for row in raw
    ]


@router.get("/ticker", response_model=Ticker)
async def get_ticker(symbol: str = "BTCUSDT"):
    data = await _binance_get("/api/v3/ticker/24hr", {"symbol": symbol})
    return Ticker(
        symbol=data["symbol"],
        last_price=data["lastPrice"],
        price_change_percent=data["priceChangePercent"],
    )