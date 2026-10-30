from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginSchema(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1, max_length=72)


class DesativarContaSchema(BaseModel):
    senha: str = Field(min_length=1, max_length=72)


class CodigoEmailSchema(BaseModel):
    codigo: str = Field(min_length=6, max_length=6)

    @field_validator("codigo")
    @classmethod
    def normaliza_codigo(cls, valor: str) -> str:
        codigo = valor.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{6}", codigo):
            raise ValueError("O código deve ter 6 letras ou números.")
        return codigo


class ConfirmarCadastroSchema(CodigoEmailSchema):
    email: EmailStr


class _CadastroBase(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    senha: str
    confirmacao_senha: str
    telefone: Optional[str] = Field(default=None, max_length=20)
    tipo: Literal["cliente", "profissional"] = "cliente"

    @field_validator("senha")
    @classmethod
    def valida_tamanho_senha(cls, valor: str) -> str:
        if len(valor) < 8 or len(valor.encode("utf-8")) > 72:
            raise ValueError("Senha deve ter pelo menos 8 caracteres e no máximo 72 bytes")
        return valor

    @field_validator("confirmacao_senha")
    @classmethod
    def valida_senhas_iguais(cls, valor: str, info) -> str:
        if "senha" in info.data and valor != info.data["senha"]:
            raise ValueError("As senhas não coincidem")
        return valor


class CadastroPFSchema(_CadastroBase):
    cpf: str = Field(min_length=11, max_length=14)
    telefone: str = Field(min_length=11, max_length=20)

    @field_validator("telefone")
    @classmethod
    def valida_celular(cls, valor: str) -> str:
        digitos = "".join(caractere for caractere in valor if caractere.isdigit())
        if len(digitos) != 11 or not 11 <= int(digitos[:2]) <= 99 or digitos[2] != "9":
            raise ValueError("Informe um celular válido com DDD")
        return digitos


class CadastroPJSchema(_CadastroBase):
    cnpj: Optional[str] = Field(default=None, min_length=14, max_length=18)


class SessaoUsuarioSchema(BaseModel):
    id: int
    nome: str
    email: EmailStr
    tipo: str


class LoginResponseSchema(BaseModel):
    token: str
    usuario: SessaoUsuarioSchema
    redirecionar_para: str


class CadastroResponseSchema(BaseModel):
    id: int
    nome: str
    email: EmailStr
    tipo: str


class UsuarioEdicaoSchema(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    telefone: Optional[str] = Field(default=None, max_length=20)


class ProfissoesProfissionalSchema(BaseModel):
    ids_profissoes: list[int] = Field(min_length=1, max_length=100)

    @field_validator("ids_profissoes")
    @classmethod
    def valida_ids_profissoes(cls, valores: list[int]) -> list[int]:
        if any(valor < 1 for valor in valores):
            raise ValueError("Selecione profissões válidas")
        if len(valores) != len(set(valores)):
            raise ValueError("Há profissões repetidas na seleção")
        return valores


class UsuarioPerfilSchema(BaseModel):
    id: int
    nome: str
    foto: Optional[str] = None
    email: Optional[EmailStr] = None
    telefone: Optional[str] = None
    tipo: str
    tipo_pessoa: str
    data_cadastro: Optional[datetime] = None
    ocupacao: str
    sobre: str
    preco_hora: Optional[float] = None
    experiencia: Optional[str] = None


class MensagemChatSchema(BaseModel):
    usuario_id: int
    texto: str = Field(min_length=1, max_length=2000)

    @field_validator("texto")
    @classmethod
    def normaliza_texto(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("A mensagem não pode estar vazia")
        return valor


class NotaPedidoSchema(BaseModel):
    usuario_id: int
    texto: str = Field(min_length=1, max_length=2000)

    @field_validator("texto")
    @classmethod
    def normaliza_texto(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("A nota não pode estar vazia")
        return valor


class ContratacaoSchema(BaseModel):
    cliente_id: int
    profissional_id: int
    data_servico: str
    horario: str
    endereco: str = Field(min_length=3, max_length=255)
    valor: Decimal = Field(ge=0, max_digits=10, decimal_places=2)

    @field_validator("endereco")
    @classmethod
    def normaliza_endereco(cls, valor: str) -> str:
        valor = valor.strip()
        if len(valor) < 3:
            raise ValueError("Endereço inválido")
        return valor
