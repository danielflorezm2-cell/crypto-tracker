import { useEffect, useRef } from "react";
import { createChart, CandlestickSeries } from "lightweight-charts";
import { getKlines } from "../lib/api";

const REFRESH_MS = 10_000;
const COLOMBIA_OFFSET = 5 * 60 * 60;

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
    let lastTime = null;
    getKlines(symbol, interval, 500)
      .then((candles) => {
        if (cancelled) return;
        series.setData(candles);
        lastTime = candles[candles.length - 1].time;
        console.log(lastTime);
        console.log(candles[candles.length - 1].time);

        timer = setInterval(() => {
          getKlines(symbol, interval, 2)
            .then((latest) => {
              if (cancelled) return;
                latest.forEach((candle) => {
                    // update() no acepta retroceder en el tiempo: la vela anterior
                    // ya está en la serie salvo justo al cruzar el cambio de minuto
                    if (candle.time < lastTime) return;
                    series.update(candle);
                    lastTime = candle.time;
                    })
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