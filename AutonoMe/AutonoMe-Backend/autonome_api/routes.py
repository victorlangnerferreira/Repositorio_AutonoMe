from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
import bcrypt
from datetime import datetime, timedelta, timezone
import re
import secrets
import hashlib
import hmac
import json
import os
import string
from zoneinfo import ZoneInfo

from autonome_api.auth import exigir_login, exigir_proprio_usuario, criar_token
from autonome_api.database import get_db
from autonome_api.models import Usuario, UsuarioInativo, VerificacaoEmail, Profissional, Favorito, Notificacao, Contratacao, Profissao, Categoria, Mensagem, NotaPedido, TokenRevogado
from autonome_api.schemas import LoginSchema, DesativarContaSchema, CodigoEmailSchema, ConfirmarCadastroSchema, CadastroPFSchema, CadastroPJSchema, MensagemChatSchema, NotaPedidoSchema, ContratacaoSchema, LoginResponseSchema, CadastroResponseSchema, UsuarioPerfilSchema, UsuarioEdicaoSchema, ProfissoesProfissionalSchema
from autonome_api.security import limitar_tentativas
from autonome_api.email_service import enviar_codigo_email

router = APIRouter()
PASTA_FOTOS_PERFIL = Path(__file__).resolve().parent.parent / "uploads" / "fotos_perfil"


def _hash_codigo_email(email: str, operacao: str, codigo: str) -> str:
    segredo = os.getenv("AUTONOME_SECRET_KEY", "").encode()
    conteudo = f"{email.lower()}:{operacao}:{codigo}".encode()
    return hmac.new(segredo, conteudo, hashlib.sha256).hexdigest()


def _solicitar_codigo_email(db: Session, email: str, operacao: str, id_usuario: int | None = None, dados_pendentes: dict | None = None) -> None:
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    db.query(VerificacaoEmail).filter(VerificacaoEmail.expira_em <= agora).delete(synchronize_session=False)
    db.query(VerificacaoEmail).filter(
        VerificacaoEmail.email == email,
        VerificacaoEmail.operacao == operacao,
    ).delete(synchronize_session=False)

    alfabeto = string.ascii_uppercase + string.digits
    codigo = "".join(secrets.choice(alfabeto) for _ in range(6))
    verificacao = VerificacaoEmail(
        email=email,
        operacao=operacao,
        codigo_hash=_hash_codigo_email(email, operacao, codigo),
        dados_pendentes=json.dumps(dados_pendentes) if dados_pendentes else None,
        id_usuario=id_usuario,
        expira_em=agora + timedelta(minutes=10),
    )
    db.add(verificacao)
    db.commit()
    try:
        enviar_codigo_email(email, codigo, operacao)
    except Exception:
        db.delete(verificacao)
        db.commit()
        raise HTTPException(status_code=503, detail="Não foi possível enviar o código. Confira as configurações de e-mail no .env.") from None


def _validar_codigo_email(db: Session, email: str, operacao: str, codigo: str, id_usuario: int | None = None) -> VerificacaoEmail:
    verificacao = db.query(VerificacaoEmail).filter(
        VerificacaoEmail.email == email,
        VerificacaoEmail.operacao == operacao,
    ).first()
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    if not verificacao or verificacao.expira_em <= agora or (id_usuario is not None and verificacao.id_usuario != id_usuario):
        if verificacao and verificacao.expira_em <= agora:
            db.delete(verificacao)
            db.commit()
        raise HTTPException(status_code=400, detail="Código inválido ou expirado. Solicite outro código.")
    if verificacao.tentativas >= 5:
        db.delete(verificacao)
        db.commit()
        raise HTTPException(status_code=429, detail="Limite de tentativas atingido. Solicite outro código.")
    esperado = _hash_codigo_email(email, operacao, codigo)
    if not hmac.compare_digest(verificacao.codigo_hash, esperado):
        verificacao.tentativas += 1
        if verificacao.tentativas >= 5:
            db.delete(verificacao)
        db.commit()
        raise HTTPException(status_code=400, detail="Código inválido ou expirado. Confira o código enviado por e-mail.")
    return verificacao

