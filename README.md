# Crypto Tracker

Aplicación web que **grafica precios de criptomonedas en tiempo real e históricos** usando
los datos públicos de Binance. React + Vite + lightweight-charts en el frontend; FastAPI +
Pydantic + HTTPX + SQLAlchemy + Alembic sobre PostgreSQL en el backend; todo en Docker Compose.

**El objetivo no es la aplicación: es aprender el stack y el flujo de trabajo de un proyecto
de datos.** No es un proyecto de producción: no hay usuarios, ni SLA, ni dinero real en juego.
Por eso el código busca ser el mínimo que resuelve la fase actual, sin capas ni abstracciones
"por si acaso".

> **Estado:** fase 2 (PostgreSQL e ingesta idempotente) en curso. Ya están la tabla
> `candles`, el upsert idempotente, el backfill paginado con reintentos ante `429`/`418` y
> `/api/klines` leyendo de Postgres. Falta que algo ejecute la ingesta de forma periódica:
> hoy se corre a mano.

**Documentos de trabajo**

| Archivo | Para qué |
|---|---|
| `README.md` | Documentación estable: arquitectura, puesta en marcha, convenciones y decisiones. |
| [`CONTEXTO.md`](CONTEXTO.md) | Estado actual, pendientes y dudas abiertas. Se reescribe. |
| [`BITACORA.md`](BITACORA.md) | Historia del trabajo, sesión por sesión. Append-only. |

---

## 1. Arquitectura y flujo de datos

### Hoy (fase 2 en curso)

```
                    ┌── GET /api/klines ──> FastAPI (:8000) ──SELECT──> PostgreSQL
React (Vite :5173) ─┤   (proxy de Vite)                                     ▲
                    └── GET /api/ticker ──> FastAPI ──HTTPX async──> Binance │
                                                                             │ upsert
 app.ingest.candles (a mano) ──HTTPX sync──> data-api.binance.vision ────────┘
```

Hay dos caminos:

- **Velas:** se leen de PostgreSQL. La tabla se llena con la ingesta (`app/ingest/`), que
  pide velas a Binance y las guarda con un upsert idempotente. **La API ya no llama a
  Binance para velas.**
- **Ticker:** sigue siendo un proxy directo a Binance. Se deja así a propósito: es un solo
  dato vivo que no vale la pena persistir; la fase 3 lo pasará a Redis.

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
| Frontend | `frontend/src/` | `App.jsx` muestra el ticker; `CandleChart.jsx` pinta velas y refresca cada 10 s. |
| Cliente HTTP (front) | `frontend/src/lib/api.js` | `fetch` con URL relativa: Vite hace de intermediario, así no hay CORS en desarrollo. |
| API | `backend/app/api/market.py` | `/api/klines` lee de Postgres; `/api/ticker` hace proxy a Binance con HTTPX. |
| Esquemas | `backend/app/api/schemas.py` | Pydantic: `CandleOut` y `Ticker`, el contrato con el frontend. |
| Configuración | `backend/app/core/config.py` | `Settings` desde variables de entorno (pydantic-settings). |
| Base de datos | `backend/app/db/` | `models.py` (modelo `Candle`, tabla `candles`) y `session.py` (engine + `SessionLocal`). |
| Ingesta | `backend/app/ingest/candles.py` | Descarga de Binance con reintentos, upsert idempotente, `ingest_latest` y `backfill`. Importable por Airflow. |
| Migraciones | `backend/alembic/` | Esquema de PostgreSQL versionado. |

**Flujo paso a paso**

1. **Ingesta.** `ingest_latest()` o `backfill()` piden velas a `/api/v3/klines`, descartan
   la vela en curso, convierten cada fila a `Decimal` y `datetime` UTC y hacen upsert en
   `candles`.
2. **Carga inicial.** `CandleChart` pide `GET /api/klines?symbol=BTCUSDT&interval=1m&limit=500`
   y pasa el resultado a `series.setData()`.
3. **Lectura.** `get_klines` hace un `SELECT` ordenado por `open_time DESC` con `LIMIT`
   (para quedarse con las más recientes), invierte el resultado a orden ascendente (lo exige
   lightweight-charts) y convierte cada fila a `CandleOut`: `open_time` pasa a **segundos
   UNIX** y los `Decimal` a `float`.
4. **Refresco.** Cada 10 s se piden solo las 2 últimas velas y se aplican con
   `series.update()`. Se descarta cualquier vela más antigua que la última pintada, porque
   `update()` no acepta retroceder en el tiempo. **Solo aparecen velas nuevas si alguien
   corrió la ingesta entretanto.**
