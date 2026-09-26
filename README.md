# Crypto Tracker

Aplicación web que **grafica precios de criptomonedas en tiempo real e históricos** usando
los datos públicos de Binance. React + Vite + lightweight-charts en el frontend; FastAPI +
Pydantic + HTTPX + SQLAlchemy + Alembic sobre PostgreSQL en el backend; todo en Docker Compose.

**El objetivo no es la aplicación: es aprender el stack y el flujo de trabajo de un proyecto
de datos.** No es un proyecto de producción: no hay usuarios, ni SLA, ni dinero real en juego.
Por eso el código busca ser el mínimo que resuelve la fase actual, sin capas ni abstracciones
"por si acaso".

> **Estado:** fase 1 (rebanada vertical sin persistencia) terminada. Fase 2 (PostgreSQL e
> ingesta idempotente) en curso: el modelo `candles`, la sesión de SQLAlchemy y Alembic ya
> están; la ingesta y la lectura desde Postgres todavía no.

---

## 1. Arquitectura y flujo de datos

### Hoy (fase 1)

```
React (Vite :5173) ──GET /api/klines, /api/ticker──> Proxy de Vite ──> FastAPI (:8000)
       ▲                                                                   │
       │                                                                   v
       └──── JSON (Candle[], Ticker) <──── Pydantic <──── HTTPX async ──> data-api.binance.vision
```

FastAPI actúa como **proxy**: recibe la petición, llama a Binance, convierte la respuesta a
los esquemas de `app/api/schemas.py` y la devuelve. No hay base de datos en el camino.

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
| API | `backend/app/api/market.py` | Endpoints `/api/klines` y `/api/ticker`; proxy a Binance con HTTPX. |
| Esquemas | `backend/app/api/schemas.py` | Pydantic: `Candle` y `Ticker`, el contrato con el frontend. |
| Configuración | `backend/app/core/config.py` | `Settings` desde variables de entorno (pydantic-settings). |
| Base de datos | `backend/app/db/` | `models.py` (tabla `candles`) y `session.py` (engine + `SessionLocal`). |
| Ingesta | `backend/app/ingest/` | *Vacío por ahora.* Aquí vivirá la lógica de backfill, importable por Airflow. |
| Migraciones | `backend/alembic/` | Esquema de PostgreSQL versionado. |

**Flujo paso a paso (fase 1)**

1. **Carga inicial.** `CandleChart` pide `GET /api/klines?symbol=BTCUSDT&interval=1m&limit=500`
   y pasa el resultado a `series.setData()`.
2. **Proxy.** `_binance_get` llama a `/api/v3/klines`. Si Binance responde con error, el
   status se **propaga tal cual** (un `429` o `418` llega al navegador como `429` o `418`,
   no disfrazado de `500`).
3. **Conversión.** Binance devuelve un array de arrays con precios como *strings*; el
   endpoint lo mapea a `Candle` y pasa `open_time` de milisegundos a **segundos UNIX**, que es
   lo que espera lightweight-charts.
4. **Refresco.** Cada 10 s se piden solo las 2 últimas velas y se aplican con
   `series.update()`. Se descarta cualquier vela más antigua que la última pintada, porque
   `update()` no acepta retroceder en el tiempo.
5. **Ticker.** `App.jsx` consulta `/api/ticker` cada 10 s para mostrar precio y variación 24 h.

---

## 2. Estructura de carpetas

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI, CORS, router de mercado, /health
│   │   ├── api/
│   │   │   ├── market.py           # /api/klines y /api/ticker (proxy a Binance)
│   │   │   └── schemas.py          # Candle, Ticker
│   │   ├── core/
│   │   │   └── config.py           # Settings desde variables de entorno
│   │   ├── db/
│   │   │   ├── models.py           # Base declarativa + tabla candles
│   │   │   └── session.py          # engine (pool_pre_ping) + SessionLocal
│   │   └── ingest/                 # Lógica de ingesta (fase 2) — importable por Airflow
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
se mapea a `Decimal` en Python y conserva el valor exacto.

### Estrategia de idempotencia (planeada)

Correr la misma ingesta dos veces debe dejar la base igual que correrla una vez. La
herramienta es un **`INSERT ... ON CONFLICT (symbol, interval, open_time) DO UPDATE`**
contra la PK compuesta: si la vela no existe se inserta, si existe se sobrescribe con los
mismos valores.

Dos reglas acompañan al upsert:

1. **Nunca persistir la vela en curso.** La última vela que devuelve `/api/v3/klines`
   todavía está abierta y sus valores cambian. Se filtra por `close_time < ahora` antes de
   guardar.
2. **Paginar hacia atrás moviendo `endTime`, no `startTime`.** Máximo 1000 velas por
   llamada; el backfill avanza hacia el pasado hasta alcanzar la fecha objetivo.

### Migraciones

