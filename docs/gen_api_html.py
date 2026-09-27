"""Genera docs/api.html con diagramas SVG inline (C4 + secuencias).

Uso, desde cualquier carpeta:  python3 docs/gen_api_html.py
Solo usa la biblioteca estándar. docs/api.html es un artefacto generado: se edita
este script, no el HTML.
"""
import os
from html import escape as e

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api.html")


# ---------- primitivas SVG ----------
def text_lines(x, y, lines, cls, step=14, anchor="middle"):
    out = []
    for i, ln in enumerate(lines):
        out.append(f'<text x="{x}" y="{y + i * step}" class="{cls}" text-anchor="{anchor}">{e(ln)}</text>')
    return "".join(out)


def box(x, y, w, h, title, kind_label, desc, cls):
    cx = x + w / 2
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" class="{cls}"/>'
    s += text_lines(cx, y + 24, [title], f"t-title {cls}-t")
    s += text_lines(cx, y + 40, [f"[{kind_label}]"], f"t-kind {cls}-t")
    s += text_lines(cx, y + 60, desc, f"t-desc {cls}-t")
    return s


def person(x, y, w, h, title, desc):
    cx = x + w / 2
    s = f'<circle cx="{cx}" cy="{y + 16}" r="16" class="c4-person"/>'
    s += f'<rect x="{x}" y="{y + 28}" width="{w}" height="{h - 28}" rx="18" class="c4-person"/>'
    s += text_lines(cx, y + 52, [title], "t-title c4-person-t")
    s += text_lines(cx, y + 68, ["[Persona]"], "t-kind c4-person-t")
    s += text_lines(cx, y + 86, desc, "t-desc c4-person-t")
    return s


def cylinder(x, y, w, h, title, kind_label, desc, cls):
    ry = 10
    cx = x + w / 2
    body = (f'<path d="M{x},{y + ry} A{w / 2},{ry} 0 0 0 {x + w},{y + ry} '
            f'L{x + w},{y + h - ry} A{w / 2},{ry} 0 0 1 {x},{y + h - ry} Z" class="{cls}"/>')
    top = f'<ellipse cx="{cx}" cy="{y + ry}" rx="{w / 2}" ry="{ry}" class="{cls} cyl-top"/>'
    s = body + top
    s += text_lines(cx, y + 38, [title], f"t-title {cls}-t")
    s += text_lines(cx, y + 54, [f"[{kind_label}]"], f"t-kind {cls}-t")
    s += text_lines(cx, y + 72, desc, f"t-desc {cls}-t")
    return s


def boundary(x, y, w, h, label):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" class="boundary"/>'
            f'<text x="{x + 12}" y="{y + h - 12}" class="t-boundary">{e(label)}</text>')


def arrow(points, label=None, lx=None, ly=None, anchor="middle", dashed=False):
    pts = " ".join(f"{px},{py}" for px, py in points)
    cls = "rel dashed" if dashed else "rel"
    s = f'<polyline points="{pts}" class="{cls}" marker-end="url(#arrow)"/>'
    if label:
        s += text_lines(lx, ly, label, "t-rel", step=13, anchor=anchor)
    return s


DEFS = ('<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" '
        'markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="arrowhead"/>'
        '</marker></defs>')


def svg(w, h, body, title, minw=None):
    minw = minw or w
    return (f'<div class="diagram"><svg viewBox="0 0 {w} {h}" style="min-width:{minw}px" role="img" '
            f'aria-label="{e(title)}">{DEFS}{body}</svg></div>').replace('style="min-width', f'style="max-width:{w}px;min-width', 1)


# ---------- C4 nivel 1: contexto ----------
def c4_context():
    b = ""
    b += person(20, 40, 210, 130, "Usuario", ["Desarrollador que sigue", "el precio de BTCUSDT"])
    b += box(370, 60, 280, 110, "Crypto Tracker", "Sistema de software",
             ["Grafica velas históricas y el", "precio en vivo de criptomonedas"], "c4-system")
    b += box(800, 60, 240, 110, "Binance REST API", "Sistema externo",
             ["data-api.binance.vision", "Solo market data, sin API key"], "c4-ext")
    b += arrow([(230, 115), (366, 115)], ["Ve el gráfico y", "el ticker [HTTP]"], 298, 92)
    b += arrow([(650, 115), (796, 115)], ["Pide velas y ticker", "24 h [HTTPS/JSON]"], 723, 92)
    return svg(1060, 200, b, "Diagrama C4 de contexto", 760)


