# Crypto Tracker

Aplicación web que **grafica precios de criptomonedas en tiempo real e históricos** usando
los datos públicos de Binance. React + Vite + lightweight-charts en el frontend; FastAPI +
Pydantic + HTTPX + SQLAlchemy + Alembic sobre PostgreSQL, y Redis como caché del precio en
vivo, en el backend; todo en Docker Compose.

**El objetivo no es la aplicación: es aprender el stack y el flujo de trabajo de un proyecto
de datos.** No es un proyecto de producción: no hay usuarios, ni SLA, ni dinero real en juego.
Por eso el código busca ser el mínimo que resuelve la fase actual, sin capas ni abstracciones
"por si acaso".

> **Estado:** fase 3a (ticker vía Redis) implementada. Un worker consulta el ticker de
> Binance cada 2 s y lo guarda en Redis con TTL; `/api/ticker` solo lee de Redis. De la
> fase 2 están la tabla `candles`, el upsert idempotente, el backfill paginado y
> `/api/klines` leyendo de Postgres; falta dejar registrada la prueba del backfill para
> cerrarla. La ingesta de velas se corre a mano a propósito: ejecutarla de forma periódica
> es trabajo de Airflow en la fase 4.

**Documentos de trabajo**

| Archivo | Para qué |
|---|---|
| `README.md` | Documentación estable: arquitectura, puesta en marcha, convenciones y decisiones. |
| [`CONTEXTO.md`](CONTEXTO.md) | Estado actual, pendientes y dudas abiertas. Se reescribe. |
| [`BITACORA.md`](BITACORA.md) | Historia del trabajo, sesión por sesión. Append-only. |
| [`docs/api.html`](docs/api.html) | Diagramación de la API: C4 (contexto, contenedores, componentes), endpoints, secuencias y modelo de datos. Abrir en el navegador. **Generado**: se edita [`docs/gen_api_html.py`](docs/gen_api_html.py) y se corre `python3 docs/gen_api_html.py`. |

---

## 1. Arquitectura y flujo de datos

### Hoy (fase 3a)

```
                    ┌── GET /api/klines (10 s) ──> FastAPI (:8000) ──SELECT──> PostgreSQL
React (Vite :5173) ─┤   (proxy de Vite)                                            ▲
                    └── GET /api/ticker (2 s) ───> FastAPI ──GET──> Redis          │
                                                                      ▲            │ upsert
 worker (app.ingest.ticker, cada 2 s) ──HTTPX──> Binance ──SET EX 10──┘            │
 app.ingest.candles (a mano) ──────────HTTPX──> Binance ───────────────────────────┘
```

Hay dos caminos, y **la API ya no llama a Binance en ninguno**:

- **Velas:** se leen de PostgreSQL. La tabla se llena con la ingesta (`app/ingest/candles.py`),
  que pide velas a Binance y las guarda con un upsert idempotente.
- **Ticker:** se lee de Redis. Lo escribe el servicio `worker` de Compose
  (`app/ingest/ticker.py`), que consulta `/api/v3/ticker/24hr` cada 2 s y guarda la clave
  `ticker:<SYMBOL>` con un TTL de 10 s. Si la clave no existe (worker caído, atrasado o
  símbolo no seguido), `/api/ticker` responde `503`.

### Objetivo (fases 2–5)

```
Binance WebSocket ──► Worker de ingesta ──► Redis (caché + pub/sub) ──┐
                                                                      ├──► FastAPI ──► React
Binance REST ─────────► Airflow DAGs ──────► PostgreSQL ──────────────┤
                                       └───► MongoDB ─────────────────┘
```

Regla que gobierna el diagrama: **WebSocket para tiempo real, REST solo para históricos.**
Binance banea el polling agresivo.

**Componentes**

