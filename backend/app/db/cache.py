import redis

from app.core.config import settings

# Como el engine de SQLAlchemy: un cliente por proceso, con su propio pool
cache = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def ticker_key(symbol: str) -> str:
    return f"ticker:{symbol}"