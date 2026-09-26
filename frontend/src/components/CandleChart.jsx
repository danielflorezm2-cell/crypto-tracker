import { useEffect, useRef, useState } from "react";
import { createChart, CandlestickSeries } from "lightweight-charts";
import { getKlines } from "../lib/api";

const REFRESH_MS = 10_000;
const INITIAL_LIMIT = 500;

export default function CandleChart({ symbol = "BTCUSDT", interval = "1m" }) {
  const containerRef = useRef(null);
  const [empty, setEmpty] = useState(false);

  useEffect(() => {
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: { background: { color: "#131722" }, textColor: "#d1d4dc" },
      grid: { vertLines: { color: "#1e222d" }, horzLines: { color: "#1e222d" } },
      timeScale: { timeVisible: true },
    });
    const series = chart.addSeries(CandlestickSeries);

    // Evita que un fetch en vuelo escriba sobre un chart ya destruido
    let cancelled = false;
    // null = todavía no hay historia; el próximo tick intenta la carga completa
    let lastTime = null;

    const load = () => {
      const initial = lastTime === null;

      getKlines(symbol, interval, initial ? INITIAL_LIMIT : 2)
        .then((candles) => {
          if (cancelled) return;
          if (initial) setEmpty(candles.length === 0);
          if (candles.length === 0) return;

          if (initial) {
            series.setData(candles);
          } else {
            // update() no acepta retroceder en el tiempo: se saltea lo ya pintado
            candles.forEach((candle) => {
              if (candle.time >= lastTime) series.update(candle);
            });
          }
          lastTime = candles[candles.length - 1].time;
        })
        .catch(console.error);
    };

    load();
    const timer = setInterval(load, REFRESH_MS);

    return () => {
      cancelled = true;
      clearInterval(timer);
      chart.remove();
    };
  }, [symbol, interval]);

  return (
    <div style={{ position: "relative" }}>
      <div ref={containerRef} style={{ height: 400, width: "100%", isolation: "isolate" }} />
      {empty && (
        <p
          style={{
            position: "absolute",
            inset: 0,
            margin: 0,
            display: "grid",
            placeItems: "center",
            pointerEvents: "none",
          }}
        >
          No candles for {symbol} {interval} yet
        </p>
      )}
    </div>
  );
}