# ---------- C4 nivel 2: contenedores ----------
def c4_containers():
    A, B, C = 60, 380, 680
    W, H = 220, 110
    r1, r2, r3 = 200, 400, 580
    b = boundary(30, 170, 890, 560, "Crypto Tracker  [Sistema de software · Docker Compose + host]")
    b += person(A, 10, W, 130, "Usuario", ["Abre localhost:5173"])
    b += box(A, r1, W, H, "Frontend SPA", "React 19 + Vite · host :5173",
             ["App.jsx: ticker cada 2 s", "CandleChart.jsx: velas cada 10 s"], "c4-container")
    b += box(B, r1, W, H, "API", "FastAPI · uvicorn · :8000",
             ["/api/klines, /api/ticker,", "/health. No llama a Binance"], "c4-container")
    b += cylinder(A, r2, W, H, "PostgreSQL", "postgres:16 · host :5433",
                  ["Tabla candles (PK natural)"], "c4-db")
    b += cylinder(B, r2, W, H, "Redis", "redis:7 · sin puerto en host",
                  ["ticker:<SYMBOL> con TTL 10 s"], "c4-db")
    b += box(C, r2, W, H, "Worker del ticker", "Python · app.ingest.ticker",
             ["Bucle infinito, poll cada 2 s", "restart: unless-stopped"], "c4-container")
    b += box(A, r3, W, H, "Ingesta de velas", "Python · app.ingest.candles",
             ["ingest_latest / backfill", "Se corre a mano (Airflow en F4)"], "c4-container")
    b += box(1040, r2, 200, H, "Binance REST API", "Sistema externo",
             ["data-api.binance.vision", "6.000 de peso/min por IP"], "c4-ext")

    b += arrow([(A + W / 2, 140), (A + W / 2, r1 - 4)], ["Usa [navegador]"], A + W / 2 + 8, 160, "start")
    b += arrow([(A + W, r1 + 55), (B - 4, r1 + 55)], ["GET /api/*", "[JSON, proxy", "de Vite]"], (A + W + B) / 2, r1 + 22)
    b += arrow([(B + 40, r1 + H), (A + W - 40, r2 - 2)], ["SELECT velas", "[SQL, psycopg]"], 300, r1 + H + 36)
    b += arrow([(B + W / 2, r1 + H), (B + W / 2, r2 - 2)], ["GET ticker:SYM", "[RESP]"], B + W / 2 + 8, r1 + H + 36, "start")
    b += arrow([(C, r2 + 60), (B + W + 4, r2 + 60)], ["SET … EX 10", "[RESP]"], (B + W + C) / 2, r2 + 34)
    b += arrow([(C + W, r2 + 55), (1036, r2 + 55)], ["ticker/24hr", "cada 2 s [HTTPS]"], 982, r2 + 28)
    b += arrow([(A + W / 2, r3), (A + W / 2, r2 + H + 4)], ["upsert ON CONFLICT", "[SQL]"], A + W / 2 + 8, r2 + H + 28, "start")
    b += arrow([(A + W, r3 + 60), (1140, r3 + 60), (1140, r2 + H + 4)], ["GET /api/v3/klines · reintenta 429, corta en 418 [HTTPS]"], 705, r3 + 52)
    return svg(1260, 750, b, "Diagrama C4 de contenedores", 900)


# ---------- C4 nivel 3: componentes de la API ----------
def c4_components():
    W, H = 220, 100
    b = boundary(20, 140, 1020, 640, "API  [Contenedor · FastAPI · backend/app]")
    b += box(420, 10, W, 90, "Frontend SPA", "Contenedor · React + Vite", ["lib/api.js: getKlines, getTicker"], "c4-container")
    b += box(420, 170, W, H, "main.py", "FastAPI app",
             ["CORSMiddleware (CORS_ORIGINS)", "include_router · GET /health"], "c4-component")
    b += box(60, 330, W, H, "get_klines", "Ruta sync · api/market.py",
             ["GET /api/klines", "SELECT … DESC LIMIT, invierte"], "c4-component")
    b += box(420, 330, W, H, "schemas.py", "Pydantic",
             ["CandleOut, Ticker", "Contrato con el frontend"], "c4-component")
    b += box(780, 330, W, H, "get_ticker", "Ruta sync · api/market.py",
             ["GET /api/ticker", "503 si la clave no existe"], "c4-component")
    b += box(60, 490, W, H, "models.py", "SQLAlchemy ORM",
             ["Base declarativa", "Modelo Candle → candles"], "c4-component")
    b += box(310, 490, W, H, "session.py", "SQLAlchemy",
             ["engine (pool_pre_ping)", "SessionLocal"], "c4-component")
    b += box(780, 490, W, H, "cache.py", "redis-py",
             ["cache (1 cliente/proceso)", "ticker_key(symbol)"], "c4-component")
    b += box(560, 650, W, H, "config.py", "pydantic-settings",
             ["Settings: DATABASE_URL,", "REDIS_URL, CORS_ORIGINS…"], "c4-component")
    b += cylinder(310, 810, W, 100, "PostgreSQL", "Contenedor · postgres:16", ["Tabla candles"], "c4-db")
    b += cylinder(780, 810, W, 100, "Redis", "Contenedor · redis:7", ["ticker:<SYMBOL>"], "c4-db")

    b += arrow([(530, 100), (530, 166)], ["HTTP/JSON"], 538, 138, "start")
    b += arrow([(450, 270), (240, 326)], ["enruta"], 330, 290)
    b += arrow([(610, 270), (820, 326)], ["enruta"], 730, 290)
    b += arrow([(280, 380), (416, 380)], ["CandleOut"], 348, 372)
    b += arrow([(780, 380), (644, 380)], ["Ticker"], 712, 372)
    b += arrow([(170, 430), (170, 486)], ["select(Candle)"], 178, 462, "start")
    b += arrow([(250, 430), (380, 486)], ["SessionLocal()"], 340, 452, "start")
    b += arrow([(890, 430), (890, 486)], ["cache.get", "ticker_key"], 898, 456, "start")
    b += arrow([(470, 590), (600, 646)], ["database_url"], 548, 612, "start")
    b += arrow([(840, 590), (784, 646)], ["redis_url"], 826, 624, "start")
    b += arrow([(640, 220), (1015, 220), (1015, 700), (784, 700)], ["cors_origins_list"], 1005, 690, "end")
    b += arrow([(400, 590), (400, 806)], ["SQL [psycopg 3]"], 392, 800, "end")
    b += arrow([(890, 590), (890, 806)], ["RESP"], 898, 800, "start")
    return svg(1060, 930, b, "Diagrama C4 de componentes de la API", 860)


