import json
import time

import httpx
import redis

from app.core.config import settings
from app.db.cache import cache, ticker_key

SYMBOL = "BTCUSDT"
POLL_SECONDS = 2
# Varias vueltas de margen: un par de fallos seguidos no alcanzan para que la clave expire
TTL_SECONDS = 10
TIMEOUT = 5.0
FALLBACK_WAIT = 60


def poll_once(client: httpx.Client, symbol: str) -> None:
    response = client.get("/api/v3/ticker/24hr", params={"symbol": symbol})
    response.raise_for_status()
    data = response.json()

    # Nuestro formato, no el de Binance: en la 3b cambia la fuente y la API no se entera
    payload = {
        "symbol": data["symbol"],
        "last_price": data["lastPrice"],
        "price_change_percent": data["priceChangePercent"],
    }
    cache.set(ticker_key(symbol), json.dumps(payload), ex=TTL_SECONDS)


def run(symbol: str = SYMBOL) -> None:
    with httpx.Client(base_url=settings.binance_rest_url, timeout=TIMEOUT) as client:
        while True:
            try:
                poll_once(client, symbol)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in (429, 418):
                    wait = float(exc.response.headers.get("Retry-After", FALLBACK_WAIT))
                    print(f"{status} recibido, esperando {wait}s")
                    time.sleep(wait)
                    continue
                print(f"Binance respondió {status}")
            except (httpx.TransportError, redis.RedisError) as exc:
                # Red o Redis caídos un momento: se reintenta en la próxima vuelta
                print(f"error transitorio: {exc!r}")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()