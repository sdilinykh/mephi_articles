import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .models import Base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://mephi:mephi@localhost:5432/mephi_journals",
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE article ADD COLUMN IF NOT EXISTS funding_section_found BOOLEAN DEFAULT FALSE"))

def reset_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
