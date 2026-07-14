import os
from dotenv import load_dotenv

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DB_USER = os.getenv("MYSQLUSER")
DB_PASSWORD = os.getenv("MYSQLPASSWORD")
DB_HOST = os.getenv("MYSQLHOST")
DB_PORT = os.getenv("MYSQLPORT")
DB_NAME = os.getenv("MYSQLDATABASE")

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
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