# ---------- diagramas de secuencia ----------
def sequence(parts, items, width=None, title=""):
    gap = 190
    x0 = 100
    xs = {p[0]: x0 + i * gap for i, p in enumerate(parts)}
    W = width or x0 * 2 + gap * (len(parts) - 1)
    y = 90
    body_items = []
    frames = []
    for it in items:
        k = it[0]
        if k == "msg":
            _, a, c, label, dashed = it
            xa, xc = xs[a], xs[c]
            if a == c:
                body_items.append(
                    f'<polyline points="{xa},{y} {xa + 40},{y} {xa + 40},{y + 18} {xa + 4},{y + 18}" '
                    f'class="rel{" dashed" if dashed else ""}" marker-end="url(#arrow)"/>')
                body_items.append(text_lines(xa + 48, y + 13, [label], "t-msg", anchor="start"))
                y += 44
                continue
            end = xc - 4 if xc > xa else xc + 4
            body_items.append(arrow([(xa, y), (end, y)], dashed=dashed))
            body_items.append(text_lines((xa + xc) / 2, y - 7, [label], "t-msg"))
            y += 38
        elif k == "note":
            _, a, c, lines = it
            xa, xc = xs[a], xs[c]
            half = max((max(xa, xc) - min(xa, xc)) / 2 + 70, 6.4 * max(len(t) for t in lines) / 2 + 12)
            mid = (xa + xc) / 2
            lft, rgt = mid - half, mid + half
            h = 10 + 14 * len(lines)
            body_items.append(f'<rect x="{lft}" y="{y - 12}" width="{rgt - lft}" height="{h}" rx="4" class="note"/>')
            body_items.append(text_lines((lft + rgt) / 2, y + 3, lines, "t-note"))
            y += h + 18
        elif k == "frame":
            _, label, a, c = it
            d = 10 * len(frames)
            frames.append({"label": label, "l": xs[a] - 92 + d, "r": xs[c] + 92 - d, "top": y - 8, "else": []})
            y += 34
        elif k == "else":
            frames[-1]["else"].append((y - 10, it[1]))
            y += 30
        elif k == "end":
            f = frames.pop()
            h = y - f["top"] - 8
            s = f'<rect x="{f["l"]}" y="{f["top"]}" width="{f["r"] - f["l"]}" height="{h}" class="frame"/>'
            tw = 12 + 6.6 * len(f["label"])
            s += (f'<path d="M{f["l"]},{f["top"]} h{tw} v12 l-8,8 h{-(tw - 8)} z" class="frame-tab"/>'
                  f'<text x="{f["l"] + 6}" y="{f["top"] + 14}" class="t-frame">{e(f["label"])}</text>')
            for ey, el in f["else"]:
                s += (f'<line x1="{f["l"]}" y1="{ey}" x2="{f["r"]}" y2="{ey}" class="frame-sep"/>'
                      f'<text x="{f["l"] + 6}" y="{ey + 14}" class="t-frame">{e(el)}</text>')
            body_items.insert(0, s)
            y += 10
    H = y + 10
    head = ""
    for name, sub in parts:
        x = xs[name]
        head += f'<line x1="{x}" y1="56" x2="{x}" y2="{H - 6}" class="lifeline"/>'
        head += f'<rect x="{x - 80}" y="10" width="160" height="46" rx="6" class="seq-head"/>'
        head += text_lines(x, 30, [name], "t-title seq-head-t")
        head += text_lines(x, 46, [sub], "t-kind seq-head-t")
    return svg(W, H, head + "".join(body_items), title, min(W, 820))


def seq_klines():
    parts = [("CandleChart", "React"), ("Vite", "proxy :5173"), ("get_klines", "FastAPI"),
             ("PostgreSQL", "tabla candles")]
    items = [
        ("frame", "al montar y cada 10 s", "CandleChart", "PostgreSQL"),
        ("msg", "CandleChart", "Vite", "GET /api/klines?limit=500 | 2", False),
        ("msg", "Vite", "get_klines", "reenvía a localhost:8000", False),
        ("msg", "get_klines", "PostgreSQL", "SELECT … ORDER BY open_time DESC LIMIT n", False),
        ("msg", "PostgreSQL", "get_klines", "filas Candle (Decimal, TIMESTAMPTZ)", True),
        ("msg", "get_klines", "get_klines", "reversed() → ASC; Decimal → float; time en s", False),
        ("msg", "get_klines", "CandleChart", "200 list[CandleOut]  (puede ser [])", True),
        ("frame", "alt [lastTime null]", "CandleChart", "Vite"),
        ("msg", "CandleChart", "CandleChart", "setData(500 velas)", False),
        ("else", "[ya hay historia]"),
        ("msg", "CandleChart", "CandleChart", "update() con velas ≥ lastTime", False),
        ("else", "[respuesta vacía]"),
        ("msg", "CandleChart", "CandleChart", "aviso \"No candles for … yet\"", False),
        ("end",),
        ("end",),
    ]
    return sequence(parts, items, width=900, title="Secuencia de GET /api/klines")


