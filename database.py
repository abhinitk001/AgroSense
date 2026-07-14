from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# ======================================================
# DATABASE CONFIGURATION
# ======================================================

DB_USER = "root"
DB_PASSWORD = "1234"
DB_HOST = "localhost"
DB_PORT = "3306"
DB_NAME = "agrosense"

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{1234}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ======================================================
# CREATE DATABASE ENGINE
# ======================================================

engine = create_engine(
    DATABASE_URL,

    # Shows SQL queries in terminal
    echo=True,

    # Prevents MySQL timeout errors
    pool_pre_ping=True,

    # Recycles old connections
    pool_recycle=3600
)

# ======================================================
# SESSION FACTORY
# ======================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ======================================================
# BASE MODEL
# ======================================================

Base = declarative_base()

# ======================================================
# DATABASE DEPENDENCY
# ======================================================

def get_db():
    """
    Creates a new database session for every request.

    FastAPI automatically closes it
    after the request finishes.
    """

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()