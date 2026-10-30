from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request


_tentativas: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def limitar_tentativas(request: Request, operacao: str, limite: int, janela_segundos: int) -> None:
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
