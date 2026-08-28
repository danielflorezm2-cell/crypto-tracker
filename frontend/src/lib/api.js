const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function get(path, params) {
  const url = new URL(path, BASE);
  url.search = new URLSearchParams(params).toString();

  const response = await fetch(url);

  // fetch NO lanza en 4xx/5xx: solo falla si la red se cae. Sin este check,
  // un 429 de Binance llegaría a la UI como si fuera JSON válido.
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json();
}

export const getKlines = (symbol, interval, limit) =>
  get("/api/klines", { symbol, interval, limit });

export const getTicker = (symbol) => get("/api/ticker", { symbol });