Nunca DDL a mano contra la base. `alembic/env.py` sobrescribe `sqlalchemy.url` con
`settings.database_url` y usa `Base.metadata` como `target_metadata`, así `--autogenerate`
compara los modelos con el esquema real.

---

## 4. Binance: límites y manejo de errores

Se usa `https://data-api.binance.vision` (solo market data) en lugar de `api.binance.com`:
no requiere API key y evita bloqueos geográficos.

| Situación | Qué hace hoy la API | Qué hará (fase 2) |
|---|---|---|
| `2xx` | Convierte a `Candle` / `Ticker` y responde | Igual, leyendo de Postgres |
| `400` (símbolo o intervalo inválido) | Propaga `400` con el cuerpo de Binance | Igual |
| `429` (rate limit) | Propaga `429` | Backoff respetando `Retry-After` |
| `418` (IP baneada) | Propaga `418` | Detener la ingesta; el baneo escala de 2 min a 3 días |
| Timeout (> 10 s) | Excepción de HTTPX → `500` | Reintento con backoff |

- Límite: **6.000 de peso por minuto, por IP** (no por API key).
- `X-MBX-USED-WEIGHT-1M` informa el peso consumido en la ventana actual.

### Limitaciones de la fase 1 (declaradas a propósito)

1. **El refresco es polling REST cada 10 s.** Aceptable para una sola pestaña; es justo lo
   que la fase 3 sustituye por WebSocket → Redis Pub/Sub.
2. **Cada request abre un `AsyncClient` nuevo.** Sin reutilización de conexiones. Suficiente
   con este volumen; el salto natural es un cliente compartido creado en el `lifespan`.
3. **No hay caché.** Cada pestaña abierta multiplica las llamadas a Binance.
4. **El frontend pide `limit=2` en cada refresco** para cubrir el cruce de minuto: si entre
   dos refrescos se cierra una vela, la anterior llega completa y la nueva empieza.

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

Frontend:

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
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Inicialización del contenedor de Postgres |
| `POSTGRES_PORT` | Puerto publicado en el host |
| `DATABASE_URL` | Conexión de SQLAlchemy y Alembic (`postgresql+psycopg://...@postgres:5432/...`) |
| `BINANCE_REST_URL` | Base de la API REST de Binance |
| `BACKEND_PORT` | Puerto publicado del backend |
| `CORS_ORIGINS` | Orígenes permitidos, separados por coma |

---

## 6. Recorrido de una vela hasta el gráfico

**a) El frontend pide velas:**

```
GET /api/klines?symbol=BTCUSDT&interval=1m&limit=500
```

**b) FastAPI llama a Binance**, que responde con un array de arrays:

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

**c) Qué ocurre dentro:**

1. `_binance_get` hace la petición con timeout de 10 s y propaga cualquier error.
2. Cada fila se convierte en `Candle`: `time = row[0] // 1000` y Pydantic transforma los
   strings de precio a `float`.
3. FastAPI valida la lista contra `response_model=list[Candle]` y responde:

```json
[{"time":1789000020,"open":65012.1,"high":65030.0,"low":64998.5,"close":65020.4,"volume":12.531}]
```

4. `CandleChart` llama a `series.setData(candles)` y guarda el `time` de la última vela.

> En el contrato hacia el navegador se usa `float` a propósito: lightweight-charts solo
> dibuja números y la precisión que se pierde no es visible en pantalla. El `Decimal` importa
> donde se **guarda**, no donde se pinta.

**d) Ticker:**

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
| 2 — PostgreSQL | Tabla `candles`, upsert idempotente, backfill paginado, API lee de Postgres | 🚧 |
| 3 — Redis y tiempo real | 3a: polling a Redis con TTL (cache-aside). 3b: WebSocket de Binance → Pub/Sub → WebSocket de FastAPI | ⏳ |
| 4 — Airflow | DAG incremental diario y DAG de backfill con `catchup=True` (ZIP de `data.binance.vision`) | ⏳ |
| 5 — MongoDB | Snapshots de order book y alertas/watchlists, con justificación frente a Postgres | ⏳ |
| 6 — Proyecto real | pytest, JWT, CI en GitHub Actions, Prometheus + Grafana, deploy | ⏳ |

---

## 8. Convenciones y supuestos

- **Timestamps siempre UTC.** `TIMESTAMPTZ` en Postgres; segundos UNIX (UTC) hacia el
  navegador. La conversión a hora local es responsabilidad de la capa de presentación.
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
| `COMPOSE_FILE` + `COMPOSE_PROJECT_NAME` en `.env` | Conserva `infra/` sin escribir `-f`; a cambio, Compose se ejecuta desde la raíz |
| Airflow aunque un cron bastaría | Objetivo pedagógico explícito, no técnico |
| Mongo solo en fase 5, con caso justificado | No meter tecnología sin razón |
| Deploy en la fase 6 | El deploy temprano roba tiempo al aprendizaje |