5. **Ticker.** `App.jsx` consulta `/api/ticker` cada 10 s; `_binance_get` llama a
   `/api/v3/ticker/24hr` y **propaga el status de Binance tal cual** (un `429` o `418` llega
   al navegador como `429` o `418`, no disfrazado de `500`).

---

## 2. Estructura de carpetas

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI, CORS, router de mercado, /health
│   │   ├── api/
│   │   │   ├── market.py           # /api/klines (Postgres) y /api/ticker (proxy a Binance)
│   │   │   └── schemas.py          # CandleOut, Ticker
│   │   ├── core/
│   │   │   └── config.py           # Settings desde variables de entorno
│   │   ├── db/
│   │   │   ├── models.py           # Base declarativa + modelo Candle (tabla candles)
│   │   │   └── session.py          # engine (pool_pre_ping) + SessionLocal
│   │   └── ingest/
│   │       └── candles.py          # fetch con reintentos, upsert, ingest_latest, backfill
│   ├── alembic/
│   │   ├── env.py                  # Toma la URL de settings, no de alembic.ini
│   │   └── versions/               # Historial de migraciones
│   ├── alembic.ini
│   ├── Dockerfile                  # python:3.12-slim + uvicorn
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                 # Cabecera con ticker + gráfico
│   │   ├── components/
│   │   │   └── CandleChart.jsx     # lightweight-charts, carga inicial + refresco
│   │   └── lib/
│   │       └── api.js              # getKlines, getTicker
│   ├── vite.config.js              # Proxy /api → localhost:8000
│   └── package.json
├── infra/
│   └── docker-compose.yml          # postgres + backend
├── Makefile                        # Atajos de Compose, psql y Alembic
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
| `fetch_klines(symbol, interval, limit, **params)` | GET a `/api/v3/klines` con reintentos ante `429`/`418` (ver §4). |
| `to_rows(symbol, interval, raw)` | Array de arrays de Binance → dicts listos para el upsert (`datetime` UTC, `Decimal`). |
| `upsert_candles(rows)` | Upsert en una transacción; devuelve cuántas filas envió. |
| `ingest_latest(symbol="BTCUSDT", interval="1m", limit=500)` | Últimas velas cerradas. |
| `backfill(symbol, interval, start, page_size=1000)` | Historia desde `start` (que **debe** tener timezone) hasta hoy. |

### Migraciones

Nunca DDL a mano contra la base. `alembic/env.py` sobrescribe `sqlalchemy.url` con
`settings.database_url` y usa `Base.metadata` como `target_metadata`, así `--autogenerate`
compara los modelos con el esquema real.

---

## 4. Binance: límites y manejo de errores

Se usa `https://data-api.binance.vision` (solo market data) en lugar de `api.binance.com`:
no requiere API key y evita bloqueos geográficos.

- Límite: **6.000 de peso por minuto, por IP** (no por API key).
- `X-MBX-USED-WEIGHT-1M` informa el peso consumido en la ventana actual.

| Situación | `/api/ticker` (proxy) | Ingesta (`fetch_klines`) |
|---|---|---|
| `2xx` | Convierte a `Ticker` y responde | Devuelve el JSON |
| `400` (símbolo o intervalo inválido) | Propaga `400` con el cuerpo de Binance | `raise_for_status()`: excepción, sin reintento |
| `429` (rate limit) | Propaga `429` | Reintenta hasta 5 veces |
| `418` (IP baneada) | Propaga `418` | Reintenta hasta 5 veces (ver pendiente abajo) |
| Otro `4xx`/`5xx` | Propaga el status | Excepción, sin reintento |
| Timeout (> 10 s) | Excepción de HTTPX → `500` | Excepción, sin reintento |

**Reintentos.** La espera es la de la cabecera `Retry-After` si Binance la manda (su número
gana sobre nuestro cálculo); si no, backoff exponencial `1 s, 2 s, 4 s, 8 s`. Tras el quinto
intento fallido no se espera más y se lanza `RuntimeError`.

**Pendiente:** ante un `418` la ingesta debería detenerse en vez de reintentar, porque cada
petición durante un baneo lo prolonga (escala de 2 min a 3 días).

### Limitaciones actuales (declaradas a propósito)

1. **La ingesta no corre sola.** Hay que ejecutarla a mano (ver §5). Airflow la orquestará
   en la fase 4.
2. **El refresco es polling REST cada 10 s.** Aceptable para una sola pestaña; es justo lo
   que la fase 3 sustituye por WebSocket → Redis Pub/Sub.
