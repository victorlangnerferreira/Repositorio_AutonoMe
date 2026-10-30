import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("AUTONOME_DATABASE_URL", "sqlite:///./AutonoMe.db")

# O "engine" é quem sabe conversar com o banco de verdade (abrir conexão, etc.)
# connect_args só é necessário pro SQLite (evita erro de thread); pode remover
# se/quando migrar pra MySQL.
engine_options = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, **engine_options)

# Cada requisição vai pedir uma sessão nova pra conversar com o banco.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base é a classe da qual TODOS os models (Usuario, Foto...) precisam herdar.
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
