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

### 2026-09-26 — Gráfico con tabla vacía, intervalos y dependencias fijadas

**Hecho:** `CandleChart.jsx` reescrito con una sola función `load` que se llama al montar
y cada 10 s: mientras `lastTime` es `null` pide la carga completa (500 velas) y, cuando
ya hay historia, solo las 2 últimas (`7ff3a33`). Si `/api/klines` devuelve `[]` se
muestra "No candles for … yet" encima del gráfico. Se quita la constante
`COLOMBIA_OFFSET` y los `console.log` sobrantes. Se probó el gráfico con intervalos
`1m`, `5m` y `15m` cambiando el prop en `App.jsx`; queda en `1m` (`9107dba`).
`requirements.txt`: se elimina el `pydantic-settings==2.15.0` duplicado y se fijan
`alembic`, `SQLAlchemy`, `psycopg` y `psycopg-binary` a versión exacta (`b9fc78a`).
`README.md` al día: flujo de carga inicial con tabla vacía, se elimina la limitación
"con la tabla vacía el gráfico no se recupera", aviso de que `make up` no reconstruye la
imagen y cómo ver otros intervalos.
**Problemas:** Resuelve lo anotado en la entrada anterior: con la tabla vacía el gráfico
ya no se queda muerto; se recupera solo en el siguiente tick, sin recargar la página.
**Aprendido:** El intervalo del gráfico tiene que coincidir con uno ya ingerido; si no,
la tabla no tiene filas para ese `interval` y se ve el aviso de vacío.
**Decisiones:** La ingesta periódica sale de la fase 2: es trabajo de Airflow en la fase 4
y no se monta ningún mecanismo provisional mientras tanto. Corrige el "Siguiente" de las
entradas anteriores de 2026-09-26, que la ponían como pendiente de esta fase.
**Siguiente:** Decidir si `418` corta la ingesta; probar el backfill para cerrar la fase 2.

### 2026-09-26 — `418` corta la ingesta y fase 3a: ticker vía Redis

**Hecho:** `fetch_klines` ya no reintenta ante `418`: lanza `RuntimeError` con el
`Retry-After` en el mensaje; solo el `429` se reintenta (`3296a77`). Servicio `redis`
(redis:7 con healthcheck) en Compose y `REDIS_URL` en `.env.example` (`09872c4`).
`app/db/cache.py` con un cliente de Redis por proceso y `ticker_key` (`3476132`).
`app/ingest/ticker.py`: worker que consulta `/api/v3/ticker/24hr` cada 2 s y guarda
`ticker:BTCUSDT` con TTL de 10 s; `/api/ticker` deja de llamar a Binance y lee de Redis,
con `503` si no hay clave; `redis_url` en `Settings`, `redis==8.1.0` y `make redis`
(`43e0b26`). Servicio `worker` en Compose (`python -u -m app.ingest.ticker`,
`restart: unless-stopped`, `init: true`); `App.jsx` refresca el ticker cada 2 s y, si la
petición falla, conserva el último precio en gris con la marca `· stale` (`5377e5d`).
README, CONTEXTO y esta bitácora al día.
**Problemas:** Sin `-u` los `print` del worker no aparecen en `docker compose logs`
(stdout con buffer). El servicio `worker` necesitó un ajuste de `init` en Compose
(`5377e5d`).
**Aprendido:** El TTL sirve como señal de salud: si el worker muere, la clave expira y la
API puede distinguir "no hay dato reciente" en vez de servir un precio viejo. Pedir desde
el navegador más rápido de lo que escribe el worker no trae datos nuevos.
**Decisiones:** Un solo escritor (el worker) y la API solo lee, para que las llamadas a
Binance no crezcan con las pestañas abiertas. El valor en Redis usa nuestro formato y no
el de Binance, para que la fase 3b cambie la fuente sin tocar la API. `418` corta la
ingesta de velas porque reintentar durante un baneo lo alarga; resuelve la duda anotada
en las entradas anteriores de 2026-09-26.
**Siguiente:** Quitar la versión vieja de `get_ticker` que quedó al final de `market.py`;
probar el backfill para cerrar la fase 2; fase 3b (WebSocket → Pub/Sub).

### 2026-09-26 — Limpieza de `market.py`

