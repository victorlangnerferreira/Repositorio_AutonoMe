from sqlalchemy import Column, Integer, String, Text, Boolean, Date, Time, DateTime, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from autonome_api.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column("id_usuario", Integer, primary_key=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(120), nullable=False, unique=True)
    documento = Column(String(18), nullable=False, unique=True)
    data_nascimento = Column(Date)
    tipo_pessoa = Column(String(2), nullable=False, default="PF")
    telefone = Column(String(20))
    estado = Column(String(2))
    cidade = Column(String(100))
    cadastro_configurado = Column(Boolean, nullable=False, default=True)
    senha = Column(String(255), nullable=False)
    tipo = Column(String(20), default="cliente")
    foto = Column(String(255))
    data_cadastro = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    ativo = Column(Boolean, default=True)

    profissional_rel = relationship("Profissional", back_populates="usuario_rel", uselist=False)
    favoritos = relationship("Favorito", back_populates="cliente_rel")
    avaliacoes = relationship("Avaliacao", back_populates="cliente_rel")
    contratacoes = relationship("Contratacao", back_populates="cliente_rel")
    notificacoes = relationship("Notificacao", back_populates="usuario_rel")
    mensagens = relationship("Mensagem", back_populates="usuario_rel")
    configuracao_rel = relationship("Configuracao", back_populates="usuario_rel", uselist=False)


class UsuarioInativo(Base):
    __tablename__ = "usuarios_inativos"

    id = Column("id_registro_inativo", Integer, primary_key=True)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False, unique=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(120), nullable=False)
    documento = Column(String(18), nullable=False)
    data_nascimento = Column(Date)
    tipo_pessoa = Column(String(2), nullable=False)
    telefone = Column(String(20))
    tipo = Column(String(20), nullable=False)
    foto = Column(String(255))
    data_cadastro = Column(DateTime)
    data_desativacao = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class VerificacaoEmail(Base):
    __tablename__ = "verificacoes_email"
    __table_args__ = (UniqueConstraint("email", "operacao", name="uq_verificacao_email_operacao"),)

    id = Column(Integer, primary_key=True)
    email = Column(String(120), nullable=False, index=True)
    operacao = Column(String(20), nullable=False)
    codigo_hash = Column(String(64), nullable=False)
    dados_pendentes = Column(Text)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"))
    expira_em = Column(DateTime, nullable=False)
    tentativas = Column(Integer, nullable=False, default=0)
    criada_em = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class Categoria(Base):
    __tablename__ = "categorias"

    id = Column("id_categoria", Integer, primary_key=True)
    nome = Column(String, nullable=False)
    imagem = Column(String)
    descricao = Column(String)

    profissoes = relationship("Profissao", back_populates="categoria_rel")


class Profissao(Base):
    __tablename__ = "profissoes"

    id = Column("id_profissao", Integer, primary_key=True)
    nome = Column(String, nullable=False)

    id_categoria = Column(Integer, ForeignKey("categorias.id_categoria"), nullable=False)
    categoria_rel = relationship("Categoria", back_populates="profissoes")

    profissionais = relationship(
        "Profissional",
        secondary="profissional_profissao",
        back_populates="profissoes",
    )


class Profissional(Base):
    __tablename__ = "profissionais"

    id = Column("id_profissional", Integer, primary_key=True)
    descricao = Column(Text)
    experiencia = Column(String)
    preco_hora = Column(Numeric(10, 2))
    media_avaliacao = Column(Numeric(3, 2), default=0)

    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    usuario_rel = relationship("Usuario", back_populates="profissional_rel")

    profissoes = relationship(
        "Profissao",
        secondary="profissional_profissao",
        back_populates="profissionais",
    )
    favoritos = relationship("Favorito", back_populates="profissional_rel")
    avaliacoes = relationship("Avaliacao", back_populates="profissional_rel")
    contratacoes = relationship("Contratacao", back_populates="profissional_rel")
    disponibilidades = relationship("Disponibilidade", back_populates="profissional_rel", cascade="all, delete-orphan")


