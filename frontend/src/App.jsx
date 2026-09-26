import { useEffect, useState } from "react";
import CandleChart from "./components/CandleChart";
import { getTicker } from "./lib/api";

const SYMBOL = "BTCUSDT";
// Pedir más seguido que lo que el worker escribe no trae datos nuevos
const REFRESH_MS = 2_000;

export default function App() {
  const [ticker, setTicker] = useState(null);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const load = () =>
      getTicker(SYMBOL)
        .then((data) => {
          if (cancelled) return;
          setTicker(data);
          setStale(false);
        })
        .catch((error) => {
          // Se conserva el último precio, pero marcado como viejo
          if (!cancelled) setStale(true);
          console.error(error);
        });

    load();
    const timer = setInterval(load, REFRESH_MS);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const up = ticker && ticker.price_change_percent >= 0;
  const color = stale ? "#787b86" : up ? "#26a69a" : "#ef5350";

  return (
    <div style={{ padding: 24, minHeight: "100vh", background: "#131722", color: "#d1d4dc" }}>
      <h1 style={{ fontSize: 20, fontWeight: 500 }}>
        {SYMBOL}{" "}
        {ticker && (
          <span style={{ color }}>
            {ticker.last_price} ({ticker.price_change_percent}%)
            {stale && " · stale"}
          </span>
        )}
      </h1>
      <CandleChart symbol={SYMBOL} interval="1m" />
    </div>
  );
}