| Capa | Archivos | Responsabilidad |
|---|---|---|
| Frontend | `frontend/src/` | `App.jsx` muestra el ticker (refresco de 2 s, marca "stale" si falla); `CandleChart.jsx` pinta velas y refresca cada 10 s. |
| Cliente HTTP (front) | `frontend/src/lib/api.js` | `fetch` con URL relativa: Vite hace de intermediario, así no hay CORS en desarrollo. |
| API | `backend/app/api/market.py` | `/api/klines` lee de Postgres; `/api/ticker` lee de Redis. Ninguno llama a Binance. |
| Esquemas | `backend/app/api/schemas.py` | Pydantic: `CandleOut` y `Ticker`, el contrato con el frontend. |
| Configuración | `backend/app/core/config.py` | `Settings` desde variables de entorno (pydantic-settings). |
| Base de datos | `backend/app/db/` | `models.py` (modelo `Candle`, tabla `candles`), `session.py` (engine + `SessionLocal`) y `cache.py` (cliente de Redis + `ticker_key`). |
| Ingesta de velas | `backend/app/ingest/candles.py` | Descarga de Binance con reintentos, upsert idempotente, `ingest_latest` y `backfill`. Importable por Airflow. |
| Worker del ticker | `backend/app/ingest/ticker.py` | Bucle infinito: consulta el ticker cada 2 s y lo escribe en Redis con TTL. Corre como servicio `worker`. |
| Migraciones | `backend/alembic/` | Esquema de PostgreSQL versionado. |

**Flujo paso a paso**

1. **Ingesta.** `ingest_latest()` o `backfill()` piden velas a `/api/v3/klines`, descartan
   la vela en curso, convierten cada fila a `Decimal` y `datetime` UTC y hacen upsert en
   `candles`.
2. **Carga inicial.** `CandleChart` pide `GET /api/klines?symbol=BTCUSDT&interval=1m&limit=500`
   y pasa el resultado a `series.setData()`. Si llega `[]` (tabla vacía para ese
   `interval`) muestra "No candles for … yet" y repite la carga completa en cada refresco
   hasta que haya datos; no hace falta recargar la página.
3. **Lectura.** `get_klines` hace un `SELECT` ordenado por `open_time DESC` con `LIMIT`
   (para quedarse con las más recientes), invierte el resultado a orden ascendente (lo exige
   lightweight-charts) y convierte cada fila a `CandleOut`: `open_time` pasa a **segundos
   UNIX** y los `Decimal` a `float`.
4. **Refresco.** Cada 10 s se piden solo las 2 últimas velas y se aplican con
   `series.update()`. Se descarta cualquier vela más antigua que la última pintada, porque
   `update()` no acepta retroceder en el tiempo. **Solo aparecen velas nuevas si alguien
   corrió la ingesta entretanto.**
5. **Ticker (escritura).** El worker pide `/api/v3/ticker/24hr?symbol=BTCUSDT` cada 2 s,
   lo traduce a **nuestro formato** (`symbol`, `last_price`, `price_change_percent`) y hace
   `SET ticker:BTCUSDT <json> EX 10`.
6. **Ticker (lectura).** `App.jsx` consulta `/api/ticker` cada 2 s; `get_ticker` hace un
   `GET` a Redis y valida el JSON contra `Ticker`. Si la clave expiró responde `503`, y el
   frontend conserva el último precio pero lo pinta en gris con la marca `· stale`. En
   cuanto vuelve un `200`, la marca desaparece.

---

