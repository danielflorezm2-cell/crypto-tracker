from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# pool_pre_ping evita el "server closed the connection unexpectedly" cuando
# reinicias el contenedor de Postgres y el pool conserva conexiones muertas
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)