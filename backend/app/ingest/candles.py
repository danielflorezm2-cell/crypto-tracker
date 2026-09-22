from datetime import datetime, timezone
from decimal import Decimal

import httpx
import time
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.db.models import Candle
from app.db.session import SessionLocal


TIMEOUT = 10.0
MAX_RETRIES = 5
BASE_DELAY = 1.0

def fetch_klines(symbol: str, interval: str, limit: int = 500, **params) -> list[list]:
    query = {"symbol": symbol, "interval": interval, "limit": limit, **params}

    with httpx.Client(base_url=settings.binance_rest_url, timeout=TIMEOUT) as client:
        for attempt in range(MAX_RETRIES):
            response = client.get("/api/v3/klines", params=query)

            if response.status_code not in (429,418):
                response.raise_for_status()
                return response.json()

            # Binance dice cuánto esperar; su número gana sobre nuestro cálculo
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else BASE_DELAY * (2 ** attempt)

            print(f"{response.status_code} recibido, esperando {delay}s (intento {attempt + 1}/{MAX_RETRIES})")
            time.sleep(delay)

    raise RuntimeError(f"Binance sigue rechazando después de {MAX_RETRIES} intentos")

def to_rows(symbol: str, interval: str, raw: list[list]) -> list[dict]:
    return [
        {
            "symbol": symbol,
            "interval": interval,
            # open_time siempre cae en un segundo exacto, así que // 1000 no pierde nada
            "open_time": datetime.fromtimestamp(row[0] // 1000, tz=timezone.utc),
            "open": Decimal(row[1]),
            "high": Decimal(row[2]),
            "low": Decimal(row[3]),
            "close": Decimal(row[4]),
            "volume": Decimal(row[5]),
        }
        for row in raw
    ]


def upsert_candles(rows: list[dict]) -> int:
    if not rows:
        return 0

    stmt = insert(Candle).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "interval", "open_time"],
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
        },
    )

    with SessionLocal() as session:
        session.execute(stmt)
        session.commit()

    return len(rows)


def ingest_latest(symbol: str = "BTCUSDT", interval: str = "1m", limit: int = 500, **params) -> int:
    raw = fetch_klines(symbol, interval, limit)
    # La última vela del array siempre es la en curso cuando pedimos hasta el presente
    return upsert_candles(to_rows(symbol, interval, raw[:-1]))