## 2. Estructura de carpetas

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI, CORS, router de mercado, /health
│   │   ├── api/
│   │   │   ├── market.py           # /api/klines (Postgres) y /api/ticker (Redis)
│   │   │   └── schemas.py          # CandleOut, Ticker
│   │   ├── core/
│   │   │   └── config.py           # Settings desde variables de entorno
│   │   ├── db/
│   │   │   ├── models.py           # Base declarativa + modelo Candle (tabla candles)
│   │   │   ├── session.py          # engine (pool_pre_ping) + SessionLocal
│   │   │   └── cache.py            # Cliente de Redis + ticker_key
│   │   └── ingest/
│   │       ├── candles.py          # fetch con reintentos, upsert, ingest_latest, backfill
│   │       └── ticker.py           # Worker: ticker de Binance → Redis cada 2 s
│   ├── alembic/
│   │   ├── env.py                  # Toma la URL de settings, no de alembic.ini
│   │   └── versions/               # Historial de migraciones
│   ├── alembic.ini
│   ├── Dockerfile                  # python:3.12-slim + uvicorn
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                 # Cabecera con ticker (2 s, marca stale) + gráfico
│   │   ├── components/
│   │   │   └── CandleChart.jsx     # lightweight-charts, carga inicial + refresco
│   │   └── lib/
│   │       └── api.js              # getKlines, getTicker
│   ├── vite.config.js              # Proxy /api → localhost:8000
│   └── package.json
├── infra/
│   └── docker-compose.yml          # postgres + redis + backend + worker
├── docs/
│   ├── api.html                    # Diagramas C4, endpoints y secuencias (generado)
│   └── gen_api_html.py             # Generador de api.html (solo biblioteca estándar)
├── Makefile                        # Atajos de Compose, psql, redis-cli y Alembic
├── CONTEXTO.md                     # Estado actual del proyecto
├── BITACORA.md                     # Bitácora append-only
├── .env.example
└── .gitignore
```

Carpetas previstas para fases posteriores: `backend/tests/` (fase 6) y `airflow/dags/`
(fase 4, **solo orquestación**, sin lógica).

---

## 3. Persistencia e idempotencia (fase 2)

### Tabla

`app/db/models.py` define `candles`:

| Columna | Tipo | Nota |
|---|---|---|
| `symbol` | `VARCHAR(20)` | PK |
| `interval` | `VARCHAR(10)` | PK |
| `open_time` | `TIMESTAMPTZ` | PK. Siempre UTC, nunca naive. |
| `open`, `high`, `low`, `close` | `NUMERIC(20, 8)` | |
| `volume` | `NUMERIC(30, 8)` | Más dígitos enteros que los precios. |

**PK compuesta `(symbol, interval, open_time)`.** Es la clave natural de una vela: el mismo
símbolo, en el mismo intervalo, no puede tener dos velas que abren en el mismo instante. No
se añade un `id` sustituto porque no aportaría nada y obligaría a un índice único adicional.

**`NUMERIC` y no `FLOAT`.** Binance manda los precios como strings precisamente para no
perder decimales. En cripto de bajo valor (p. ej. `0.00000123`) un `float` redondea; `Numeric`
se mapea a `Decimal` en Python y conserva el valor exacto. Por eso `to_rows` construye
`Decimal(row[1])` directamente desde el string, sin pasar por `float`.

### Idempotencia

Correr la misma ingesta dos veces deja la base igual que correrla una vez. La herramienta es
un **`INSERT ... ON CONFLICT (symbol, interval, open_time) DO UPDATE`** contra la PK
compuesta (`upsert_candles`): si la vela no existe se inserta; si existe, se sobrescriben
`open`, `high`, `low`, `close` y `volume` con los valores recibidos.

Dos reglas acompañan al upsert:

1. **Nunca persistir la vela en curso.** Cuando se piden velas hasta el presente, la última
   del array todavía está abierta y sus valores cambian. `ingest_latest` y la primera página
   de `backfill` la descartan con `raw[:-1]`.
2. **Paginar hacia atrás moviendo `endTime`, no `startTime`.** Máximo 1000 velas por
   llamada. `backfill` arranca en el presente y en cada página fija
   `endTime = open_time más antiguo - 1`, hasta cruzar la fecha `start` o hasta que Binance
   no devuelva más historia. Las velas anteriores a `start` se filtran antes de guardar.

### Funciones de `app/ingest/candles.py`

| Función | Qué hace |
|---|---|
| `fetch_klines(symbol, interval, limit, **params)` | GET a `/api/v3/klines`: reintenta ante `429`, corta ante `418` (ver §5). |
| `to_rows(symbol, interval, raw)` | Array de arrays de Binance → dicts listos para el upsert (`datetime` UTC, `Decimal`). |
| `upsert_candles(rows)` | Upsert en una transacción; devuelve cuántas filas envió. |
| `ingest_latest(symbol="BTCUSDT", interval="1m", limit=500)` | Últimas velas cerradas. |
| `backfill(symbol, interval, start, page_size=1000)` | Historia desde `start` (que **debe** tener timezone) hasta hoy. |

### Migraciones

Nunca DDL a mano contra la base. `alembic/env.py` sobrescribe `sqlalchemy.url` con
`settings.database_url` y usa `Base.metadata` como `target_metadata`, así `--autogenerate`
compara los modelos con el esquema real.

---

## 4. Ticker en Redis (fase 3a)

Patrón: **un solo proceso escribe, la API solo lee.** El worker es el único que habla con
Binance para el ticker; la API y los navegadores leen de Redis. Así, abrir más pestañas no
multiplica las llamadas a Binance.

| Pieza | Valor | Dónde |
|---|---|---|
| Clave | `ticker:<SYMBOL>` (p. ej. `ticker:BTCUSDT`) | `ticker_key` en `app/db/cache.py` |
| Valor | JSON `{"symbol", "last_price", "price_change_percent"}` (strings, tal como llegan de Binance) | `poll_once` en `app/ingest/ticker.py` |
| Frecuencia de escritura | `POLL_SECONDS = 2` | `app/ingest/ticker.py` |
| TTL | `TTL_SECONDS = 10` | `app/ingest/ticker.py` |
| Refresco del frontend | `REFRESH_MS = 2_000` | `frontend/src/App.jsx` |
| Símbolo seguido | `SYMBOL = "BTCUSDT"` (uno solo) | `app/ingest/ticker.py` |

**El TTL es la señal de salud.** Con 10 s de TTL y escrituras cada 2 s, un par de fallos
seguidos no hacen expirar la clave; si el worker se cae o se atasca, la clave desaparece y
la API responde `503` en vez de servir un precio viejo como si fuera actual. El frontend
tampoco pide más rápido que el worker escribe: no traería datos nuevos.

**El formato es nuestro, no el de Binance.** El worker traduce `lastPrice` y
`priceChangePercent` antes de guardar. Cuando en la fase 3b la fuente pase a ser el
WebSocket de Binance, solo cambia el worker; la API y el frontend no se enteran.

**Errores en el worker.** El bucle nunca termina por un error:

| Situación | Qué hace |
|---|---|
| `429` / `418` | Duerme lo que diga `Retry-After` (60 s si no viene) y sigue |
| Otro status de error | Lo imprime y sigue en la próxima vuelta |
| Error de red (`httpx.TransportError`) o de Redis (`redis.RedisError`) | Lo imprime como transitorio y sigue |

Durante esas esperas la clave expira y el frontend muestra el precio como `stale`.

**Servicio en Compose.** `worker` usa la misma imagen que `backend` y monta `../backend`
como volumen, pero ejecuta `python -u -m app.ingest.ticker`:

- `-u` desactiva el buffer de stdout; sin él, los `print` no aparecen en `docker compose logs`.
- `init: true` pone un init (tini) como PID 1 para que `docker compose stop` le llegue al
  proceso de Python y el contenedor pare al instante en vez de esperar el timeout.
- `restart: unless-stopped`: si el proceso muere, Compose lo levanta de nuevo.
- Necesita `DATABASE_URL` aunque no use Postgres, porque `Settings` la exige al importarse.
- **No tiene `--reload`:** los cambios en `ticker.py` requieren `docker compose restart worker`.

El cliente de Redis (`cache`) es uno por proceso, igual que el engine de SQLAlchemy, con
`decode_responses=True` para recibir `str` y no `bytes`.

---

## 5. Binance: límites y manejo de errores

Se usa `https://data-api.binance.vision` (solo market data) en lugar de `api.binance.com`:
no requiere API key y evita bloqueos geográficos.

