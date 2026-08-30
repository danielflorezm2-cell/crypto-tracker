async function get(path, params) {
  const query = new URLSearchParams(params).toString();

  // Sin host: la URL es relativa al propio Vite, que hace de intermediario.
  const response = await fetch(`${path}?${query}`);

  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json();
}

export const getKlines = (symbol, interval, limit) =>
  get("/api/klines", { symbol, interval, limit });

export const getTicker = (symbol) => get("/api/ticker", { symbol });