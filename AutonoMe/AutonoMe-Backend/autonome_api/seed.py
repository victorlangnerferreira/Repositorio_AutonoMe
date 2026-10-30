from sqlalchemy.orm import Session
from sqlalchemy import inspect
import bcrypt

from autonome_api.database import Base, engine, SessionLocal
from autonome_api.models import (
    Usuario, Categoria, Profissao, Profissional,
    ProfissionalProfissao, Avaliacao, Configuracao
)

CATALOGO_PROFISSOES = {
    "Casa": ("Serviços domésticos e cuidados residenciais.", [
        "Babá", "Faxineira", "Diarista", "Cozinheira", "Passadeira", "Jardineiro",
        "Cuidador de Idosos", "Cuidador de Pessoas com Deficiência", "Pet sitter",
        "Dog walker", "Lavador de estofados", "Organizador residencial", "Caseiro",
        "Piscineiro", "Lavador de carros", "Montador de móveis"
    ]),
    "Trabalho Manual": ("Reparos, reformas e serviços manuais.", [
        "Faz-tudo", "Eletricista", "Encanador", "Pintor", "Pedreiro", "Marceneiro",
        "Azulejista", "Gesseiro", "Serralheiro", "Chaveiro", "Vidraceiro",
        "Instalador de ar-condicionado", "Técnico de manutenção", "Tapeceiro",
        "Montador de móveis", "Telhadista", "Calheiro", "Instalador de pisos"
    ]),
    "Beleza e Bem-estar": ("Cuidados pessoais, beleza e bem-estar.", [
        "Cabeleireiro", "Barbeiro", "Manicure", "Pedicure", "Maquiador",
        "Massagista", "Designer de sobrancelhas", "Depilador", "Trancista"
    ]),
    "Aulas e Consultoria": ("Aulas particulares e orientação profissional.", [
        "Professor particular", "Professor de idiomas", "Reforço escolar",
        "Aula de música", "Personal trainer", "Consultor de informática"
    ]),
    "Tecnologia e Serviços Digitais": ("Ajuda com tecnologia e serviços pela internet.", [
        "Técnico de informática", "Instalador de redes", "Conserto de celular",
        "Designer gráfico", "Editor de vídeo", "Fotógrafo", "Digitador"
    ]),
    "Eventos e Entregas": ("Apoio para eventos, mudanças e entregas locais.", [
        "Garçom", "Copeiro", "Cozinheiro para eventos", "Decorador de festas",
        "Músico", "Entregador", "Freteiro", "Ajudante de mudança"
    ])
}

def garantir_catalogo(db: Session):
    profissoes = []
    for nome_categoria, (descricao, nomes_profissoes) in CATALOGO_PROFISSOES.items():
        categoria = db.query(Categoria).filter(Categoria.nome == nome_categoria).first()
        if not categoria:
            categoria = Categoria(nome=nome_categoria, descricao=descricao)
            db.add(categoria)
            db.flush()
        elif not categoria.descricao:
            categoria.descricao = descricao

        for nome_profissao in nomes_profissoes:
            profissao = db.query(Profissao).filter(
                Profissao.id_categoria == categoria.id,
                Profissao.nome == nome_profissao
            ).first()
            if not profissao:
                profissao = Profissao(nome=nome_profissao, id_categoria=categoria.id)
                db.add(profissao)
                db.flush()
            profissoes.append(profissao)
    db.commit()
    return profissoes

def gerar_cpf(index: int) -> str:
    base = f"{index:09d}"
    soma1 = sum(int(base[i]) * (10 - i) for i in range(9))
    d1 = (soma1 * 10) % 11
    d1 = 0 if d1 >= 10 else d1
    soma2 = sum(int(base[i]) * (11 - i) for i in range(9)) + d1 * 2
    d2 = (soma2 * 10) % 11
    d2 = 0 if d2 >= 10 else d2
    return f"{base}{d1}{d2}"

