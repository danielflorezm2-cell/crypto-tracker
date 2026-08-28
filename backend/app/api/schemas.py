from pydantic import BaseModel


class Candle(BaseModel):
    # segundos UNIX, no milisegundos: es lo que espera lightweight-charts
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class Ticker(BaseModel):
    symbol: str
    last_price: float
    price_change_percent: float