def seq_ticker():
    parts = [("Binance", "ticker/24hr"), ("Worker", "app.ingest.ticker"), ("Redis", "redis:7"),
             ("get_ticker", "FastAPI"), ("App.jsx", "React")]
    items = [
        ("frame", "loop cada 2 s (worker)", "Binance", "Redis"),
        ("msg", "Worker", "Binance", "GET /api/v3/ticker/24hr?symbol=BTCUSDT", False),
        ("frame", "alt [200]", "Binance", "Redis"),
        ("msg", "Binance", "Worker", "{lastPrice, priceChangePercent, …}", True),
        ("msg", "Worker", "Redis", "SET ticker:BTCUSDT <json propio> EX 10", False),
        ("else", "[429 / 418]"),
        ("note", "Worker", "Worker", ["sleep(Retry-After, 60 s por defecto)"]),
        ("else", "[otro error HTTP, red o Redis]"),
        ("note", "Worker", "Worker", ["print y sigue en la próxima vuelta"]),
        ("end",),
        ("end",),
        ("frame", "loop cada 2 s (navegador)", "Redis", "App.jsx"),
        ("msg", "App.jsx", "get_ticker", "GET /api/ticker?symbol=BTCUSDT", False),
        ("msg", "get_ticker", "Redis", "GET ticker:BTCUSDT", False),
        ("frame", "alt [clave presente]", "Redis", "App.jsx"),
        ("msg", "Redis", "get_ticker", "json", True),
        ("msg", "get_ticker", "App.jsx", "200 Ticker → precio en verde/rojo", True),
        ("else", "[clave expirada: nil]"),
        ("msg", "Redis", "get_ticker", "nil", True),
        ("msg", "get_ticker", "App.jsx", "503 → último precio en gris · stale", True),
        ("end",),
        ("end",),
    ]
    return sequence(parts, items, title="Secuencia del ticker")


def seq_ingest():
    parts = [("Operador", "docker compose exec"), ("candles.py", "ingest_latest / backfill"),
             ("Binance", "/api/v3/klines"), ("PostgreSQL", "tabla candles")]
    items = [
        ("msg", "Operador", "candles.py", "ingest_latest() o backfill(start)", False),
        ("frame", "loop por página (backfill: endTime = más antigua − 1)", "candles.py", "PostgreSQL"),
        ("frame", "loop hasta 5 intentos (fetch_klines)", "candles.py", "Binance"),
        ("msg", "candles.py", "Binance", "GET klines?symbol&interval&limit[&endTime]", False),
        ("frame", "alt [200]", "candles.py", "Binance"),
        ("msg", "Binance", "candles.py", "array de arrays → sale del loop", True),
        ("else", "[429]"),
        ("note", "candles.py", "candles.py", ["espera Retry-After o 1, 2, 4, 8 s"]),
        ("else", "[418]"),
        ("note", "candles.py", "candles.py", ["RuntimeError inmediato (sin reintento)"]),
        ("end",),
        ("end",),
        ("msg", "candles.py", "candles.py", "descarta vela en curso; to_rows → Decimal, UTC", False),
        ("msg", "candles.py", "PostgreSQL", "INSERT … ON CONFLICT (symbol, interval, open_time) DO UPDATE", False),
        ("end",),
        ("msg", "candles.py", "Operador", "n filas enviadas al upsert", True),
    ]
    return sequence(parts, items, title="Secuencia de la ingesta de velas")


