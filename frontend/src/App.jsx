import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL;

export default function App() {
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((res) => res.json())
      .then((data) => setStatus(data.status))
      // Sin este catch, un fallo de CORS deja la promesa rechazada en silencio
      // y la UI se queda en "loading" para siempre sin ninguna pista.
      .catch(() => setStatus("unreachable"));
  }, []);

  return <h1>Backend: {status}</h1>;
}