def executar_seed():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "usuarios" in tables:
        columns = [c["name"] for c in inspector.get_columns("usuarios")]
        if "documento" not in columns:
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
    else:
        Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        admin_existente = db.query(Usuario).filter(Usuario.email == "admin@autonome.com").first()
        if admin_existente:
            garantir_catalogo(db)
            return

        senha_hash = bcrypt.hashpw("123456789".encode(), bcrypt.gensalt()).decode()

        admin = Usuario(
            nome="admin",
            email="admin@autonome.com",
            documento=gerar_cpf(100000001),
            tipo_pessoa="PF",
            telefone="11999999999",
            senha=senha_hash,
            tipo="administrador",
            ativo=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        config = Configuracao(
            id_usuario=admin.id,
            notificacoes=True,
            modo_escuro=False,
            idioma="Português"
        )
        db.add(config)
        db.commit()

        profissoes_obj = garantir_catalogo(db)

        nomes = [
            "Ana Souza", "Carlos Silva", "Beatriz Oliveira", "Diego Ferreira",
            "Camila Santos", "Eduardo Lima", "Fernanda Costa", "Gabriel Pereira",
            "Juliana Rodrigues", "Lucas Almeida", "Mariana Barbosa", "Pedro Rocha",
            "Aline Ribeiro", "Bruno Martins", "Carla Alves", "Daniel Gomes",
            "Patricia Dias", "Rafael Castro", "Priscila Mendes", "Rodrigo Ramos",
            "Vanessa Cardoso", "Thiago Nogueira", "Tatiany Duarte", "Vinicius Freitas",
            "Amanda Monteiro", "Felipe Barbosa", "Leticia Santana", "Gustavo Teixeira",
            "Monique Melo", "Leonardo Pires", "Sabrina Campos", "Mateus Vasconcelos",
            "Natalia Guimaraes", "Vitor Machado", "Jaqueline Moraes", "Alexandre Nunes",
            "Carolina Borges", "Igor Fernandes", "Debora Soares", "Luciano Andrade",
            "Renata Marques", "Marcelo Vieira", "Bianca Nascimento", "Fabio Lopes",
            "Larissa Araujo", "Roberto Correia", "Raquel Figueiredo", "Hugo Carvalho"
        ]

        prof_counter = 0
        for prof in profissoes_obj[:12]:
            for idx in range(4):
                nome_completo = nomes[prof_counter % len(nomes)]
                primeiro_nome = nome_completo.split()[0].lower()
                sobrenome = nome_completo.split()[1].lower()
                email = f"{primeiro_nome}.{sobrenome}{prof_counter + 1}@autonome.com"
                cpf = gerar_cpf(200000000 + prof_counter + 1)
                telefone = f"119{80000000 + prof_counter:08d}"

                u = Usuario(
                    nome=nome_completo,
                    email=email,
                    documento=cpf,
                    tipo_pessoa="PF",
                    telefone=telefone,
                    senha=senha_hash,
                    tipo="profissional",
                    ativo=True
                )
                db.add(u)
                db.commit()
                db.refresh(u)

                exp_anos = (prof_counter % 14) + 2
                preco = round(25.0 + float((prof_counter * 7) % 95), 2)
                avaliacao = round(3.8 + float((prof_counter * 3) % 13) / 10.0, 2)

                p_prof = Profissional(
                    descricao=f"Profissional qualificado em {prof.nome} com atendimento rápido.",
                    experiencia=f"{exp_anos} anos",
                    preco_hora=preco,
                    media_avaliacao=avaliacao,
                    id_usuario=u.id
                )
                db.add(p_prof)
                db.commit()
                db.refresh(p_prof)

                link = ProfissionalProfissao(
                    id_profissional=p_prof.id,
                    id_profissao=prof.id
                )
                db.add(link)
                db.commit()

                av1 = Avaliacao(
                    nota=5,
                    comentario="Excelente atendimento, muito pontual e profissional.",
                    id_cliente=admin.id,
                    id_profissional=p_prof.id
                )
                db.add(av1)
                if prof_counter % 2 == 0:
                    av2 = Avaliacao(
                        nota=4,
                        comentario="Ótimo serviço prestado.",
                        id_cliente=admin.id,
                        id_profissional=p_prof.id
                    )
                    db.add(av2)
                db.commit()

                prof_counter += 1
    finally:
        db.close()