- Límite: **6.000 de peso por minuto, por IP** (no por API key).
- `X-MBX-USED-WEIGHT-1M` informa el peso consumido en la ventana actual.

La API ya no llama a Binance; solo lo hacen la ingesta de velas y el worker del ticker.

| Situación | Ingesta de velas (`fetch_klines`) | Worker del ticker |
|---|---|---|
| `2xx` | Devuelve el JSON | Escribe en Redis |
| `400` (símbolo o intervalo inválido) | `raise_for_status()`: excepción, sin reintento | Lo imprime y sigue |
| `429` (rate limit) | Reintenta hasta 5 veces | Duerme `Retry-After` y sigue |
| `418` (IP baneada) | **`RuntimeError` inmediato**, sin reintento | Duerme `Retry-After` y sigue |
| Otro `4xx`/`5xx` | Excepción, sin reintento | Lo imprime y sigue |
| Timeout | > 10 s: excepción, sin reintento | > 5 s: lo imprime y sigue |

**Reintentos ante `429`.** La espera es la de la cabecera `Retry-After` si Binance la manda
(su número gana sobre nuestro cálculo); si no, backoff exponencial `1 s, 2 s, 4 s, 8 s`.
Tras el quinto intento fallido no se espera más y se lanza `RuntimeError`.

