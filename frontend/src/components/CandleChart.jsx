import { useEffect, useRef } from "react";
import { createChart, CandlestickSeries } from "lightweight-charts";
import { getKlines } from "../lib/api";

const REFRESH_MS = 10_000;

export default function CandleChart({ symbol = "BTCUSDT", interval = "1m" }) {
  const containerRef = useRef(null);

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
    let timer = null;

    getKlines(symbol, interval, 500)
      .then((candles) => {
        if (cancelled) return;
        series.setData(candles);

        timer = setInterval(() => {
          getKlines(symbol, interval, 2)
            .then((latest) => {
              if (cancelled) return;
              // update() reemplaza si el timestamp ya existe y añade si es
              // nuevo. Por eso la vela en curso se redibuja en su sitio
              // en vez de duplicarse, y sin resetear zoom ni scroll.
              latest.forEach((candle) => series.update(candle));
            })
            .catch(console.error);
        }, REFRESH_MS);
      })
      .catch(console.error);

    return () => {
      cancelled = true;
      clearInterval(timer);
      chart.remove();
    };
  }, [symbol, interval]);

  return <div ref={containerRef} style={{ height: 400, width: "100%" }} />;
}