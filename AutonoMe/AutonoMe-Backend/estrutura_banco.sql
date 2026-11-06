-- Estrutura atual do banco AutonoMe (SQLite).
-- Somente definições SQL; nenhum dado foi exportado.
PRAGMA foreign_keys = ON;

CREATE TABLE avaliacoes (
	id_avaliacao INTEGER NOT NULL, 
	nota INTEGER NOT NULL, 
	comentario TEXT, 
	data_avaliacao DATETIME, 
	id_cliente INTEGER, 
	id_profissional INTEGER, 
	PRIMARY KEY (id_avaliacao), 
	FOREIGN KEY(id_cliente) REFERENCES usuarios (id_usuario), 
	FOREIGN KEY(id_profissional) REFERENCES profissionais (id_profissional)
);

CREATE TABLE categorias (
	id_categoria INTEGER NOT NULL, 
	nome VARCHAR NOT NULL, 
	imagem VARCHAR, 
	descricao VARCHAR, 
	PRIMARY KEY (id_categoria)
);

CREATE TABLE configuracoes (
	id_configuracao INTEGER NOT NULL, 
	notificacoes BOOLEAN, 
	modo_escuro BOOLEAN, 
	idioma VARCHAR, 
	id_usuario INTEGER, 
	PRIMARY KEY (id_configuracao), 
	FOREIGN KEY(id_usuario) REFERENCES usuarios (id_usuario)
);

CREATE TABLE contratacoes (
	id_contratacao INTEGER NOT NULL, 
	data_servico DATE, 
	horario TIME, 
	endereco VARCHAR, 
	status VARCHAR, 
	valor NUMERIC(10, 2), 
	id_cliente INTEGER, 
	id_profissional INTEGER, 
	PRIMARY KEY (id_contratacao), 
	FOREIGN KEY(id_cliente) REFERENCES usuarios (id_usuario), 
	FOREIGN KEY(id_profissional) REFERENCES profissionais (id_profissional)
);

CREATE TABLE disponibilidades (
	id INTEGER NOT NULL, 
	id_profissional INTEGER NOT NULL, 
	dia_semana INTEGER NOT NULL, 
	horario TIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_disponibilidade_profissional_dia_hora UNIQUE (id_profissional, dia_semana, horario), 
	FOREIGN KEY(id_profissional) REFERENCES profissionais (id_profissional)
);

CREATE TABLE favoritos (
	id_favorito INTEGER NOT NULL, 
	data_favorito DATETIME, 
	id_cliente INTEGER, 
	id_profissional INTEGER, 
	PRIMARY KEY (id_favorito), 
	FOREIGN KEY(id_cliente) REFERENCES usuarios (id_usuario), 
	FOREIGN KEY(id_profissional) REFERENCES profissionais (id_profissional)
);

CREATE TABLE mensagens (
	id_mensagem INTEGER NOT NULL, 
	assunto VARCHAR, 
	mensagem TEXT, 
	data_envio DATETIME, 
	id_usuario INTEGER, 
	PRIMARY KEY (id_mensagem), 
	FOREIGN KEY(id_usuario) REFERENCES usuarios (id_usuario)
);

CREATE TABLE notas_pedido (
	id_nota INTEGER NOT NULL, 
	id_contratacao INTEGER NOT NULL, 
	id_usuario INTEGER NOT NULL, 
	texto TEXT NOT NULL, 
	data_criacao DATETIME NOT NULL, 
	PRIMARY KEY (id_nota), 
	FOREIGN KEY(id_contratacao) REFERENCES contratacoes (id_contratacao), 
	FOREIGN KEY(id_usuario) REFERENCES usuarios (id_usuario)
);

CREATE TABLE notificacoes (
	id_notificacao INTEGER NOT NULL, 
	titulo VARCHAR, 
	mensagem TEXT, 
	visualizada BOOLEAN, 
	data_envio DATETIME, 
	id_usuario INTEGER, 
	PRIMARY KEY (id_notificacao), 
	FOREIGN KEY(id_usuario) REFERENCES usuarios (id_usuario)
);

