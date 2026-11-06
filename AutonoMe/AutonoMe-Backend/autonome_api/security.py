from collections import defaultdict, deque
import os
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request


_tentativas: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def limitar_tentativas(request: Request, operacao: str, limite: int, janela_segundos: int) -> None:
    # A opção de desenvolvimento só desativa o limite local por IP.
    # Em produção, o limite permanece ativo mesmo que a variável esteja definida.
    ambiente = os.getenv("AUTONOME_ENV", "development").strip().lower()
    limite_ativo = os.getenv("AUTONOME_RATE_LIMIT_ENABLED", "true").strip().lower() not in ("false", "0", "nao", "não")
    if ambiente != "production" and not limite_ativo:
        return

    agora = monotonic()
    ip = request.client.host if request.client else "unknown"
    chave = f"{operacao}:{ip}"
    with _lock:
        fila = _tentativas[chave]
        while fila and agora - fila[0] >= janela_segundos:
            fila.popleft()
        if len(fila) >= limite:
            espera = max(1, int(janela_segundos - (agora - fila[0])))
            raise HTTPException(
                status_code=429,
                detail="Muitas tentativas. Aguarde antes de tentar novamente.",
                headers={"Retry-After": str(espera)},
            )
        fila.append(agora)
