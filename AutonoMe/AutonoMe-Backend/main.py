import os

from dotenv import load_dotenv

load_dotenv()

chave_jwt = os.getenv("AUTONOME_SECRET_KEY", "").strip()
if len(chave_jwt) < 32:
    raise RuntimeError(
        "AUTONOME_SECRET_KEY não configurada. Copie .env.example para .env e defina uma chave aleatória com pelo menos 32 caracteres. "
        "Gere uma com: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

from autonome_api.database import Base, engine
from autonome_api.seed import executar_seed
from autonome_api.app import create_app


AMBIENTE = os.getenv("AUTONOME_ENV", "development").strip().lower()
Base.metadata.create_all(bind=engine)
if AMBIENTE != "production":
    executar_seed()

app = create_app(AMBIENTE)
