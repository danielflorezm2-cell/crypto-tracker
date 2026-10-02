import json
import time

import redis
from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from app.core.config import settings
from app.db.cache import cache, ticker_key

SYMBOL = "BTCUSDT"
# Binance empuja el ticker cada 1 s: 10 s de TTL aguantan varios mensajes perdidos
TTL_SECONDS = 10
# Si Binance, que manda cada 1 s, lleva 10 s callado, la conexión está muerta aunque
# TCP no se haya enterado (red caída sin aviso). Igual al TTL: el worker la da por
# muerta más o menos cuando la clave expira
SILENCE_SECONDS = 10
BASE_DELAY = 1.0
MAX_DELAY = 60.0
# Una conexión que vivió más que esto se considera sana y reinicia el backoff
STABLE_SECONDS = 60


def save(message: str) -> None:
    data = json.loads(message)
    # Nuestro formato, no el de Binance: cambió la fuente y la API no se entera
    payload = {
        "symbol": data["s"],
        "last_price": data["c"],
        "price_change_percent": data["P"],
    }
    key = ticker_key(data["s"])
    value = json.dumps(payload)
    # SET es la foto para quien llega tarde; PUBLISH avisa a quien ya escucha.
    # Pub/Sub no guarda nada: sin suscriptores, el mensaje se pierde.
    # El pipeline (MULTI/EXEC) manda los dos juntos: nadie ve uno sin el otro
    with cache.pipeline() as pipe:
        pipe.set(key, value, ex=TTL_SECONDS)
        # Claves y canales son espacios de nombres separados en Redis: el mismo
        # nombre no choca
        pipe.publish(key, value)
        pipe.execute()


def stream(symbol: str) -> None:
    # Binance exige el símbolo en minúsculas en el nombre del stream
    url = f"{settings.binance_ws_url}/ws/{symbol.lower()}@ticker"
    # websockets contesta solo los ping que Binance manda cada 20 s; sin ese pong,
    # Binance corta la conexión al minuto
    with connect(url) as ws:
        print(f"conectado a {url}")
        while True:
            message = ws.recv(timeout=SILENCE_SECONDS)
            try:
                save(message)
            except redis.RedisError as exc:
                # Redis caído un momento no es motivo para soltar a Binance:
                # el siguiente mensaje llega en 1 s
                print(f"error de Redis: {exc!r}")


def run(symbol: str = SYMBOL) -> None:
    delay = BASE_DELAY
    while True:
        started = time.monotonic()
        try:
            stream(symbol)
        except (OSError, WebSocketException) as exc:
            # También llega aquí el cierre limpio (ConnectionClosedOK): Binance
            # corta toda conexión a las 24 h. TimeoutError (silencio) es un OSError
            print(f"conexión perdida: {exc!r}")

        # El backoff se reinicia cuando la conexión duró, no cuando conectó: si Binance
        # acepta y corta enseguida, reiniciar al conectar reconectaría cada segundo
        if time.monotonic() - started > STABLE_SECONDS:
            delay = BASE_DELAY
        print(f"reconectando en {delay:.0f}s")
        time.sleep(delay)
        # Binance permite 300 intentos de conexión cada 5 min por IP
        delay = min(delay * 2, MAX_DELAY)


if __name__ == "__main__":
    run()