# Bitácora

Registro cronológico del trabajo en Crypto Tracker: qué se hizo, qué falló, qué se
aprendió y qué se decidió.

## Reglas

1. **Append-only.** Las entradas nuevas se agregan **al final**. Nunca se editan ni se
   borran entradas anteriores.
2. **Si algo estaba mal, se corrige con una entrada nueva** que diga qué entrada corrige
   y por qué (ej. "Corrige 2026-09-21: …").
3. **Una entrada por sesión de trabajo**, con fecha `AAAA-MM-DD` en el encabezado.
4. El estado actual del proyecto no va aquí: va en [`CONTEXTO.md`](CONTEXTO.md).

## Plantilla

```markdown
### AAAA-MM-DD — Título corto

**Hecho:** qué se cambió (archivos, commits).
**Problemas:** qué falló y cómo se resolvió.
**Aprendido:** lo que no era obvio.
**Decisiones:** qué se eligió y por qué.
**Siguiente:** por dónde seguir.
```

Solo se incluyen los campos que tengan contenido.

---

> Las entradas hasta 2026-09-23 se reconstruyeron a partir del historial de git el
> 2026-09-26; por eso son más escuetas que las siguientes.

### 2026-08-23 — Fase 0: andamiaje

**Hecho:** Monorepo con Docker Compose (Postgres + backend), `/health`, CORS y variables
de entorno (`f6c3dc1`).

### 2026-08-27 — Fase 1: primeros intentos en el frontend

**Problemas:** Cambios poco fructíferos; faltaba entender cómo se conectan los
componentes (`8327dbe`).

### 2026-08-29 — Fase 1: velas en pantalla

**Hecho:** Se pintan las velas con lightweight-charts (`201cda3`) y después funciona el
refresco (`1d24d45`).
**Problemas:** El gráfico se veía pero no se actualizaba. Era un error de uso de la
librería de velas en `CandleChart.jsx`.

### 2026-08-30 — Fase 1 terminada

**Hecho:** Endpoints `/api/klines` y `/api/ticker` funcionando como proxy a Binance, todas
las peticiones en `200`, proxy de Vite configurado (`5788545`). Ajuste del YAML de Compose
(`645340e`).

### 2026-09-02 — Inicio de la fase 2

**Hecho:** Arranque de la fase 2: PostgreSQL e ingesta (`34ac228`).

### 2026-09-07 — Configuración y dependencias

**Problemas:** Bug en pydantic-settings y problemas con `requirements.txt` y el venv;
corregidos (`8e252cb`).

### 2026-09-10 — `ConfigDict` / `SettingsConfigDict`

**Hecho:** Se migra la configuración a `ConfigDict` (`0638550`) y luego a
`SettingsConfigDict` (`f49251a`).
**Aprendido:** `SettingsConfigDict` es el `ConfigDict` extendido de pydantic-settings; es
el que corresponde en una clase `BaseSettings`.

### 2026-09-14 — Alembic y `sudo`

**Problemas:** `alembic init` generado con `sudo` dejó problemas en los archivos
generados; corregido (`227f0be`).

### 2026-09-17 — Alembic con autogenerate

**Hecho:** Alembic configurado con `--autogenerate` y migración de la tabla `candles`
(`b23a0f8`).

### 2026-09-20 — Ingesta idempotente

**Hecho:** `app/ingest/candles.py` con upsert `ON CONFLICT` funcionando (`1028625`).
**Problemas:** Choque de nombres entre el esquema Pydantic `Candle` y el modelo de
SQLAlchemy `Candle`. Se renombra el de la API a `CandleOut` (`98d932f`).

### 2026-09-21 — Reintentos y backfill

**Hecho:** Reintentos con backoff exponencial ante `429` y `418`, respetando
`Retry-After` (`4bf5587`). Backfill paginando hacia atrás con `endTime` (`3d71aec`).

### 2026-09-23 — `/api/klines` desde Postgres

**Hecho:** Bug del backoff arreglado (`2e643c0`). `/api/klines` deja de ser async y de
llamar a Binance: ahora lee de la tabla `candles` (`353e4f6`).

### 2026-09-26 — Documentación de trabajo

**Hecho:** Actualización del README (`24b4574`). Se crean `CONTEXTO.md` (estado actual,
se reescribe) y `BITACORA.md` (este archivo, append-only).
**Siguiente:** Decidir cómo se ejecuta la ingesta de forma periódica antes de Airflow;
revisar si `418` debe cortar la ingesta en vez de reintentarse; poner el README al día con
la fase 2.

### 2026-09-26 — README al día con la fase 2

**Hecho:** `README.md` reescrito para reflejar la fase 2: diagrama actual (velas desde
Postgres, ticker como proxy), funciones de `app/ingest/candles.py`, tabla de errores
separando `/api/ticker` y la ingesta, comandos para cargar velas a mano, recorrido de una
vela Binance → Postgres → gráfico y nuevas filas en el registro de decisiones.
**Aprendido:** Si `candles` está vacía, `CandleChart` falla al leer la última vela de `[]`
y no arranca el refresco; hay que ingerir y recargar.
**Siguiente:** Ingesta periódica; decidir si `418` corta la ingesta.