**Hecho:** Se elimina la versión vieja de `get_ticker` (async, llamaba a `_binance_get`,
que ya no existía) que había quedado al final de `market.py`, y la constante `TIMEOUT` sin
uso. `/openapi.json` expone una sola ruta `/api/ticker`, la que lee de Redis.
**Aprendido:** FastAPI permite registrar dos veces la misma ruta sin error; atiende la
primera y la segunda queda como código muerto.
**Siguiente:** Probar el backfill para cerrar la fase 2; fase 3b (WebSocket → Pub/Sub).

### 2026-09-26 — Diagramación de la API

**Hecho:** Se crea `docs/api.html`, un HTML autocontenido (SVG inline, sin dependencias
externas, tema claro y oscuro): diagramas C4 de contexto, contenedores y componentes de la
API; referencia de `/api/klines`, `/api/ticker` y `/health` con parámetros, status y
ejemplos; secuencias de lectura de velas, del ticker (worker + API) y de la ingesta;
modelo de datos (tabla `candles` y clave `ticker:<SYMBOL>`), errores de Binance y
variables de entorno. Enlazado desde el README.
**Decisiones:** Los diagramas son SVG inline y no Mermaid ni PlantUML cargados desde
un CDN, para que el archivo abra sin conexión.
**Siguiente:** Mantener `docs/api.html` al día cuando cambien endpoints o contenedores
(fase 3b agrega Pub/Sub y un WebSocket en FastAPI).

### 2026-09-26 — Generador de `docs/api.html`

**Hecho:** Se versiona `docs/gen_api_html.py`, el script que produce `docs/api.html` (solo
biblioteca estándar; escribe junto a sí mismo, así que se puede correr desde cualquier
carpeta). Regenerado, el HTML queda idéntico al versionado.
**Decisiones:** `docs/api.html` pasa a ser un archivo generado: los cambios se hacen en el
script y se regenera con `python3 docs/gen_api_html.py`. Las coordenadas de los diagramas
viven en las funciones `c4_*` y el contenido de las secuencias en `seq_*`.

### 2026-09-27 — Backfill probado: cierre de la fase 2

**Hecho:** Prueba de `backfill` sin cambios en el código, en dos partes. Primero contra
PostgreSQL 16 con la migración de Alembic y un Binance simulado (`/api/v3/klines` con límite
de 1000, `endTime`, vela en curso, fecha de listado, huecos, `429` y `418`): 35 chequeos OK
(paginación sin huecos, bordes de página, `start` naive, no alineado al minuto, anterior al
listado o en el futuro, idempotencia, `429` respetando `Retry-After`, `418` que corta y
reanudación sin duplicar). Después contra Binance real en Docker:
`backfill('BTCUSDT', '1m', 2026-09-24 00:00 UTC)` devolvió 5617, exactamente los minutos
entre `start` y la vela en curso (21:37 UTC), en 6 páginas. Re-ejecutado 20 min después
devolvió 5637, y la ventana `2026-09-24 00:00` → `2026-09-27 21:36` quedó con 5617 filas y la
misma huella md5 (`0b25a252…`) antes y después. README con las consultas de comprobación
(§6, "Comprobar una carga"); README, CONTEXTO y esta bitácora al día.
**Aprendido:** El número que devuelve `backfill` cuenta filas enviadas al upsert, no
insertadas: prueba que la paginación recorrió todo, no la idempotencia. La idempotencia se
comprueba en la tabla con una huella sobre una ventana fija, porque el total sube entre
corridas a medida que cierran velas. La huella no cambia porque una vela cerrada en Binance
no cambia: el `DO UPDATE` reescribe los mismos valores. Si se guardara la vela en curso, la
re-ejecución la modificaría; la idempotencia sale de las dos reglas juntas (PK + upsert, y
nunca la vela en curso). Que el conteo real cuadrara con los minutos transcurridos confirma
lo que el simulador solo suponía: con solo `endTime`, Binance devuelve las `limit` velas más
recientes anteriores a esa fecha; si no fuera así, el backfill habría guardado una página y
terminado sin error. `TIMESTAMPTZ` se muestra en la zona horaria de la sesión: con
`America/Bogota`, la vela de 00:00 UTC aparece como 19:00 del día anterior, y es el mismo
instante.
**Siguiente:** Fase 3b (WebSocket de Binance → Redis Pub/Sub → WebSocket de FastAPI).