# ---------- página ----------
CSS = """
:root{
  --bg:#f7f8fa;--surface:#ffffff;--surface-2:#eef1f5;--text:#1b1f27;--muted:#5b6474;
  --border:#d7dce4;--accent:#1168bd;--line:#4a5363;--code-bg:#eef1f5;
  --ok:#1f7a4d;--warn:#9a5b00;--err:#b42318;
  --person:#08427b;--system:#1168bd;--container:#438dd5;--component:#85bbf0;--ext:#8a8f98;--db:#2f6fb0;
  --on-dark:#ffffff;--on-light:#0b2a4a;--note:#fff6d6;--note-text:#4a3b00;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#11141a;--surface:#181c24;--surface-2:#20252f;--text:#e6e9ef;--muted:#9aa3b2;
    --border:#2e3440;--accent:#6aa9ec;--line:#aeb6c4;--code-bg:#20252f;
    --ok:#4cc38a;--warn:#e0a84a;--err:#f07366;
    --person:#0b4d8f;--system:#1868b8;--container:#3a7fc4;--component:#8cbcee;--ext:#5d636d;--db:#2b67a3;
    --note:#3a3420;--note-text:#f2e3b0;
  }
}
:root[data-theme="dark"]{
  --bg:#11141a;--surface:#181c24;--surface-2:#20252f;--text:#e6e9ef;--muted:#9aa3b2;
  --border:#2e3440;--accent:#6aa9ec;--line:#aeb6c4;--code-bg:#20252f;
  --ok:#4cc38a;--warn:#e0a84a;--err:#f07366;
  --person:#0b4d8f;--system:#1868b8;--container:#3a7fc4;--component:#8cbcee;--ext:#5d636d;--db:#2b67a3;
  --note:#3a3420;--note-text:#f2e3b0;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--text);
  font:15px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:32px 16px 64px}
header h1{font-size:28px;margin:0 0 6px;letter-spacing:-.01em}
header p{margin:0;color:var(--muted);max-width:760px}
.meta{font-size:13px;color:var(--muted);margin-top:10px}
nav{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--border);
  margin:24px -16px 0;padding:10px 16px;display:flex;gap:6px 16px;flex-wrap:wrap;font-size:14px}
nav a{color:var(--muted);text-decoration:none}
nav a:hover{color:var(--accent)}
section{margin-top:44px;scroll-margin-top:60px}
h2{font-size:21px;margin:0 0 4px}
h3{font-size:16px;margin:26px 0 8px}
.lead{color:var(--muted);margin:0 0 16px;max-width:820px}
code{font:13px/1.5 ui-monospace,"SF Mono",Menlo,Consolas,monospace;background:var(--code-bg);
  padding:1px 5px;border-radius:4px}
pre{background:var(--code-bg);border:1px solid var(--border);border-radius:8px;padding:12px 14px;
  overflow-x:auto;margin:8px 0 0}
pre code{background:none;padding:0}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px 20px;margin-top:14px}
.diagram{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px;
  overflow-x:auto;margin-top:12px}
.diagram svg{display:block;width:100%;height:auto;margin:0 auto}
table{border-collapse:collapse;width:100%;font-size:14px;margin-top:8px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--border);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:13px}
.tbl{overflow-x:auto}
.endpoint{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.endpoint h3{margin:0}
.verb{font:600 12px/1 ui-monospace,Menlo,monospace;background:var(--accent);color:var(--bg);
  padding:5px 8px;border-radius:5px}
.pill{font-size:12px;border:1px solid var(--border);border-radius:99px;padding:2px 9px;color:var(--muted)}
.s2{color:var(--ok);font-weight:600}.s4{color:var(--warn);font-weight:600}.s5{color:var(--err);font-weight:600}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.legend{display:flex;flex-wrap:wrap;gap:8px 18px;font-size:13px;color:var(--muted);margin-top:10px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.sw{width:14px;height:14px;border-radius:3px;display:inline-block}
.callout{border-left:3px solid var(--accent);padding:6px 12px;background:var(--surface-2);border-radius:0 6px 6px 0;
  margin-top:12px;font-size:14px}
/* SVG */
.c4-person{fill:var(--person)}.c4-system{fill:var(--system)}.c4-container{fill:var(--container)}
.c4-component{fill:var(--component)}.c4-ext{fill:var(--ext)}.c4-db{fill:var(--db)}
.cyl-top{stroke:rgba(255,255,255,.35);stroke-width:1}
.c4-person-t,.c4-system-t,.c4-container-t,.c4-ext-t,.c4-db-t{fill:var(--on-dark)}
.c4-component-t{fill:var(--on-light)}
.t-title{font:600 14px system-ui,sans-serif}
.t-kind{font:11px system-ui,sans-serif;opacity:.85}
.t-desc{font:11.5px system-ui,sans-serif}
.boundary{fill:none;stroke:var(--line);stroke-width:1.3;stroke-dasharray:7 5}
.t-boundary{font:600 12px system-ui,sans-serif;fill:var(--muted)}
.rel{fill:none;stroke:var(--line);stroke-width:1.4}
.rel.dashed{stroke-dasharray:5 4}
.arrowhead{fill:var(--line)}
.t-rel,.t-msg{font:11.5px system-ui,sans-serif;fill:var(--text);paint-order:stroke;stroke:var(--surface);
  stroke-width:4px;stroke-linejoin:round}
.t-msg{font-family:ui-monospace,Menlo,monospace;font-size:11px}
.lifeline{stroke:var(--border);stroke-width:1.2;stroke-dasharray:4 4}
.seq-head{fill:var(--surface-2);stroke:var(--border)}
.seq-head-t{fill:var(--text)}
.note{fill:var(--note);stroke:none}
.t-note{font:11.5px system-ui,sans-serif;fill:var(--note-text)}
.frame{fill:none;stroke:var(--muted);stroke-width:1}
.frame-tab{fill:var(--surface-2);stroke:var(--muted);stroke-width:1}
.frame-sep{stroke:var(--muted);stroke-width:1;stroke-dasharray:5 4}
.t-frame{font:600 11px system-ui,sans-serif;fill:var(--muted)}
@media (max-width:640px){header h1{font-size:23px}.card{padding:14px}}
"""

LEGEND = """<div class="legend">
<span><i class="sw" style="background:var(--person)"></i>Persona</span>
<span><i class="sw" style="background:var(--system)"></i>Sistema</span>
<span><i class="sw" style="background:var(--container)"></i>Contenedor</span>
<span><i class="sw" style="background:var(--component)"></i>Componente</span>
<span><i class="sw" style="background:var(--db)"></i>Almacén de datos</span>
<span><i class="sw" style="background:var(--ext)"></i>Externo</span>
<span>- - - Límite del sistema / contenedor</span>
</div>"""

html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crypto Tracker API</title>
<meta name="description" content="Arquitectura, diagramas C4, endpoints y flujos de la API de Crypto Tracker.">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>Crypto Tracker API</h1>
  <p>Arquitectura, diagramas C4 (contexto, contenedores y componentes), referencia de endpoints,
  flujos de secuencia y modelo de datos del backend FastAPI.</p>
  <div class="meta">Estado: fase 3a (ticker vía Redis) · Actualizado: 2026-09-26 · Fuente de verdad:
  <code>backend/app/</code>, <code>infra/docker-compose.yml</code></div>
</header>

<nav>
  <a href="#resumen">Resumen</a><a href="#c4-contexto">C4 · Contexto</a><a href="#c4-contenedores">C4 · Contenedores</a>
  <a href="#c4-componentes">C4 · Componentes</a><a href="#endpoints">Endpoints</a><a href="#secuencias">Secuencias</a>
  <a href="#datos">Modelo de datos</a><a href="#errores">Errores</a><a href="#config">Configuración</a>
</nav>

<section id="resumen">
  <h2>Resumen</h2>
  <p class="lead">La API es de solo lectura y <strong>nunca llama a Binance</strong>: las velas salen de PostgreSQL
  y el precio en vivo de Redis. Hablar con Binance es trabajo de dos procesos aparte: la ingesta de velas
  (a mano hoy, Airflow en la fase 4) y el worker del ticker.</p>
  <div class="grid2">
    <div class="card"><strong>Velas</strong><br>Binance → <code>app.ingest.candles</code> → upsert idempotente en
      <code>candles</code> → <code>GET /api/klines</code> → gráfico (refresco 10 s).</div>
    <div class="card"><strong>Ticker</strong><br>Binance → worker cada 2 s → <code>SET ticker:BTCUSDT EX 10</code> →
      <code>GET /api/ticker</code> → cabecera (refresco 2 s, <code>503</code> si la clave expiró).</div>
  </div>
