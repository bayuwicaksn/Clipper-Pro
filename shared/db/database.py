from sqlmodel import SQLModel, create_engine, Session
from ..config import settings
from .models import Job  # Ensure models are imported for SQLModel to recognize them

db_url = settings.DATABASE_URL or "sqlite:///clipper.db"

# Handle Postgres connection strings (fix for SQLAlchemy/Heroku/Supabase)
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Connect args (only for SQLite)
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    db_url, 
    echo=settings.DEBUG, 
    connect_args=connect_args
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