**`418` corta la ingesta.** Cada petición durante un baneo lo prolonga (escala de 2 min a
3 días), así que `fetch_klines` no reintenta: lanza `RuntimeError` con el `Retry-After` en
el mensaje y deja que decida quien llama (a mano hoy, Airflow en la fase 4).

**Peso del worker.** `/api/v3/ticker/24hr` con un símbolo pesa 2; cada 2 s son ~60 de peso
por minuto, el 1 % del límite.

**Respuestas de `/api/ticker`** (lee de Redis, no de Binance):

| Situación | Respuesta |
|---|---|
| La clave existe | `200` con `Ticker` |
| La clave no existe (expiró o nunca se escribió) | `503` `No recent ticker for <SYMBOL>` |
| Redis caído | Excepción de `redis` → `500` |

### Limitaciones actuales (declaradas a propósito)

1. **La ingesta de velas no corre sola.** Hay que ejecutarla a mano (ver §6). Airflow la
   orquestará en la fase 4.
2. **El worker hace polling REST a Binance cada 2 s**, en contra de la regla "WebSocket
   para tiempo real". Es un paso intermedio aceptado: la fase 3b lo sustituye por el
   WebSocket de Binance → Redis Pub/Sub → WebSocket de FastAPI.
3. **El navegador también hace polling** (ticker cada 2 s, velas cada 10 s). Lo resuelve
   la misma fase 3b.
4. **El worker sigue un solo símbolo** (`BTCUSDT`). Pedir otro a `/api/ticker` da `503`.
5. **`fetch_klines` abre un `httpx.Client` por página** del backfill. Sin reutilización de
   conexiones; suficiente con este volumen. El worker, en cambio, reutiliza un solo cliente.
6. **El frontend pide `limit=2` en cada refresco** para cubrir el cruce de minuto: si entre
   dos refrescos se cierra una vela, la anterior llega completa y la nueva empieza.
7. **La ingesta y el worker usan `print`**, no `logging`.

---

## 6. Puesta en marcha

Requisitos: Docker con Compose v2, `make` y Node `^20.19` o `>=22.12` (lo exige Vite 8).

```bash
cp .env.example .env
make up
make migrate
```

