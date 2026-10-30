"""
Script para criar todas as tabelas do banco AutonoMe.db a partir dos models
definidos em autonome_api/models.py.

Uso:
    python create_db.py
"""

from autonome_api.database import Base, engine
from autonome_api import models  # noqa: F401  (necessário para registrar os models na Base)


def main():
    print("Criando tabelas no banco de dados...")
    Base.metadata.create_all(bind=engine)
    print("Tabelas criadas com sucesso em AutonoMe.db!")


if __name__ == "__main__":
    main()