</section>

<section id="c4-contexto">
  <h2>C4 · Nivel 1: Contexto</h2>
  <p class="lead">Quién usa el sistema y con qué sistemas externos habla. Binance es la única dependencia externa;
  se usa <code>data-api.binance.vision</code> porque no requiere API key ni tiene bloqueos geográficos.</p>
  {c4_context()}
  {LEGEND}
</section>

<section id="c4-contenedores">
  <h2>C4 · Nivel 2: Contenedores</h2>
  <p class="lead">Las piezas desplegables. Todo corre en Docker Compose excepto el frontend, que corre en el host
  con <code>npm run dev</code>. La ingesta de velas no es un servicio: se ejecuta dentro del contenedor
  <code>backend</code> con <code>docker compose exec</code>.</p>
  {c4_containers()}
  {LEGEND}
  <div class="tbl"><table>
    <tr><th>Contenedor</th><th>Tecnología</th><th>Servicio Compose</th><th>Puerto en host</th><th>Notas</th></tr>
    <tr><td>Frontend SPA</td><td>React 19, Vite 8, lightweight-charts</td><td>— (host)</td><td>5173</td><td>Proxy <code>/api</code> → <code>localhost:8000</code>; sin CORS en desarrollo</td></tr>
    <tr><td>API</td><td>FastAPI, uvicorn <code>--reload</code></td><td><code>backend</code></td><td><code>BACKEND_PORT</code> (8000)</td><td>Depende de postgres y redis <em>healthy</em></td></tr>
    <tr><td>Worker del ticker</td><td>Python 3.12, HTTPX sync, redis-py</td><td><code>worker</code></td><td>—</td><td><code>python -u -m app.ingest.ticker</code>, <code>init: true</code>, sin <code>--reload</code></td></tr>
    <tr><td>Ingesta de velas</td><td>Python 3.12, HTTPX sync, SQLAlchemy</td><td>(dentro de <code>backend</code>)</td><td>—</td><td>Importable por Airflow en la fase 4</td></tr>
    <tr><td>PostgreSQL</td><td>postgres:16</td><td><code>postgres</code></td><td><code>POSTGRES_PORT</code> (5433)</td><td>Volumen <code>postgres_data</code>; esquema por Alembic</td></tr>
    <tr><td>Redis</td><td>redis:7</td><td><code>redis</code></td><td>—</td><td>Sin volumen: datos efímeros</td></tr>
  </table></div>
</section>

<section id="c4-componentes">
  <h2>C4 · Nivel 3: Componentes de la API</h2>
  <p class="lead">Módulos de <code>backend/app</code> y cómo dependen entre sí. Las dos rutas son funciones
  <code>def</code> síncronas: FastAPI las ejecuta en un threadpool, así que no bloquean el event loop.</p>
  {c4_components()}
  {LEGEND}
  <div class="tbl"><table>
    <tr><th>Componente</th><th>Archivo</th><th>Responsabilidad</th></tr>
    <tr><td>FastAPI app</td><td><code>app/main.py</code></td><td>Crea la app, registra <code>market_router</code>, CORS desde <code>settings.cors_origins_list</code>, <code>GET /health</code>.</td></tr>
    <tr><td>Router de mercado</td><td><code>app/api/market.py</code></td><td><code>APIRouter(prefix="/api")</code> con <code>get_ticker</code> y <code>get_klines</code>.</td></tr>
    <tr><td>Esquemas</td><td><code>app/api/schemas.py</code></td><td><code>CandleOut</code> y <code>Ticker</code>: el contrato JSON con el frontend.</td></tr>
    <tr><td>Configuración</td><td><code>app/core/config.py</code></td><td><code>Settings</code> (pydantic-settings) desde variables de entorno. <code>database_url</code> y <code>redis_url</code> son obligatorias.</td></tr>
    <tr><td>Sesión SQL</td><td><code>app/db/session.py</code></td><td><code>engine</code> con <code>pool_pre_ping</code> y <code>SessionLocal</code>.</td></tr>
    <tr><td>Modelo ORM</td><td><code>app/db/models.py</code></td><td><code>Base</code> declarativa y <code>Candle</code> (tabla <code>candles</code>).</td></tr>
    <tr><td>Caché</td><td><code>app/db/cache.py</code></td><td>Cliente <code>cache</code> (uno por proceso, <code>decode_responses=True</code>) y <code>ticker_key</code>.</td></tr>
  </table></div>
</section>

<section id="endpoints">
  <h2>Endpoints</h2>
  <p class="lead">Base: <code>http://localhost:8000</code> (o relativa desde el frontend vía el proxy de Vite).
  Documentación interactiva generada por FastAPI en <code>/docs</code>.</p>

  <div class="card">
    <div class="endpoint"><span class="verb">GET</span><h3><code>/api/klines</code></h3><span class="pill">PostgreSQL</span><span class="pill">sync</span></div>
    <p>Últimas velas cerradas de un símbolo e intervalo, en orden ascendente de tiempo.</p>
    <div class="tbl"><table>
      <tr><th>Parámetro</th><th>Tipo</th><th>Por defecto</th><th>Regla</th></tr>
      <tr><td><code>symbol</code></td><td>str</td><td><code>BTCUSDT</code></td><td>Filtra <code>candles.symbol</code></td></tr>
      <tr><td><code>interval</code></td><td>str</td><td><code>1m</code></td><td>Filtra <code>candles.interval</code>; solo hay datos de los intervalos ingeridos</td></tr>
      <tr><td><code>limit</code></td><td>int</td><td><code>500</code></td><td><code>≤ 1000</code>; si no, <code>422</code></td></tr>
    </table></div>
    <div class="tbl"><table>
      <tr><th>Status</th><th>Cuándo</th><th>Cuerpo</th></tr>
      <tr><td class="s2">200</td><td>Siempre que la consulta funcione, aunque no haya filas</td><td><code>list[CandleOut]</code>, puede ser <code>[]</code></td></tr>
      <tr><td class="s4">422</td><td><code>limit &gt; 1000</code> o no entero</td><td>Error de validación de FastAPI</td></tr>
      <tr><td class="s5">500</td><td>PostgreSQL inaccesible</td><td>Error interno</td></tr>
    </table></div>
