# Contexto del proyecto

Foto del **estado actual** de Crypto Tracker: qué hay, qué falta y qué está en duda.
Se lee al empezar una sesión de trabajo (propia o de un asistente) para retomar sin
releer todo el código.

- Este archivo **se reescribe**: cuando algo cambia, se corrige aquí y se borra lo viejo.
- La historia de *cómo* se llegó hasta aquí va en [`BITACORA.md`](BITACORA.md), que es
  append-only.
- La documentación estable (arquitectura, puesta en marcha, convenciones, registro de
  decisiones) vive en [`README.md`](README.md). Aquí no se duplica, solo se enlaza.

> **Última actualización:** 2026-09-27

---

## 1. Qué es y para qué

App web que grafica velas de criptomonedas con datos públicos de Binance. React + Vite +
lightweight-charts; FastAPI + SQLAlchemy + Alembic sobre PostgreSQL, Redis para el precio
en vivo; Docker Compose.

**El objetivo es aprender el stack y el flujo de un proyecto de datos, no la app en sí.**
Por eso se prefiere el código mínimo que resuelve la fase actual, sin abstracciones
"por si acaso".

## 2. Fase actual

**Fase 3a — ticker vía Redis** (✅ implementada). La fase 2 está cerrada: el backfill se
probó contra Binance real el 2026-09-27 (detalle en `BITACORA.md`). Sigue la fase 3b. Plan
completo en `README.md` §8; detalle de Redis en §4.

| Pieza | Estado | Dónde |
|---|---|---|
| Tabla `candles` (PK `symbol, interval, open_time`, `NUMERIC`) | ✅ | `backend/app/db/models.py` |
| Migración inicial con Alembic | ✅ | `backend/alembic/versions/92e1536d2411_*` |
| `fetch_klines`: reintenta `429` (respeta `Retry-After`), corta con `RuntimeError` ante `418` | ✅ | `backend/app/ingest/candles.py` |
| `upsert_candles` con `ON CONFLICT DO UPDATE` | ✅ | `backend/app/ingest/candles.py` |
| `ingest_latest` (descarta la vela en curso) | ✅ | `backend/app/ingest/candles.py` |
| `backfill` paginando hacia atrás con `endTime` | ✅ probado contra Binance real | `backend/app/ingest/candles.py` |
| `/api/klines` lee de Postgres (sync) | ✅ | `backend/app/api/market.py` |
| Servicio `redis` (redis:7, con healthcheck, sin volumen ni puerto publicado) | ✅ | `infra/docker-compose.yml` |
| Cliente de Redis por proceso + `ticker_key` | ✅ | `backend/app/db/cache.py` |
| Worker: ticker de Binance cada 2 s → `ticker:<SYMBOL>` con TTL 10 s | ✅ | `backend/app/ingest/ticker.py`, servicio `worker` |
| `/api/ticker` lee de Redis (sync); `503` si no hay clave | ✅ | `backend/app/api/market.py` |
| Frontend: ticker cada 2 s, marca `· stale` en gris si falla | ✅ | `frontend/src/App.jsx` |
| Gráfico tolera la tabla vacía (aviso + reintenta la carga completa) | ✅ | `frontend/src/components/CandleChart.jsx` |
| `redis==8.1.0` en dependencias; `make redis` | ✅ | `backend/requirements.txt`, `Makefile` |
| Tests | ❌ (carpeta `backend/tests/` vacía) | — |

## 3. Pendientes inmediatos

1. **Fase 3b:** WebSocket de Binance en el worker → Redis Pub/Sub → WebSocket de FastAPI →
   navegador, para dejar el polling. El formato propio del valor en Redis está pensado para
   que ese cambio no toque la API.
2. **La ingesta periódica de velas no es de esta fase.** Se corre a mano a propósito; la
   automatiza Airflow en la fase 4, sin mecanismo provisional. Mientras tanto, el refresco
   de 10 s del gráfico solo muestra velas nuevas si se ingirió a mano entre refresco y
   refresco.

## 4. Dudas abiertas y discrepancias conocidas

- **El worker hace polling REST cada 2 s**, contra la regla "WebSocket para tiempo real".
  Aceptado como paso intermedio hasta la 3b; pesa ~60/min de los 6.000 permitidos.
- **El worker sigue un solo símbolo** (`BTCUSDT`, constante en `ticker.py`). Cualquier
  otro símbolo en `/api/ticker` da `503`.
- **El worker no tiene `--reload`:** tras editar `ticker.py` hay que
  `docker compose restart worker`.
- **Redis caído → `500` en `/api/ticker`**, no `503`: `get_ticker` no captura
  `redis.RedisError`. El frontend lo trata igual (marca `stale`).
- **El worker exige `DATABASE_URL`** aunque no use Postgres, porque `Settings` la declara
  obligatoria.
- **Un `httpx.Client` nuevo por página** en `fetch_klines`: en un backfill largo no se
  reutilizan conexiones.
- **`print` en lugar de `logging`** en la ingesta y el worker.
- **El intervalo está fijo en `App.jsx`** (`interval="1m"`). El gráfico solo muestra los
  intervalos que se hayan ingerido.
- **`ingest_latest` descarta la vela en curso**, así que el refresco nunca pinta la vela
  abierta: el gráfico avanza de a una vela cerrada por ingesta.
- `airflow/dags/` y `backend/tests/` existen localmente pero están vacías (git no las
  versiona).

## 5. Cómo retomar

```bash
cp .env.example .env   # solo la primera vez; ahora incluye REDIS_URL
make up                # postgres, redis, backend y worker
make migrate
cd frontend && npm install && npm run dev
```

Ejecutar la ingesta de velas a mano (desde la raíz del repo; `interval` por defecto es `"1m"`):

```bash
docker compose exec backend python -c \
  "from app.ingest.candles import ingest_latest; print(ingest_latest(interval='1m'))"
```

Comprobar que una carga de velas quedó completa e idempotente: consultas en `README.md` §6
("Comprobar una carga").

Comprobar el ticker: `docker compose logs -f worker` y `make redis` → `GET ticker:BTCUSDT`
/ `TTL ticker:BTCUSDT`.

Si se cambió `requirements.txt`, reconstruir la imagen antes de probar (`make up` **no**
reconstruye): `docker compose up -d --build backend worker`. Un `.env` creado antes de
2026-09-26 no tiene `REDIS_URL`: Compose falla con `falta en .env` hasta agregarla.

Recordatorios que muerden: Compose se ejecuta **siempre desde la raíz** (ver `README.md`
§6); Postgres se expone en el host en `localhost:5433`; Redis no se expone; Alembic corre
**dentro** del contenedor.