3. **Cliente HTTP nuevo en cada llamada.** `_binance_get` abre un `AsyncClient` por request
   y `fetch_klines` un `Client` por página del backfill. Sin reutilización de conexiones;
   suficiente con este volumen.
4. **El ticker no tiene caché.** Cada pestaña abierta multiplica las llamadas a Binance.
5. **El frontend pide `limit=2` en cada refresco** para cubrir el cruce de minuto: si entre
   dos refrescos se cierra una vela, la anterior llega completa y la nueva empieza.
6. **Con la tabla vacía el gráfico no se recupera.** `/api/klines` devuelve `[]`, el
   componente falla al leer la última vela y no arranca el refresco. Hay que correr la
   ingesta y recargar la página.
7. **La ingesta usa `print`**, no `logging`.

---

## 5. Puesta en marcha

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
| `make up` | Levanta `postgres` y `backend` en segundo plano |
| `make down` | Apaga el proyecto (los volúmenes se conservan) |
| `make restart` | `down` + `up` |
| `make logs` | Logs de todos los servicios en vivo |
| `make psql` | Consola `psql` dentro del contenedor de Postgres |
| `make migrate` | `alembic upgrade head` dentro del contenedor `backend` |
| `make revision m="mensaje"` | Genera una migración con `--autogenerate` |

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

### Frontend

```bash
cd frontend
npm install
npm run dev
```

La app queda en `http://localhost:5173`; la documentación interactiva de la API en
`http://localhost:8000/docs`. El backend monta `../backend` como volumen y arranca con
`--reload`, así que los cambios en Python se aplican sin reconstruir la imagen.

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

---

## 6. Recorrido de una vela hasta el gráfico

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

**f) Ticker** (sin base de datos):

```
GET /api/ticker?symbol=BTCUSDT
→ {"symbol":"BTCUSDT","last_price":65020.4,"price_change_percent":1.234}
```

---

## 7. Plan por fases

Cada fase queda funcionando de punta a punta antes de pasar a la siguiente.

| Fase | Contenido | Estado |
|---|---|---|
| 0 — Andamiaje | Monorepo, Compose con Postgres, `/health`, CORS, variables de entorno | ✅ |
| 1 — Rebanada vertical | Proxy a klines y ticker, velas en React con refresco de 10 s | ✅ |
| 2 — PostgreSQL | Tabla `candles` ✅, upsert idempotente ✅, backfill paginado ✅, API lee de Postgres ✅, ingesta periódica ⏳ | 🚧 |
| 3 — Redis y tiempo real | 3a: polling a Redis con TTL (cache-aside). 3b: WebSocket de Binance → Pub/Sub → WebSocket de FastAPI | ⏳ |
| 4 — Airflow | DAG incremental diario y DAG de backfill con `catchup=True` (ZIP de `data.binance.vision`) | ⏳ |
| 5 — MongoDB | Snapshots de order book y alertas/watchlists, con justificación frente a Postgres | ⏳ |
| 6 — Proyecto real | pytest, JWT, CI en GitHub Actions, Prometheus + Grafana, deploy | ⏳ |

---

## 8. Convenciones y supuestos

- **Timestamps siempre UTC.** `TIMESTAMPTZ` en Postgres; segundos UNIX (UTC) hacia el
  navegador. La conversión a hora local es responsabilidad de la capa de presentación.
  `backfill` rechaza fechas naive con `ValueError`.
- **Toda ingesta es idempotente.** La garantiza la PK de PostgreSQL, no la aplicación.
- **Nunca se persiste la vela en curso.**
- **La lógica vive en `app/ingest/`; los DAGs solo orquestan.** Lo que está dentro de una
  tarea de Airflow no se puede testear ni reutilizar.
- **Secretos en `.env`** (en `.gitignore`); `.env.example` está versionado.
- Explicaciones y documentación en español; código y nombres en inglés.
- Un solo símbolo por defecto (`BTCUSDT`) e intervalo `1m`. Los endpoints aceptan otros
  valores, pero el frontend todavía no ofrece selector.

### Registro de decisiones

| Decisión | Razón |
|---|---|
| `data-api.binance.vision` en vez de `api.binance.com` | Sin API key, sin bloqueos geográficos |
| WebSocket para tiempo real, REST solo para históricos | Binance banea el polling agresivo |
| lightweight-charts en vez de Recharts | Hecha para velas; evita pelear con ejes de tiempo |
| Proxy de Vite para `/api` | URLs relativas en el front y sin CORS en desarrollo |
| Propagar el status de Binance | Un `429`/`418` disfrazado de `500` oculta el problema real |
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