CREATE TABLE profissionais (
	id_profissional INTEGER NOT NULL, 
	descricao TEXT, 
	experiencia VARCHAR, 
	preco_hora NUMERIC(10, 2), 
	media_avaliacao NUMERIC(3, 2), 
	id_usuario INTEGER NOT NULL, 
	PRIMARY KEY (id_profissional), 
	FOREIGN KEY(id_usuario) REFERENCES usuarios (id_usuario)
);

CREATE TABLE profissional_profissao (
	id_profissional INTEGER NOT NULL, 
	id_profissao INTEGER NOT NULL, 
	PRIMARY KEY (id_profissional, id_profissao), 
	FOREIGN KEY(id_profissional) REFERENCES profissionais (id_profissional), 
	FOREIGN KEY(id_profissao) REFERENCES profissoes (id_profissao)
);

CREATE TABLE profissoes (
	id_profissao INTEGER NOT NULL, 
	nome VARCHAR NOT NULL, 
	id_categoria INTEGER NOT NULL, 
	PRIMARY KEY (id_profissao), 
	FOREIGN KEY(id_categoria) REFERENCES categorias (id_categoria)
);

CREATE TABLE tokens_revogados (
	jti VARCHAR(36) NOT NULL, 
	id_usuario INTEGER NOT NULL, 
	expira_em DATETIME NOT NULL, 
	PRIMARY KEY (jti), 
	FOREIGN KEY(id_usuario) REFERENCES usuarios (id_usuario)
);

CREATE TABLE usuarios (
	id_usuario INTEGER NOT NULL, 
	nome VARCHAR(120) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	documento VARCHAR(18) NOT NULL, 
	tipo_pessoa VARCHAR(2) NOT NULL, 
	telefone VARCHAR(20), 
	senha VARCHAR(255) NOT NULL, 
	tipo VARCHAR(20), 
	foto VARCHAR(255), 
	data_cadastro DATETIME, 
	ativo BOOLEAN, estado VARCHAR(2), cidade VARCHAR(100), cadastro_configurado BOOLEAN NOT NULL DEFAULT 1, data_nascimento DATE, 
	PRIMARY KEY (id_usuario), 
	UNIQUE (email), 
	UNIQUE (documento)
);

CREATE TABLE usuarios_inativos (
	id_registro_inativo INTEGER NOT NULL, 
	id_usuario INTEGER NOT NULL, 
	nome VARCHAR(120) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	documento VARCHAR(18) NOT NULL, 
	tipo_pessoa VARCHAR(2) NOT NULL, 
	telefone VARCHAR(20), 
	tipo VARCHAR(20) NOT NULL, 
	foto VARCHAR(255), 
	data_cadastro DATETIME, 
	data_desativacao DATETIME NOT NULL, data_nascimento DATE, 
	PRIMARY KEY (id_registro_inativo), 
	UNIQUE (id_usuario), 
	FOREIGN KEY(id_usuario) REFERENCES usuarios (id_usuario)
);

CREATE TABLE verificacoes_email (
	id INTEGER NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	operacao VARCHAR(20) NOT NULL, 
	codigo_hash VARCHAR(64) NOT NULL, 
	dados_pendentes TEXT, 
	id_usuario INTEGER, 
	expira_em DATETIME NOT NULL, 
	tentativas INTEGER NOT NULL, 
	criada_em DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_verificacao_email_operacao UNIQUE (email, operacao), 
	FOREIGN KEY(id_usuario) REFERENCES usuarios (id_usuario)
);

CREATE INDEX ix_disponibilidades_id_profissional ON disponibilidades (id_profissional);

CREATE INDEX ix_tokens_revogados_expira_em ON tokens_revogados (expira_em);

CREATE INDEX ix_tokens_revogados_id_usuario ON tokens_revogados (id_usuario);

CREATE INDEX ix_verificacoes_email_email ON verificacoes_email (email);