<pre><code>GET /api/klines?symbol=BTCUSDT&amp;interval=1m&amp;limit=2
200 [
  {{"time":1789000020,"open":65012.1,"high":65030.0,"low":64998.5,"close":65020.4,"volume":12.531}},
  {{"time":1789000080,"open":65020.4,"high":65041.2,"low":65010.0,"close":65038.7,"volume":9.874}}
]</code></pre>
    <p class="callout"><code>time</code> va en <strong>segundos</strong> UNIX (UTC), no milisegundos: es lo que espera
    lightweight-charts. Los precios se guardan como <code>NUMERIC</code> y se envían como <code>float</code>:
    la precisión importa donde se guarda, no donde se pinta.</p>
  </div>

  <div class="card">
    <div class="endpoint"><span class="verb">GET</span><h3><code>/api/ticker</code></h3><span class="pill">Redis</span><span class="pill">sync</span></div>
    <p>Último precio y variación de 24 h, tal como lo dejó el worker en Redis.</p>
    <div class="tbl"><table>
      <tr><th>Parámetro</th><th>Tipo</th><th>Por defecto</th><th>Regla</th></tr>
      <tr><td><code>symbol</code></td><td>str</td><td><code>BTCUSDT</code></td><td>Solo tiene datos el símbolo que sigue el worker (<code>BTCUSDT</code>)</td></tr>
    </table></div>
    <div class="tbl"><table>
      <tr><th>Status</th><th>Cuándo</th><th>Cuerpo</th></tr>
      <tr><td class="s2">200</td><td>La clave <code>ticker:&lt;symbol&gt;</code> existe</td><td><code>Ticker</code></td></tr>
      <tr><td class="s5">503</td><td>La clave no existe: worker caído, atrasado más de 10 s o símbolo no seguido</td><td><code>{{"detail":"No recent ticker for &lt;symbol&gt;"}}</code></td></tr>
      <tr><td class="s5">500</td><td>Redis inaccesible (<code>redis.RedisError</code> sin capturar)</td><td>Error interno</td></tr>
    </table></div>
<pre><code>GET /api/ticker?symbol=BTCUSDT
200 {{"symbol":"BTCUSDT","last_price":65020.4,"price_change_percent":1.234}}
503 {{"detail":"No recent ticker for BTCUSDT"}}</code></pre>
    <p class="callout">Ante cualquier error el frontend conserva el último precio, lo pinta en gris y agrega
    <code>· stale</code>. La marca desaparece con el siguiente <code>200</code>.</p>
  </div>

  <div class="card">
    <div class="endpoint"><span class="verb">GET</span><h3><code>/health</code></h3><span class="pill">sin dependencias</span></div>
    <p>Comprueba que el proceso responde. No toca PostgreSQL ni Redis.</p>
<pre><code>200 {{"status":"ok"}}</code></pre>
  </div>

  <h3>Esquemas de respuesta</h3>
  <div class="grid2">
    <div class="card"><strong><code>CandleOut</code></strong>
      <table><tr><th>Campo</th><th>Tipo</th><th>Origen</th></tr>
      <tr><td><code>time</code></td><td>int</td><td><code>int(open_time.timestamp())</code></td></tr>
      <tr><td><code>open</code>, <code>high</code>, <code>low</code>, <code>close</code></td><td>float</td><td><code>NUMERIC(20,8)</code></td></tr>
      <tr><td><code>volume</code></td><td>float</td><td><code>NUMERIC(30,8)</code></td></tr></table></div>
    <div class="card"><strong><code>Ticker</code></strong>
      <table><tr><th>Campo</th><th>Tipo</th><th>Origen (Binance)</th></tr>
      <tr><td><code>symbol</code></td><td>str</td><td><code>symbol</code></td></tr>
      <tr><td><code>last_price</code></td><td>float</td><td><code>lastPrice</code></td></tr>
      <tr><td><code>price_change_percent</code></td><td>float</td><td><code>priceChangePercent</code></td></tr></table></div>
  </div>
</section>

<section id="secuencias">
  <h2>Secuencias</h2>
  <h3>Lectura de velas: <code>GET /api/klines</code></h3>
  <p class="lead">La primera carga pide 500 velas; los refrescos solo las 2 últimas para cubrir el cruce de minuto.
  El gráfico descarta velas más antiguas que la última pintada porque <code>update()</code> no acepta retroceder.</p>
  {seq_klines()}
  <h3>Ticker: escritura del worker y lectura de la API</h3>
  <p class="lead">Dos bucles independientes que solo se tocan en Redis. El TTL de 10 s con escrituras cada 2 s
  tolera un par de fallos; si el worker muere, la clave expira y la API responde <code>503</code> en vez de un precio viejo.</p>
  {seq_ticker()}
  <h3>Ingesta de velas (fuera de la API)</h3>
  <p class="lead">No forma parte del ciclo de peticiones, pero es lo que llena la tabla que lee <code>/api/klines</code>.
  Correrla dos veces deja la base igual que correrla una vez.</p>
  {seq_ingest()}