**Todos los comandos de Compose se ejecutan desde la raíz del repo.** `.env` define
`COMPOSE_FILE=infra/docker-compose.yml` y `COMPOSE_PROJECT_NAME=crypto-tracker`; fuera de la
raíz las variables quedan vacías y Compose crea un segundo proyecto `infra` con volúmenes
propios. Los guardas `${VAR:?falta en .env}` convierten ese error en un fallo visible.

| Comando | Qué hace |
|---|---|
| `make up` | Levanta `postgres`, `redis`, `backend` y `worker` en segundo plano |
| `make down` | Apaga el proyecto (los volúmenes se conservan) |
| `make restart` | `down` + `up` |
| `make logs` | Logs de todos los servicios en vivo |
| `make psql` | Consola `psql` dentro del contenedor de Postgres |
| `make redis` | Consola `redis-cli` dentro del contenedor de Redis |
| `make migrate` | `alembic upgrade head` dentro del contenedor `backend` |
| `make revision m="mensaje"` | Genera una migración con `--autogenerate` |

`make up` **no reconstruye** la imagen del backend. Después de cambiar
`backend/requirements.txt` o el `Dockerfile`, reconstruir los dos servicios que la usan:
`docker compose up -d --build backend worker`.

Para ver el worker y la clave en Redis:

```bash
docker compose logs -f worker     # errores y esperas del worker
make redis                        # y dentro: GET ticker:BTCUSDT  /  TTL ticker:BTCUSDT
```

Redis no tiene volumen ni puerto publicado: solo guarda datos efímeros y se usa desde la
red de Compose (`redis:6379`).

Alembic corre **dentro** del contenedor porque `DATABASE_URL` apunta a `postgres:5432`, el
nombre del servicio en la red de Compose. Desde el host, Postgres se expone en
`localhost:${POSTGRES_PORT}` (5433 por defecto, para no chocar con un Postgres local).

### Cargar velas

La tabla empieza vacía. La ingesta también corre dentro del contenedor `backend`:

```bash
# Últimas 500 velas cerradas de BTCUSDT 1m
docker compose exec backend python -c \
  "from app.ingest.candles import ingest_latest; print(ingest_latest())"

# Historia desde una fecha (start debe llevar timezone)
docker compose exec backend python -c \
  "from datetime import datetime, timezone; from app.ingest.candles import backfill; \
   print(backfill('BTCUSDT', '1m', datetime(2026, 9, 1, tzinfo=timezone.utc)))"
```

Ambas devuelven cuántas filas se enviaron al upsert. Correrlas dos veces no duplica nada.

El gráfico pide `interval="1m"` (fijo en `App.jsx`). Para ver `5m` o `15m` hay que ingerir
ese intervalo (`ingest_latest(interval='5m')`) y cambiar el prop; si no, se ve el aviso de
tabla vacía.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

La app queda en `http://localhost:5173`; la documentación interactiva de la API en
`http://localhost:8000/docs`. El backend monta `../backend` como volumen y arranca con
`--reload`, así que los cambios en Python se aplican sin reconstruir la imagen. El
`worker` monta el mismo volumen pero **no** recarga solo: `docker compose restart worker`.

### Variables de entorno

| Variable | Uso |
|---|---|
| `COMPOSE_FILE`, `COMPOSE_PROJECT_NAME` | Ubicación del compose y nombre del proyecto (ver arriba) |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Inicialización del contenedor de Postgres |
| `POSTGRES_PORT` | Puerto publicado en el host |
| `DATABASE_URL` | Conexión de SQLAlchemy y Alembic (`postgresql+psycopg://...@postgres:5432/...`) |
| `BINANCE_REST_URL` | Base de la API REST de Binance |
| `BACKEND_PORT` | Puerto publicado del backend |
| `CORS_ORIGINS` | Orígenes permitidos, separados por coma |
| `REDIS_URL` | Conexión a Redis para la API y el worker (`redis://redis:6379/0`) |

---

## 7. Recorrido de una vela hasta el gráfico

**a) La ingesta pide velas a Binance**, que responde con un array de arrays:

