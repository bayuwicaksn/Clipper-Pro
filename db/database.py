from sqlmodel import SQLModel, create_engine, Session
from config import settings
from db.models import Job  # Ensure models are imported for SQLModel to recognize them

sqlite_url = settings.DATABASE_URL
engine = create_engine(sqlite_url, echo=settings.DEBUG, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
