from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

from app.core.config import settings


def _build_database_url() -> str:
    """Build SQLAlchemy database URL based on settings.

    - If DB_TYPE is 'postgres', use Postgres URL from env (host, port, name, user, password).
    - Otherwise, fall back to SQLite dev.db in the project root.
    """

    db_type = os.getenv("DB_TYPE", "sqlite").lower()

    if db_type == "postgres":
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "postgres")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        name = os.getenv("POSTGRES_DB", "hiresence")
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"

    # Default: SQLite file in current working directory
    return "sqlite:///./dev.db"


SQLALCHEMY_DATABASE_URL = _build_database_url()


# SQLite needs check_same_thread=False; others should not pass this.
connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