def validar_cpf(cpf: str) -> bool:
    cpf = re.sub(r"\D", "", cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    soma1 = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = 0 if (soma1 * 10) % 11 in (10, 11) else (soma1 * 10) % 11
    if d1 != int(cpf[9]):
        return False
    soma2 = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = 0 if (soma2 * 10) % 11 in (10, 11) else (soma2 * 10) % 11
    return d2 == int(cpf[10])

def validar_cnpj(cnpj: str) -> bool:
    cnpj = re.sub(r"\D", "", cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    r1 = sum(int(cnpj[i]) * p1[i] for i in range(12)) % 11
    d1 = 0 if r1 < 2 else 11 - r1
    if d1 != int(cnpj[12]):
        return False
    p2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    r2 = sum(int(cnpj[i]) * p2[i] for i in range(13)) % 11
    d2 = 0 if r2 < 2 else 11 - r2
    return d2 == int(cnpj[13])

@router.post("/login", response_model=LoginResponseSchema)
def login(dados: LoginSchema, request: Request, db: Session = Depends(get_db)):
    limitar_tentativas(request, "login", limite=5, janela_segundos=900)
    email = str(dados.email).strip().lower()
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario or not usuario.ativo or not bcrypt.checkpw(dados.senha.encode(), usuario.senha.encode()):
        raise HTTPException(status_code=401, detail="E-mail, senha inválidos ou conta inativa")
    
    redirecionar_para = "homepage.html"

    token = criar_token(usuario)
    return {
        "token": token,
        "usuario": {"id": usuario.id, "nome": usuario.nome, "email": usuario.email, "tipo": usuario.tipo},
        "redirecionar_para": redirecionar_para
    }

@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    jti = request.state.token_jti
    agora_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    db.query(TokenRevogado).filter(TokenRevogado.expira_em <= agora_utc).delete(synchronize_session=False)
    if not db.query(TokenRevogado.jti).filter(TokenRevogado.jti == jti).first():
        db.add(TokenRevogado(jti=jti, id_usuario=usuario.id, expira_em=request.state.token_expira_em))
        db.commit()
    return {"ok": True}


@router.post("/usuarios/me/desativar/solicitar-codigo")
def solicitar_codigo_desativacao(dados: DesativarContaSchema, request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    limitar_tentativas(request, "codigo_desativacao", limite=5, janela_segundos=3600)
    if not bcrypt.checkpw(dados.senha.encode(), usuario.senha.encode()):
        raise HTTPException(status_code=400, detail="A senha informada está incorreta.")
    _solicitar_codigo_email(db, usuario.email, "desativacao", id_usuario=usuario.id)
    return {"ok": True, "mensagem": "Código enviado ao e-mail da sua conta."}


@router.post("/usuarios/me/desativar/confirmar-codigo")
def confirmar_desativacao(dados: CodigoEmailSchema, request: Request, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    limitar_tentativas(request, "confirmar_desativacao", limite=10, janela_segundos=3600)
    verificacao = _validar_codigo_email(db, usuario.email, "desativacao", dados.codigo, id_usuario=usuario.id)
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    registro = db.query(UsuarioInativo).filter(UsuarioInativo.id_usuario == usuario.id).first()
    if not registro:
        registro = UsuarioInativo(
            id_usuario=usuario.id,
            nome=usuario.nome,
            email=usuario.email,
            documento=usuario.documento,
            tipo_pessoa=usuario.tipo_pessoa,
            telefone=usuario.telefone,
            tipo=usuario.tipo,
            foto=usuario.foto,
            data_cadastro=usuario.data_cadastro,
            data_desativacao=agora,
        )
        db.add(registro)
    db.delete(verificacao)
    usuario.ativo = False
    db.commit()
    return {"ok": True, "mensagem": "Conta desativada."}


@router.post("/usuarios/me/desativar")
def desativar_sem_codigo(_dados: DesativarContaSchema):
    raise HTTPException(status_code=410, detail="Solicite e confirme o código enviado ao seu e-mail antes de desativar a conta.")


@router.post("/cadastro_pf/solicitar-codigo")
def solicitar_codigo_cadastro(dados: CadastroPFSchema, request: Request, db: Session = Depends(get_db)):
    limitar_tentativas(request, "cadastro", limite=5, janela_segundos=3600)
    if dados.tipo not in (None, "cliente", "profissional"):
        raise HTTPException(status_code=400, detail="Tipo de conta inválido")
    documento = re.sub(r"\D", "", dados.cpf)
    if not validar_cpf(documento):
        raise HTTPException(status_code=400, detail="CPF inválido")
    email = str(dados.email).strip().lower()
    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    if db.query(Usuario).filter(Usuario.documento == documento).first():
        raise HTTPException(status_code=400, detail="CPF já cadastrado")

    dados_pendentes = {
        "nome": dados.nome.strip(),
        "email": email,
        "documento": documento,
        "telefone": dados.telefone,
        "senha_hash": bcrypt.hashpw(dados.senha.encode(), bcrypt.gensalt()).decode(),
        "tipo": dados.tipo or "cliente",
    }
    _solicitar_codigo_email(db, email, "cadastro", dados_pendentes=dados_pendentes)
    return {"ok": True, "mensagem": "Código de verificação enviado ao seu e-mail."}


@router.post("/cadastro_pf/confirmar-codigo", response_model=CadastroResponseSchema)
def confirmar_cadastro(dados: ConfirmarCadastroSchema, request: Request, db: Session = Depends(get_db)):
    limitar_tentativas(request, "confirmar_cadastro", limite=10, janela_segundos=3600)
    email = str(dados.email).strip().lower()
    verificacao = _validar_codigo_email(db, email, "cadastro", dados.codigo)
    cadastro = json.loads(verificacao.dados_pendentes or "{}")
    documento = cadastro.get("documento", "")
    if db.query(Usuario).filter(Usuario.email == email).first():
        db.delete(verificacao)
        db.commit()
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    if not validar_cpf(documento) or db.query(Usuario).filter(Usuario.documento == documento).first():
        db.delete(verificacao)
        db.commit()
        raise HTTPException(status_code=400, detail="CPF inválido ou já cadastrado")

    novo_usuario = Usuario(
        nome=cadastro["nome"], email=email, documento=documento, tipo_pessoa="PF",
        telefone=cadastro["telefone"], senha=cadastro["senha_hash"], tipo=cadastro["tipo"],
    )
    db.add(novo_usuario)
    db.flush()
    if novo_usuario.tipo == "profissional":
        db.add(Profissional(id_usuario=novo_usuario.id))
    db.delete(verificacao)
    db.commit()
    return {"id": novo_usuario.id, "nome": novo_usuario.nome, "email": novo_usuario.email, "tipo": novo_usuario.tipo}


@router.post("/cadastro_pf")
def cadastro_sem_codigo(_dados: CadastroPFSchema):
    raise HTTPException(status_code=410, detail="Confirme o código enviado ao seu e-mail para concluir o cadastro.")


@router.post("/cadastro_pj/solicitar-codigo")
def solicitar_codigo_cadastro_pj(dados: CadastroPJSchema, request: Request, db: Session = Depends(get_db)):
    limitar_tentativas(request, "cadastro", limite=5, janela_segundos=3600)
    if dados.tipo not in (None, "cliente", "profissional"):
        raise HTTPException(status_code=400, detail="Tipo de conta inválido")
    documento = re.sub(r"\D", "", dados.cnpj or "")
    if documento and not validar_cnpj(documento):
        raise HTTPException(status_code=400, detail="CNPJ inválido")
    email = str(dados.email).strip().lower()
    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    if documento and db.query(Usuario).filter(Usuario.documento == documento).first():
        raise HTTPException(status_code=400, detail="CNPJ já cadastrado")

    dados_pendentes = {
        "nome": dados.nome.strip(),
        "email": email,
        "documento": documento or f"AUTO{secrets.token_hex(7)}",
        "telefone": dados.telefone,
        "senha_hash": bcrypt.hashpw(dados.senha.encode(), bcrypt.gensalt()).decode(),
        "tipo": dados.tipo or "cliente",
        "tipo_pessoa": "PJ",
    }
    _solicitar_codigo_email(db, email, "cadastro", dados_pendentes=dados_pendentes)
    return {"ok": True, "mensagem": "Código de verificação enviado ao seu e-mail."}


@router.post("/cadastro_pj/confirmar-codigo", response_model=CadastroResponseSchema)
def confirmar_cadastro_pj(dados: ConfirmarCadastroSchema, request: Request, db: Session = Depends(get_db)):
    limitar_tentativas(request, "confirmar_cadastro", limite=10, janela_segundos=3600)
    email = str(dados.email).strip().lower()
    verificacao = _validar_codigo_email(db, email, "cadastro", dados.codigo)
    cadastro = json.loads(verificacao.dados_pendentes or "{}")
    documento = cadastro.get("documento", "")
    if db.query(Usuario).filter(Usuario.email == email).first():
        db.delete(verificacao)
        db.commit()
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    if not documento.startswith("AUTO") and (not validar_cnpj(documento) or db.query(Usuario).filter(Usuario.documento == documento).first()):
        db.delete(verificacao)
        db.commit()
        raise HTTPException(status_code=400, detail="CNPJ inválido ou já cadastrado")

    novo_usuario = Usuario(
        nome=cadastro["nome"], email=email, documento=documento, tipo_pessoa="PJ",
        telefone=cadastro["telefone"], senha=cadastro["senha_hash"], tipo=cadastro["tipo"],
    )
    db.add(novo_usuario)
    db.flush()
    if novo_usuario.tipo == "profissional":
        db.add(Profissional(id_usuario=novo_usuario.id))
    db.delete(verificacao)
    db.commit()
    return {"id": novo_usuario.id, "nome": novo_usuario.nome, "email": novo_usuario.email, "tipo": novo_usuario.tipo}


@router.post("/cadastro_pj")
def cadastro_pj_sem_codigo(_dados: CadastroPJSchema):
    raise HTTPException(status_code=410, detail="Confirme o código enviado ao seu e-mail para concluir o cadastro.")


@router.get("/categorias")
def listar_categorias(db: Session = Depends(get_db)):
    categorias = db.query(Categoria).all()
    resultado = []
    for c in categorias:
        profissoes_lista = [{"id_profissao": p.id, "nome": p.nome} for p in c.profissoes]
        resultado.append({
            "id_categoria": c.id,
            "nome": c.nome,
            "descricao": c.descricao,
            "imagem": c.imagem,
            "profissoes": profissoes_lista
        })
    return resultado

@router.get("/categorias/{id_categoria}/profissoes")
def listar_profissoes_categoria(id_categoria: int, db: Session = Depends(get_db)):
    profissoes = db.query(Profissao).filter(Profissao.id_categoria == id_categoria).all()
    return [{"id_profissao": p.id, "nome": p.nome, "id_categoria": p.id_categoria} for p in profissoes]

@router.get("/profissionais")
def listar_profissionais(profissao: int = None, db: Session = Depends(get_db)):
    query = db.query(Profissional)
    if profissao:
        query = query.join(Profissional.profissoes).filter(Profissao.id == profissao)
    profissionais = query.all()
    resultado = []
    for p in profissionais:
        profissoes_nomes = [prof.nome for prof in p.profissoes] if p.profissoes else []
        primeira_prof = p.profissoes[0] if p.profissoes else None
        id_prof_val = primeira_prof.id if primeira_prof else None
        cat_nome = primeira_prof.categoria_rel.nome if (primeira_prof and primeira_prof.categoria_rel) else None
        resultado.append({
            "id_profissional": p.id,
            "id_usuario": p.id_usuario,
            "nome": p.usuario_rel.nome if p.usuario_rel else "Profissional",
            "foto": f"/usuarios/{p.id_usuario}/foto" if p.usuario_rel and p.usuario_rel.foto else None,
            "media_avaliacao": float(p.media_avaliacao or 0),
            "preco_hora": float(p.preco_hora or 0),
            "experiencia": p.experiencia,
            "id_profissao": id_prof_val,
            "categoria": cat_nome,
            "profissoes": profissoes_nomes,
            "descricao": p.descricao
        })
    return resultado


@router.get("/profissionais/me/profissoes")
def minhas_profissoes(db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    profissional = db.query(Profissional).filter(Profissional.id_usuario == usuario.id).first()
    if usuario.tipo != "profissional" or not profissional:
        raise HTTPException(status_code=403, detail="Esta configuração é exclusiva para contas profissionais.")
    return [profissao.id for profissao in profissional.profissoes]


@router.put("/profissionais/me/profissoes")
def atualizar_minhas_profissoes(dados: ProfissoesProfissionalSchema, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    profissional = db.query(Profissional).filter(Profissional.id_usuario == usuario.id).first()
    if usuario.tipo != "profissional" or not profissional:
        raise HTTPException(status_code=403, detail="Esta configuração é exclusiva para contas profissionais.")
    profissoes = db.query(Profissao).filter(Profissao.id.in_(dados.ids_profissoes)).all()
    if len(profissoes) != len(dados.ids_profissoes):
        raise HTTPException(status_code=400, detail="Uma ou mais profissões não existem no catálogo.")
    profissional.profissoes = profissoes
    db.commit()
    return {"ids_profissoes": [profissao.id for profissao in profissional.profissoes]}

@router.get("/favoritos/{id_cliente}")
def listar_favoritos(id_cliente: int, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    exigir_proprio_usuario(usuario, id_cliente)
    favs = db.query(Favorito).filter(Favorito.id_cliente == id_cliente).all()
    resultado = []
    for f in favs:
        p = f.profissional_rel
        if p and p.usuario_rel:
            profissoes_nomes = [prof.nome for prof in p.profissoes] if p.profissoes else []
            resultado.append({
                "id_favorito": f.id,
                "id_profissional": p.id,
                "id_usuario": p.id_usuario,
                "nome": p.usuario_rel.nome,
                "media_avaliacao": float(p.media_avaliacao or 0),
                "profissoes": profissoes_nomes
            })
    return resultado

@router.get("/notificacoes/{id_usuario}")
def listar_notificacoes(id_usuario: int, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    exigir_proprio_usuario(usuario, id_usuario)
    notifs = db.query(Notificacao).filter(Notificacao.id_usuario == id_usuario).order_by(Notificacao.data_envio.desc()).all()
    return [{
        "id_notificacao": n.id,
        "titulo": n.titulo,
        "mensagem": n.mensagem,
        "visualizada": n.visualizada,
        "data_envio": n.data_envio.isoformat() if n.data_envio else None
    } for n in notifs]

@router.patch("/notificacoes/{id_notificacao}/visualizada")
def marcar_notificacao_visualizada(id_notificacao: int, usuario_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    exigir_proprio_usuario(usuario, usuario_id)
    notificacao = db.query(Notificacao).filter(Notificacao.id == id_notificacao, Notificacao.id_usuario == usuario_id).first()
    if not notificacao:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    notificacao.visualizada = True
    db.commit()
    return {"ok": True}


@router.patch("/notificacoes/{id_usuario}/visualizadas")
def marcar_todas_notificacoes_visualizadas(id_usuario: int, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    exigir_proprio_usuario(usuario, id_usuario)
    db.query(Notificacao).filter(Notificacao.id_usuario == id_usuario).update(
        {Notificacao.visualizada: True}, synchronize_session=False
    )
    db.commit()
    return {"ok": True}


@router.delete("/notificacoes/{id_usuario}")
def excluir_notificacoes(id_usuario: int, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    exigir_proprio_usuario(usuario, id_usuario)
    db.query(Notificacao).filter(Notificacao.id_usuario == id_usuario).delete(synchronize_session=False)
    db.commit()
    return {"ok": True}


@router.get("/contratacoes/{id_usuario}")
def listar_contratacoes(id_usuario: int, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    exigir_proprio_usuario(usuario, id_usuario)
    contratacoes = db.query(Contratacao).outerjoin(
        Profissional, Contratacao.id_profissional == Profissional.id
    ).filter(
        (Contratacao.id_cliente == id_usuario) |
        (Profissional.id_usuario == id_usuario)
    ).order_by(Contratacao.id.desc()).all()
    resultado = []
    for c in contratacoes:
        prof_nome = c.profissional_rel.usuario_rel.nome if (c.profissional_rel and c.profissional_rel.usuario_rel) else "Profissional"
        cliente_nome = c.cliente_rel.nome if c.cliente_rel else "Cliente"
        resultado.append({
            "id_contratacao": c.id,
            "profissional_nome": prof_nome,
            "cliente_nome": cliente_nome,
            "data_servico": c.data_servico.isoformat() if c.data_servico else None,
            "status": c.status,
            "valor": float(c.valor or 0),
            "id_cliente": c.id_cliente,
            "id_profissional": c.id_profissional,
            "profissional_usuario_id": c.profissional_rel.id_usuario if c.profissional_rel else None,
        })
    return resultado


@router.get("/usuarios")
def listar_usuarios(exceto: int = None, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    exceto = usuario.id
    query = db.query(Usuario).filter(Usuario.ativo.is_(True))
    if exceto is not None:
        query = query.filter(Usuario.id != exceto)
    return [{"id": u.id, "nome": u.nome, "tipo": u.tipo} for u in query.order_by(Usuario.nome).all()]


@router.patch("/usuarios/me", response_model=CadastroResponseSchema)
def atualizar_perfil(dados: UsuarioEdicaoSchema, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    email = str(dados.email).strip().lower()
    nome = dados.nome.strip()

    if len(nome) < 2:
        raise HTTPException(status_code=400, detail="Informe um nome válido")
    if db.query(Usuario).filter(Usuario.email == email, Usuario.id != usuario.id).first():
        raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado")

    usuario.nome = nome
    usuario.email = email
    usuario.telefone = (dados.telefone or "").strip() or None
    db.commit()
    db.refresh(usuario)
    return {"id": usuario.id, "nome": usuario.nome, "email": usuario.email, "tipo": usuario.tipo}


@router.post("/usuarios/me/foto")
async def atualizar_foto_perfil(arquivo: UploadFile = File(...), db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    conteudo = await arquivo.read(5 * 1024 * 1024 + 1)
    if len(conteudo) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="A foto deve ter no máximo 5 MB.")

    try:
        with Image.open(BytesIO(conteudo)) as imagem:
            if imagem.format not in ("JPEG", "PNG", "WEBP"):
                raise HTTPException(status_code=415, detail="Use uma imagem JPG, PNG ou WEBP.")
            if imagem.width * imagem.height > 20_000_000:
                raise HTTPException(status_code=413, detail="A resolução da foto é muito grande.")
            imagem = ImageOps.exif_transpose(imagem).convert("RGB")
            imagem.thumbnail((512, 512))
            PASTA_FOTOS_PERFIL.mkdir(parents=True, exist_ok=True)
            nome_arquivo = f"{usuario.id}.jpg"
            imagem.save(PASTA_FOTOS_PERFIL / nome_arquivo, format="JPEG", quality=85, optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(status_code=400, detail="Não foi possível abrir essa imagem.")

    usuario.foto = nome_arquivo
    db.commit()
    return {"foto": f"/usuarios/{usuario.id}/foto"}


@router.get("/usuarios/{id_usuario}/foto")
def obter_foto_perfil(id_usuario: int, db: Session = Depends(get_db)):
    perfil = db.query(Usuario).filter(Usuario.id == id_usuario, Usuario.ativo.is_(True)).first()
    if not perfil or not perfil.foto:
        raise HTTPException(status_code=404, detail="Foto não encontrada.")
    caminho = PASTA_FOTOS_PERFIL / Path(perfil.foto).name
    if not caminho.is_file():
        raise HTTPException(status_code=404, detail="Foto não encontrada.")
    return FileResponse(caminho, media_type="image/jpeg")


@router.get("/usuarios/{id_usuario}", response_model=UsuarioPerfilSchema)
def obter_usuario(id_usuario: int, db: Session = Depends(get_db), usuario_logado: Usuario = Depends(exigir_login)):
    perfil = db.query(Usuario).filter(Usuario.id == id_usuario, Usuario.ativo.is_(True)).first()
    if not perfil:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    profissional = perfil.profissional_rel
    return {
        "id": perfil.id,
        "nome": perfil.nome,
        "foto": f"/usuarios/{perfil.id}/foto" if perfil.foto else None,
        "email": perfil.email if usuario_logado.id == perfil.id else None,
        "telefone": perfil.telefone if usuario_logado.id == perfil.id else None,
        "tipo": perfil.tipo,
        "tipo_pessoa": perfil.tipo_pessoa,
        "data_cadastro": perfil.data_cadastro,
        "ocupacao": ", ".join(p.nome for p in profissional.profissoes) if profissional and profissional.profissoes else ("Profissional" if profissional else "Cliente / Contratante"),
        "sobre": profissional.descricao if profissional and profissional.descricao else "Usuário cadastrado na plataforma AutonoMe.",
        "preco_hora": float(profissional.preco_hora or 0) if profissional else None,
        "experiencia": profissional.experiencia if profissional else None,
    }


def _thread_chat(usuario_a: int, usuario_b: int) -> str:
    if usuario_a == usuario_b:
        raise HTTPException(status_code=400, detail="Escolha outro usuário para conversar")
    return f"chat:{min(usuario_a, usuario_b)}:{max(usuario_a, usuario_b)}"


@router.get("/chats/{usuario_a}/{usuario_b}/mensagens")
def listar_mensagens_chat(usuario_a: int, usuario_b: int, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    if usuario.id not in (usuario_a, usuario_b):
        raise HTTPException(status_code=403, detail="Acesso não autorizado a esta conversa")
    thread = _thread_chat(usuario_a, usuario_b)
    usuarios = db.query(Usuario.id).filter(Usuario.id.in_([usuario_a, usuario_b])).count()
    if usuarios != 2:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    mensagens = db.query(Mensagem).filter(Mensagem.assunto == thread).order_by(Mensagem.data_envio, Mensagem.id).all()
    return [{
        "id": m.id,
        "usuario_id": m.id_usuario,
        "nome": m.usuario_rel.nome if m.usuario_rel else "Usuário",
        "texto": m.mensagem,
        "data_envio": m.data_envio.isoformat() if m.data_envio else None,
    } for m in mensagens]


@router.post("/chats/{usuario_a}/{usuario_b}/mensagens")
def enviar_mensagem_chat(usuario_a: int, usuario_b: int, dados: MensagemChatSchema, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    thread = _thread_chat(usuario_a, usuario_b)
    if usuario.id not in (usuario_a, usuario_b) or dados.usuario_id != usuario.id:
        raise HTTPException(status_code=403, detail="Remetente não pertence à conversa")
    remetente = db.query(Usuario).filter(Usuario.id == dados.usuario_id, Usuario.ativo.is_(True)).first()
    destinatario_id = usuario_b if dados.usuario_id == usuario_a else usuario_a
    destinatario = db.query(Usuario).filter(Usuario.id == destinatario_id, Usuario.ativo.is_(True)).first()
    if not remetente or not destinatario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    mensagem = Mensagem(assunto=thread, mensagem=dados.texto.strip(), id_usuario=remetente.id)
    db.add(mensagem)
    db.add(Notificacao(id_usuario=destinatario.id, titulo=f"Mensagem de {remetente.nome}", mensagem=dados.texto.strip()))
    db.commit()
    db.refresh(mensagem)
    return {"id": mensagem.id, "usuario_id": remetente.id, "nome": remetente.nome, "texto": mensagem.mensagem, "data_envio": mensagem.data_envio.isoformat() if mensagem.data_envio else None}


@router.post("/contratacoes")
def criar_contratacao(dados: ContratacaoSchema, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    exigir_proprio_usuario(usuario, dados.cliente_id)
    cliente = db.query(Usuario).filter(Usuario.id == dados.cliente_id, Usuario.ativo.is_(True)).first()
    profissional = db.query(Profissional).filter(Profissional.id == dados.profissional_id).first()
    if (not cliente or cliente.tipo != "cliente" or not profissional
            or not profissional.usuario_rel or not profissional.usuario_rel.ativo
            or profissional.id_usuario == cliente.id):
        raise HTTPException(status_code=400, detail="Cliente ou profissional inválido")
    try:
        data_servico = datetime.strptime(dados.data_servico, "%Y-%m-%d").date()
        horario = datetime.strptime(dados.horario, "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Data ou horário inválido")
    if data_servico < datetime.now(ZoneInfo("America/Sao_Paulo")).date():
        raise HTTPException(status_code=400, detail="A data do serviÃ§o nÃ£o pode estar no passado")
    contratacao = Contratacao(
        id_cliente=cliente.id,
        id_profissional=profissional.id,
        data_servico=data_servico,
        horario=horario,
        endereco=dados.endereco.strip(),
        valor=profissional.preco_hora or 0,
        status="pendente",
    )
    db.add(contratacao)
    db.flush()
    db.add(Notificacao(id_usuario=profissional.id_usuario, titulo="Novo pedido de serviço", mensagem=f"{cliente.nome} solicitou um serviço para {data_servico.isoformat()} às {horario.strftime('%H:%M')}.") )
    db.commit()
    db.refresh(contratacao)
    return {"id_contratacao": contratacao.id, "status": contratacao.status}


def _contratacao_participante(db: Session, id_contratacao: int, id_usuario: int):
    contrato = db.query(Contratacao).outerjoin(
        Profissional, Contratacao.id_profissional == Profissional.id
    ).filter(
        Contratacao.id == id_contratacao,
        ((Contratacao.id_cliente == id_usuario) | (Profissional.id_usuario == id_usuario)),
    ).first()
    if not contrato:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return contrato


@router.get("/contratacoes/{id_contratacao}/notas")
def listar_notas_pedido(id_contratacao: int, usuario_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    exigir_proprio_usuario(usuario, usuario_id)
    _contratacao_participante(db, id_contratacao, usuario_id)
    notas = db.query(NotaPedido).filter(NotaPedido.id_contratacao == id_contratacao).order_by(NotaPedido.data_criacao).all()
    return [{"id": n.id, "usuario_id": n.id_usuario, "texto": n.texto, "data_criacao": n.data_criacao.isoformat()} for n in notas]


@router.post("/contratacoes/{id_contratacao}/notas")
def criar_nota_pedido(id_contratacao: int, dados: NotaPedidoSchema, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    exigir_proprio_usuario(usuario, dados.usuario_id)
    _contratacao_participante(db, id_contratacao, dados.usuario_id)
    nota = NotaPedido(id_contratacao=id_contratacao, id_usuario=dados.usuario_id, texto=dados.texto.strip())
    db.add(nota)
    db.commit()
    db.refresh(nota)
    return {"id": nota.id, "usuario_id": nota.id_usuario, "texto": nota.texto, "data_criacao": nota.data_criacao.isoformat()}


@router.get("/relatorios/{id_usuario}")
def relatorio_usuario(id_usuario: int, db: Session = Depends(get_db), usuario: Usuario = Depends(exigir_login)):
    exigir_proprio_usuario(usuario, id_usuario)
    contratacoes = listar_contratacoes(id_usuario, db, usuario)
    notificacoes_nao_lidas = db.query(Notificacao).filter(Notificacao.id_usuario == id_usuario, Notificacao.visualizada.is_(False)).count()
    mensagens = db.query(Mensagem).filter(Mensagem.id_usuario == id_usuario, Mensagem.assunto.like("chat:%")).count()
    return {
        "total_pedidos": len(contratacoes),
        "pendentes": sum(1 for c in contratacoes if c["status"] == "pendente"),
        "concluidos": sum(1 for c in contratacoes if c["status"] == "concluido"),
        "valor_total": sum(c["valor"] for c in contratacoes),
        "notificacoes_nao_lidas": notificacoes_nao_lidas,
        "mensagens_enviadas": mensagens,
    }