```json
[
  [1789000020000, "65012.10000000", "65030.00000000", "64998.50000000",
   "65020.40000000", "12.53100000", 1789000079999, "814563.12", 1432,
   "6.10200000", "396701.33", "0"]
]
```

| Índice | Campo | Índice | Campo |
|---|---|---|---|
| `[0]` | open time (ms) | `[6]` | close time (ms) |
| `[1]` | open | `[7]` | quote asset volume |
| `[2]` | high | `[8]` | number of trades |
| `[3]` | low | `[9]` | taker buy base volume |
| `[4]` | close | `[10]` | taker buy quote volume |
| `[5]` | volume | `[11]` | ignorar |

**b) `to_rows` la convierte y `upsert_candles` la guarda:**

```python
{"symbol": "BTCUSDT", "interval": "1m",
 "open_time": datetime(2026, 9, 10, 0, 27, tzinfo=timezone.utc),  # 1789000020000 // 1000
 "open": Decimal("65012.10000000"), "high": Decimal("65030.00000000"),
 "low": Decimal("64998.50000000"), "close": Decimal("65020.40000000"),
 "volume": Decimal("12.53100000")}
```

Solo se usan los índices `[0]` a `[5]`; el resto se ignora.

**c) El frontend pide velas:**

```
GET /api/klines?symbol=BTCUSDT&interval=1m&limit=500
```

**d) FastAPI lee de Postgres y responde:**

1. `SELECT ... WHERE symbol = 'BTCUSDT' AND interval = '1m' ORDER BY open_time DESC LIMIT 500`.
2. Invierte el resultado a orden ascendente.
3. Convierte cada fila a `CandleOut`: `time = int(open_time.timestamp())` y los `Decimal`
   a `float`.
4. FastAPI valida la lista contra `response_model=list[CandleOut]`:

```json
[{"time":1789000020,"open":65012.1,"high":65030.0,"low":64998.5,"close":65020.4,"volume":12.531}]
```

**e)** `CandleChart` llama a `series.setData(candles)` y guarda el `time` de la última vela.

> En el contrato hacia el navegador se usa `float` a propósito: lightweight-charts solo
> dibuja números y la precisión que se pierde no es visible en pantalla. El `Decimal` importa
> donde se **guarda**, no donde se pinta.

**f) Ticker** (Redis, sin Postgres). Lo que guarda el worker:

```
ticker:BTCUSDT  (TTL 10 s)
{"symbol": "BTCUSDT", "last_price": "65020.40000000", "price_change_percent": "1.234"}
```

Lo que responde la API (Pydantic convierte los strings a `float`):

```
GET /api/ticker?symbol=BTCUSDT
→ 200 {"symbol":"BTCUSDT","last_price":65020.4,"price_change_percent":1.234}
→ 503 {"detail":"No recent ticker for BTCUSDT"}   # si la clave expiró
```

---

## 8. Plan por fases

Cada fase queda funcionando de punta a punta antes de pasar a la siguiente.

| Fase | Contenido | Estado |
|---|---|---|
| 0 — Andamiaje | Monorepo, Compose con Postgres, `/health`, CORS, variables de entorno | ✅ |
| 1 — Rebanada vertical | Proxy a klines y ticker, velas en React con refresco de 10 s | ✅ |
| 2 — PostgreSQL | Tabla `candles` ✅, upsert idempotente ✅, backfill paginado ✅, API lee de Postgres ✅, `418` corta la ingesta ✅. Falta registrar la prueba del backfill | 🚧 |
| 3 — Redis y tiempo real | 3a: worker escribe el ticker en Redis con TTL, la API solo lee ✅. 3b: WebSocket de Binance → Pub/Sub → WebSocket de FastAPI ⏳ | 🚧 |
| 4 — Airflow | Ingesta periódica: DAG incremental diario y DAG de backfill con `catchup=True` (ZIP de `data.binance.vision`) | ⏳ |
| 5 — MongoDB | Snapshots de order book y alertas/watchlists, con justificación frente a Postgres | ⏳ |
| 6 — Proyecto real | pytest, JWT, CI en GitHub Actions, Prometheus + Grafana, deploy | ⏳ |

