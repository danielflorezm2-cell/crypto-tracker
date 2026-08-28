import { useEffect, useState } from "react";
import CandleChart from "./components/CandleChart";
import { getTicker } from "./lib/api";

const SYMBOL = "BTCUSDT";

export default function App() {
  const [ticker, setTicker] = useState(null);

  useEffect(() => {
    let cancelled = false;

    const load = () =>
      getTicker(SYMBOL)
        .then((data) => {
          if (!cancelled) setTicker(data);
        })
        .catch(console.error);

    load();
    const timer = setInterval(load, 10_000);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const up = ticker && ticker.price_change_percent >= 0;

  return (
    <div style={{ padding: 24, minHeight: "100vh", background: "#131722", color: "#d1d4dc" }}>
      <h1 style={{ fontSize: 20, fontWeight: 500 }}>
        {SYMBOL}{" "}
        {ticker && (
          <span style={{ color: up ? "#26a69a" : "#ef5350" }}>
            {ticker.last_price} ({ticker.price_change_percent}%)
          </span>
        )}
      </h1>
      <CandleChart symbol={SYMBOL} interval="1m" />
    </div>
  );
}