class ProfissionalProfissao(Base):
    __tablename__ = "profissional_profissao"

    id_profissional = Column(Integer, ForeignKey("profissionais.id_profissional"), primary_key=True)
    id_profissao = Column(Integer, ForeignKey("profissoes.id_profissao"), primary_key=True)


class Disponibilidade(Base):
    __tablename__ = "disponibilidades"
    __table_args__ = (UniqueConstraint("id_profissional", "dia_semana", "horario", name="uq_disponibilidade_profissional_dia_hora"),)

    id = Column(Integer, primary_key=True)
    id_profissional = Column(Integer, ForeignKey("profissionais.id_profissional"), nullable=False, index=True)
    dia_semana = Column(Integer, nullable=False)
    horario = Column(Time, nullable=False)

    profissional_rel = relationship("Profissional", back_populates="disponibilidades")


class Favorito(Base):
    __tablename__ = "favoritos"

    id = Column("id_favorito", Integer, primary_key=True)
    data_favorito = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    id_cliente = Column(Integer, ForeignKey("usuarios.id_usuario"))
    id_profissional = Column(Integer, ForeignKey("profissionais.id_profissional"))

    cliente_rel = relationship("Usuario", back_populates="favoritos")
    profissional_rel = relationship("Profissional", back_populates="favoritos")


class Avaliacao(Base):
    __tablename__ = "avaliacoes"

    id = Column("id_avaliacao", Integer, primary_key=True)
    nota = Column(Integer, nullable=False)
    comentario = Column(Text)
    data_avaliacao = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    id_cliente = Column(Integer, ForeignKey("usuarios.id_usuario"))
    id_profissional = Column(Integer, ForeignKey("profissionais.id_profissional"))

    cliente_rel = relationship("Usuario", back_populates="avaliacoes")
    profissional_rel = relationship("Profissional", back_populates="avaliacoes")


class Contratacao(Base):
    __tablename__ = "contratacoes"

    id = Column("id_contratacao", Integer, primary_key=True)
    data_servico = Column(Date)
    horario = Column(Time)
    endereco = Column(String)
    status = Column(String, default="pendente")
    valor = Column(Numeric(10, 2))

    id_cliente = Column(Integer, ForeignKey("usuarios.id_usuario"))
    id_profissional = Column(Integer, ForeignKey("profissionais.id_profissional"))

    cliente_rel = relationship("Usuario", back_populates="contratacoes")
    profissional_rel = relationship("Profissional", back_populates="contratacoes")


class Notificacao(Base):
    __tablename__ = "notificacoes"

    id = Column("id_notificacao", Integer, primary_key=True)
    titulo = Column(String)
    mensagem = Column(Text)
    visualizada = Column(Boolean, default=False)
    data_envio = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"))
    usuario_rel = relationship("Usuario", back_populates="notificacoes")


class Mensagem(Base):
    __tablename__ = "mensagens"

    id = Column("id_mensagem", Integer, primary_key=True)
    assunto = Column(String)
    mensagem = Column(Text)
    data_envio = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"))
    usuario_rel = relationship("Usuario", back_populates="mensagens")


class NotaPedido(Base):
    __tablename__ = "notas_pedido"

    id = Column("id_nota", Integer, primary_key=True)
    id_contratacao = Column(Integer, ForeignKey("contratacoes.id_contratacao"), nullable=False)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    texto = Column(Text, nullable=False)
    data_criacao = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)


class Configuracao(Base):
    __tablename__ = "configuracoes"

    id = Column("id_configuracao", Integer, primary_key=True)
    notificacoes = Column(Boolean, default=True)
    modo_escuro = Column(Boolean, default=False)
    idioma = Column(String, default="Português")

    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"))
    usuario_rel = relationship("Usuario", back_populates="configuracao_rel")


class TokenRevogado(Base):
    __tablename__ = "tokens_revogados"

    jti = Column(String(36), primary_key=True)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False, index=True)
    expira_em = Column(DateTime, nullable=False, index=True)