---

## 9. Convenciones y supuestos

- **Timestamps siempre UTC.** `TIMESTAMPTZ` en Postgres; segundos UNIX (UTC) hacia el
  navegador. La conversión a hora local es responsabilidad de la capa de presentación.
  `backfill` rechaza fechas naive con `ValueError`.
- **Toda ingesta es idempotente.** La garantiza la PK de PostgreSQL, no la aplicación.
- **Nunca se persiste la vela en curso.**
- **La lógica vive en `app/ingest/`; los DAGs solo orquestan.** Lo que está dentro de una
  tarea de Airflow no se puede testear ni reutilizar.
- **Secretos en `.env`** (en `.gitignore`); `.env.example` está versionado.
- Explicaciones y documentación en español; código y nombres en inglés.
- **La API no llama a Binance.** Lee de Postgres (velas) o de Redis (ticker); hablar con
  Binance es trabajo de la ingesta y del worker.
- Un solo símbolo por defecto (`BTCUSDT`) e intervalo `1m`. `/api/klines` acepta otros
  valores; `/api/ticker` solo tiene datos para el símbolo que sigue el worker. El frontend
  todavía no ofrece selector.

### Registro de decisiones

| Decisión | Razón |
|---|---|
| `data-api.binance.vision` en vez de `api.binance.com` | Sin API key, sin bloqueos geográficos |
| WebSocket para tiempo real, REST solo para históricos | Binance banea el polling agresivo |
| lightweight-charts en vez de Recharts | Hecha para velas; evita pelear con ejes de tiempo |
| Proxy de Vite para `/api` | URLs relativas en el front y sin CORS en desarrollo |
| Ticker: un worker escribe en Redis, la API solo lee | Las llamadas a Binance no crecen con los usuarios; la API no depende de la latencia de Binance |
| TTL de 10 s con escrituras cada 2 s | Tolera un par de fallos; si el worker muere, la clave expira y la API da `503` en vez de un precio viejo |
| `503` sin clave, y el frontend marca `stale` | Un precio viejo mostrado como actual es peor que avisar que está viejo |
| Formato propio en Redis, no el JSON de Binance | Cambiar la fuente en la fase 3b no toca la API ni el frontend |
| Worker como servicio de Compose con la imagen del backend | Reutiliza código y dependencias; `restart: unless-stopped` lo mantiene vivo |
| `418` corta la ingesta de velas | Reintentar durante un baneo lo alarga; decide quien llama |
| PK compuesta natural en `candles` | Es la identidad de la vela y el objetivo del `ON CONFLICT` |
| `NUMERIC` para precios | Evita perder precisión en cripto de bajo valor |
| Esquema de la API `CandleOut`, modelo de la base `Candle` | Evita el choque de nombres entre Pydantic y SQLAlchemy al importar ambos |
| `/api/klines` síncrono | SQLAlchemy se usa en modo sync; FastAPI corre los `def` en un threadpool y no bloquea el event loop |
| `Retry-After` gana sobre el backoff propio | Binance sabe cuánto falta para liberar la ventana |
| Ingesta con `httpx.Client` síncrono | Se ejecuta como script o tarea de Airflow, donde no hay event loop |
| `COMPOSE_FILE` + `COMPOSE_PROJECT_NAME` en `.env` | Conserva `infra/` sin escribir `-f`; a cambio, Compose se ejecuta desde la raíz |
| Airflow aunque un cron bastaría | Objetivo pedagógico explícito, no técnico |
| Mongo solo en fase 5, con caso justificado | No meter tecnología sin razón |
| Deploy en la fase 6 | El deploy temprano roba tiempo al aprendizaje |
