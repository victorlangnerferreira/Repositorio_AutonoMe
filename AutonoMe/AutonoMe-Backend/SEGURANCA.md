# Rodar o AutonoMe localmente

1. Entre na pasta `AutonoMe-Backend` e copie `.env.example` para `.env`.
2. Gere uma chave com `python -c "import secrets; print(secrets.token_hex(32))"` e cole o resultado em `AUTONOME_SECRET_KEY` no `.env`.
3. Instale as dependências com `pip install -r requirements.txt`.
4. Inicie a API com `uvicorn main:app --reload`.
5. Sirva `AutonoMe-Frontend` localmente na porta `5500`.

O `.env` mantém as configurações locais fora do Git. O banco continua sendo o arquivo SQLite `AutonoMe.db`; o `.gitignore` ignora esse arquivo e outros bancos locais.

## Variáveis do `.env`

- `AUTONOME_SECRET_KEY`: obrigatória; chave aleatória com pelo menos 32 caracteres.
- `AUTONOME_DATABASE_URL`: SQLite local, já preenchido no exemplo.
- `AUTONOME_ENV`: use `development` para carregar os dados de demonstração.
- `AUTONOME_CORS_ORIGINS`: endereços locais do frontend e da API.
