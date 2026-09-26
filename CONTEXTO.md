# Contexto del proyecto

Foto del **estado actual** de Crypto Tracker: qué hay, qué falta y qué está en duda.
Se lee al empezar una sesión de trabajo (propia o de un asistente) para retomar sin
releer todo el código.

- Este archivo **se reescribe**: cuando algo cambia, se corrige aquí y se borra lo viejo.
- La historia de *cómo* se llegó hasta aquí va en [`BITACORA.md`](BITACORA.md), que es
  append-only.
- La documentación estable (arquitectura, puesta en marcha, convenciones, registro de
  decisiones) vive en [`README.md`](README.md). Aquí no se duplica, solo se enlaza.

> **Última actualización:** 2026-09-26

---

## 1. Qué es y para qué

App web que grafica velas de criptomonedas con datos públicos de Binance. React + Vite +
lightweight-charts; FastAPI + SQLAlchemy + Alembic sobre PostgreSQL; Docker Compose.

**El objetivo es aprender el stack y el flujo de un proyecto de datos, no la app en sí.**
Por eso se prefiere el código mínimo que resuelve la fase actual, sin abstracciones
"por si acaso".

## 2. Fase actual

**Fase 2 — PostgreSQL e ingesta idempotente** (🚧). Plan completo en `README.md` §7.

| Pieza | Estado | Dónde |
|---|---|---|
| Tabla `candles` (PK `symbol, interval, open_time`, `NUMERIC`) | ✅ | `backend/app/db/models.py` |
| Migración inicial con Alembic | ✅ | `backend/alembic/versions/92e1536d2411_*` |
| `fetch_klines` con reintentos ante `429`/`418` (respeta `Retry-After`) | ✅ | `backend/app/ingest/candles.py` |
| `upsert_candles` con `ON CONFLICT DO UPDATE` | ✅ | `backend/app/ingest/candles.py` |
| `ingest_latest` (descarta la vela en curso) | ✅ | `backend/app/ingest/candles.py` |
| `backfill` paginando hacia atrás con `endTime` | ✅ | `backend/app/ingest/candles.py` |
| `/api/klines` lee de Postgres (sync) | ✅ | `backend/app/api/market.py` |
| `/api/ticker` sigue siendo proxy directo a Binance (async) | ✅ a propósito | `backend/app/api/market.py` |
| Algo que ejecute la ingesta periódicamente | ❌ | — |
| Tests | ❌ (carpeta `backend/tests/` vacía) | — |

## 3. Pendientes inmediatos

1. **Nadie alimenta la tabla de forma continua.** `/api/klines` ya lee de Postgres, pero
   la ingesta solo corre a mano. Sin eso, el refresco de 10 s del frontend repite datos
   viejos. Decidir el mecanismo provisional hasta que llegue Airflow (fase 4).
2. **Criterio de cierre de la fase 2:** ingesta periódica + backfill probado + API leyendo
   de Postgres + README al día.

## 4. Dudas abiertas y discrepancias conocidas

- **`418` se reintenta.** El README dice que ante un `418` la ingesta debe detenerse (el
  baneo escala de 2 min a 3 días), pero `fetch_klines` lo trata igual que un `429`.
- **Un `httpx.Client` nuevo por página** en `fetch_klines`: en un backfill largo no se
  reutilizan conexiones.
- **`print` en lugar de `logging`** en la ingesta.
- **Con la tabla vacía el gráfico no se recupera:** `CandleChart` falla al leer la última
  vela de `[]` y no arranca el refresco hasta recargar la página.
- `airflow/dags/` y `backend/tests/` existen localmente pero están vacías (git no las
  versiona).

## 5. Cómo retomar

```bash
cp .env.example .env   # solo la primera vez
make up
make migrate
cd frontend && npm install && npm run dev
```

Ejecutar la ingesta a mano (desde la raíz del repo):

```bash
docker compose exec backend python -c \
  "from app.ingest.candles import ingest_latest; print(ingest_latest())"
```

Recordatorios que muerden: Compose se ejecuta **siempre desde la raíz** (ver `README.md`
§5); Postgres se expone en el host en `localhost:5433`; Alembic corre **dentro** del
contenedor.