</section>

<section id="datos">
  <h2>Modelo de datos</h2>
  <div class="grid2">
    <div class="card"><strong>PostgreSQL · tabla <code>candles</code></strong>
      <table><tr><th>Columna</th><th>Tipo</th><th>Nota</th></tr>
      <tr><td><code>symbol</code></td><td><code>VARCHAR(20)</code></td><td>PK</td></tr>
      <tr><td><code>interval</code></td><td><code>VARCHAR(10)</code></td><td>PK</td></tr>
      <tr><td><code>open_time</code></td><td><code>TIMESTAMPTZ</code></td><td>PK, siempre UTC</td></tr>
      <tr><td><code>open</code>, <code>high</code>, <code>low</code>, <code>close</code></td><td><code>NUMERIC(20,8)</code></td><td></td></tr>
      <tr><td><code>volume</code></td><td><code>NUMERIC(30,8)</code></td><td></td></tr></table>
      <p class="callout">PK compuesta natural <code>(symbol, interval, open_time)</code>: es la identidad de la vela y el
      objetivo del <code>ON CONFLICT</code> del upsert. Migración: <code>alembic/versions/92e1536d2411_*</code>.</p></div>
    <div class="card"><strong>Redis · clave <code>ticker:&lt;SYMBOL&gt;</code></strong>
      <table><tr><th>Aspecto</th><th>Valor</th></tr>
      <tr><td>Tipo</td><td>String con JSON</td></tr>
      <tr><td>Escribe</td><td>Worker, cada 2 s (<code>POLL_SECONDS</code>)</td></tr>
      <tr><td>TTL</td><td>10 s (<code>TTL_SECONDS</code>)</td></tr>
      <tr><td>Lee</td><td><code>get_ticker</code></td></tr></table>
<pre><code>{{"symbol": "BTCUSDT",
 "last_price": "65020.40000000",
 "price_change_percent": "1.234"}}</code></pre>
      <p class="callout">Formato propio, no el de Binance: en la fase 3b cambia la fuente (WebSocket) y la API no se entera.</p></div>
  </div>
</section>

<section id="errores">
  <h2>Manejo de errores de Binance</h2>
  <p class="lead">La API no ve errores de Binance: solo los procesos que la llaman. Límite: 6.000 de peso por minuto
  por IP; el worker consume ~60/min.</p>
  <div class="tbl"><table>
    <tr><th>Situación</th><th>Ingesta de velas (<code>fetch_klines</code>)</th><th>Worker del ticker</th></tr>
    <tr><td class="s2">2xx</td><td>Devuelve el JSON</td><td>Escribe en Redis</td></tr>
    <tr><td class="s4">400</td><td>Excepción, sin reintento</td><td>Lo imprime y sigue</td></tr>
    <tr><td class="s4">429</td><td>Reintenta hasta 5 veces: <code>Retry-After</code> o 1, 2, 4, 8 s</td><td>Duerme <code>Retry-After</code> (60 s por defecto)</td></tr>
    <tr><td class="s5">418</td><td><code>RuntimeError</code> inmediato: reintentar alarga el baneo</td><td>Duerme <code>Retry-After</code> (60 s por defecto)</td></tr>
    <tr><td class="s5">Otro 4xx/5xx</td><td>Excepción, sin reintento</td><td>Lo imprime y sigue</td></tr>
    <tr><td>Timeout / red</td><td>&gt; 10 s: excepción</td><td>&gt; 5 s: lo imprime y sigue</td></tr>
  </table></div>
</section>

<section id="config">
  <h2>Configuración</h2>
  <p class="lead"><code>Settings</code> lee variables de entorno (inyectadas por Compose desde <code>.env</code>).
  Faltar <code>DATABASE_URL</code> o <code>REDIS_URL</code> impide importar la app; por eso el worker recibe
  <code>DATABASE_URL</code> aunque no use Postgres.</p>
  <div class="tbl"><table>
    <tr><th>Variable</th><th>Campo</th><th>Usan</th><th>Ejemplo</th></tr>
    <tr><td><code>DATABASE_URL</code></td><td><code>database_url</code> (obligatorio)</td><td>API, ingesta, Alembic, worker (solo por import)</td><td><code>postgresql+psycopg://crypto:crypto@postgres:5432/crypto_tracker</code></td></tr>
    <tr><td><code>REDIS_URL</code></td><td><code>redis_url</code> (obligatorio)</td><td>API, worker</td><td><code>redis://redis:6379/0</code></td></tr>
    <tr><td><code>BINANCE_REST_URL</code></td><td><code>binance_rest_url</code></td><td>Ingesta, worker</td><td><code>https://data-api.binance.vision</code></td></tr>
    <tr><td><code>CORS_ORIGINS</code></td><td><code>cors_origins</code></td><td>API</td><td><code>http://localhost:5173</code></td></tr>
    <tr><td><code>BACKEND_PORT</code></td><td>—</td><td>Compose</td><td><code>8000</code></td></tr>
  </table></div>
</section>
</div>
<script>
// Respeta un tema forzado por ?theme=light|dark
try {{ const t = new URLSearchParams(location.search).get("theme");
  if (t === "light" || t === "dark") document.documentElement.dataset.theme = t; }} catch (_) {{}}
</script>
</body>
</html>
"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"escrito {OUT} ({len(html)} bytes)")
