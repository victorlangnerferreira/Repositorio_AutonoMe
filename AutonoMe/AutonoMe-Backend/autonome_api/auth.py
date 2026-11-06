import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from autonome_api.database import get_db
from autonome_api.models import TokenRevogado, Usuario


_bearer = HTTPBearer(auto_error=False)


def _secret_key() -> str:
    secret = os.getenv("AUTONOME_SECRET_KEY", "")
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="Autenticação indisponível: configure AUTONOME_SECRET_KEY")
    return secret


def criar_token(usuario: Usuario) -> str:
    agora = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(usuario.id),
            "tipo": usuario.tipo,
            "jti": str(uuid.uuid4()),
            "iat": agora,
            "exp": agora + timedelta(hours=8),
        },
        _secret_key(),
        algorithm="HS256",
    )


def perfil_inicial_completo(usuario: Usuario) -> bool:
    if usuario.tipo not in ("cliente", "profissional"):
        return True
    if usuario.cadastro_configurado:
        return True
    if not usuario.estado or not usuario.cidade:
        return False
    if usuario.tipo == "profissional":
        profissional = usuario.profissional_rel
        return bool(
            profissional
            and profissional.preco_hora
            and profissional.preco_hora > 0
            and profissional.profissoes
        )
    return True


def exigir_login(
    request: Request,
    credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    if not credenciais or credenciais.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Autenticação necessária", headers={"WWW-Authenticate": "Bearer"})
    try:
        dados = jwt.decode(credenciais.credentials, _secret_key(), algorithms=["HS256"])
        usuario_id = int(dados["sub"])
        jti = dados["jti"]
        expira_em = datetime.fromtimestamp(int(dados["exp"]), timezone.utc).replace(tzinfo=None)
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido ou expirado", headers={"WWW-Authenticate": "Bearer"})

    usuario = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.ativo.is_(True)).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="Conta inativa ou inexistente", headers={"WWW-Authenticate": "Bearer"})
    if db.query(TokenRevogado.jti).filter(TokenRevogado.jti == jti).first():
        raise HTTPException(status_code=401, detail="Sessão encerrada", headers={"WWW-Authenticate": "Bearer"})
    if not perfil_inicial_completo(usuario) and request.url.path not in (
        "/usuarios/me/configuracao-inicial",
        "/logout",
    ):
        raise HTTPException(status_code=403, detail="Complete seu cadastro antes de continuar.")
    request.state.token_jti = jti
    request.state.token_expira_em = expira_em
    return usuario


def exigir_proprio_usuario(usuario: Usuario, usuario_id: int) -> None:
    if usuario.id != usuario_id:
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
