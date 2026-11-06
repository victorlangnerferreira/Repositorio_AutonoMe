import os

from dotenv import load_dotenv

load_dotenv()

chave_jwt = os.getenv("AUTONOME_SECRET_KEY", "").strip()
if len(chave_jwt) < 32:
    raise RuntimeError(
        "AUTONOME_SECRET_KEY não configurada. Copie .env.example para .env e defina uma chave aleatória com pelo menos 32 caracteres. "
        "Gere uma com: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

from sqlalchemy import inspect

from autonome_api.database import Base, engine
from autonome_api.seed import executar_seed
from autonome_api.app import create_app


AMBIENTE = os.getenv("AUTONOME_ENV", "development").strip().lower()
Base.metadata.create_all(bind=engine)
if engine.dialect.name == "sqlite":
    colunas_usuario = {coluna["name"] for coluna in inspect(engine).get_columns("usuarios")}
    with engine.begin() as conexao:
        if "estado" not in colunas_usuario:
            conexao.exec_driver_sql("ALTER TABLE usuarios ADD COLUMN estado VARCHAR(2)")
        if "cidade" not in colunas_usuario:
            conexao.exec_driver_sql("ALTER TABLE usuarios ADD COLUMN cidade VARCHAR(100)")
        if "cadastro_configurado" not in colunas_usuario:
            conexao.exec_driver_sql("ALTER TABLE usuarios ADD COLUMN cadastro_configurado BOOLEAN NOT NULL DEFAULT 1")
        if "data_nascimento" not in colunas_usuario:
            conexao.exec_driver_sql("ALTER TABLE usuarios ADD COLUMN data_nascimento DATE")
        colunas_inativos = {coluna["name"] for coluna in inspect(engine).get_columns("usuarios_inativos")}
        if "data_nascimento" not in colunas_inativos:
            conexao.exec_driver_sql("ALTER TABLE usuarios_inativos ADD COLUMN data_nascimento DATE")
if AMBIENTE != "production":
    executar_seed()

app = create_app(AMBIENTE)
