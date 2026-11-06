from datetime import date, datetime
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
    def valida_senha_forte(cls, valor: str) -> str:
        if len(valor) < 8:
            raise ValueError("A senha deve ter pelo menos 8 caracteres.")
        if len(valor.encode("utf-8")) > 72:
            raise ValueError("A senha não pode ultrapassar 72 bytes.")
        if not re.search(r"[A-Z]", valor):
            raise ValueError("A senha deve ter pelo menos uma letra maiúscula.")
        if not re.search(r"[a-z]", valor):
            raise ValueError("A senha deve ter pelo menos uma letra minúscula.")
        if not re.search(r"[0-9]", valor):
            raise ValueError("A senha deve ter pelo menos um número.")
        if not re.search(r"[^A-Za-z0-9\s]", valor):
            raise ValueError("A senha deve ter pelo menos um símbolo, como ! ou #.")
        return valor

    @field_validator("confirmacao_senha")
    @classmethod
    def valida_senhas_iguais(cls, valor: str, info) -> str:
        if "senha" in info.data and valor != info.data["senha"]:
            raise ValueError("As senhas não coincidem")
        return valor


class CadastroPFSchema(_CadastroBase):
    cpf: str = Field(min_length=11, max_length=14)
    data_nascimento: date
    telefone: str = Field(min_length=11, max_length=20)

    @field_validator("data_nascimento")
    @classmethod
    def valida_data_nascimento(cls, valor: date) -> date:
        if valor >= date.today():
            raise ValueError("A data de nascimento deve estar no passado.")
        return valor

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
    estado: Optional[str] = None
    cidade: Optional[str] = None
    perfil_completo: bool = True


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
    preco_hora: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    descricao: Optional[str] = Field(default=None, max_length=2000)
    experiencia: Optional[str] = Field(default=None, max_length=120)

    @field_validator("ids_profissoes")
    @classmethod
    def valida_ids_profissoes(cls, valores: list[int]) -> list[int]:
        if any(valor < 1 for valor in valores):
            raise ValueError("Selecione profissões válidas")
        if len(valores) != len(set(valores)):
            raise ValueError("Há profissões repetidas na seleção")
        return valores


class ItemDisponibilidadeSchema(BaseModel):
    dia_semana: int = Field(ge=0, le=6)
    horario: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class DisponibilidadesSchema(BaseModel):
    horarios: list[ItemDisponibilidadeSchema] = Field(max_length=168)

    @field_validator("horarios")
    @classmethod
    def sem_horarios_duplicados(cls, valores: list[ItemDisponibilidadeSchema]) -> list[ItemDisponibilidadeSchema]:
        pares = [(item.dia_semana, item.horario) for item in valores]
        if len(pares) != len(set(pares)):
            raise ValueError("Remova dias e horários repetidos")
        return valores


class ConfiguracaoInicialSchema(BaseModel):
    estado: str = Field(min_length=2, max_length=2)
    cidade: str = Field(min_length=2, max_length=100)
    ids_profissoes: Optional[list[int]] = Field(default=None, min_length=1, max_length=100)
    preco_hora: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)

    @field_validator("estado")
    @classmethod
    def normaliza_estado(cls, valor: str) -> str:
        estado = valor.strip().upper()
        if estado not in {
            "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
            "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
        }:
            raise ValueError("Selecione um estado válido")
        return estado

    @field_validator("cidade")
    @classmethod
    def normaliza_cidade(cls, valor: str) -> str:
        cidade = valor.strip()
        if len(cidade) < 2:
            raise ValueError("Informe uma cidade válida")
        return cidade

    @field_validator("ids_profissoes")
    @classmethod
    def valida_ids_profissoes(cls, valores: Optional[list[int]]) -> Optional[list[int]]:
        if valores is not None and (any(valor < 1 for valor in valores) or len(valores) != len(set(valores))):
            raise ValueError("Selecione profissões válidas, sem repetição")
        return valores


class UsuarioPerfilSchema(BaseModel):
    id: int
    id_profissional: Optional[int] = None
    nome: str
    foto: Optional[str] = None
    email: Optional[EmailStr] = None
    telefone: Optional[str] = None
    tipo: str
    tipo_pessoa: str
    data_nascimento: Optional[date] = None
    estado: Optional[str] = None
    cidade: Optional[str] = None
    data_cadastro: Optional[datetime] = None
    ocupacao: str
    sobre: str
    preco_hora: Optional[float] = None
    experiencia: Optional[str] = None
    tem_servicos: bool = False


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
