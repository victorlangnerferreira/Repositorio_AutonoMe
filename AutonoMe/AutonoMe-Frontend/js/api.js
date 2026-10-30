const API_BASE_URL = window.AUTONOME_API_BASE_URL || "http://127.0.0.1:8000";

async function apiFetch(url, options = {}) {
    const headers = new Headers(options.headers || {});
    const token = localStorage.getItem("token");
    if (token && !url.endsWith("/login") && !url.includes("/cadastro_")) {
        headers.set("Authorization", `Bearer ${token}`);
    }
    const resposta = await fetch(url, { ...options, headers });
    if (resposta.status === 401 && token && !url.endsWith("/login")) {
        localStorage.removeItem("token");
        localStorage.removeItem("usuario");
        window.location.href = "login.html";
    }
    return resposta;
}

function mensagemDaResposta(dados, mensagemPadrao) {
    if (typeof dados.detail === "string") return dados.detail;

    if (Array.isArray(dados.detail)) {
        const documentoFaltando = dados.detail.some(function (erro) {
            if (!erro.loc) return false;
            const campo = erro.loc[erro.loc.length - 1];
            return campo === "cpf" || campo === "cnpj";
        });

        if (documentoFaltando) {
            return "Reinicie a API para aplicar o cadastro sem CPF/CNPJ.";
        }

        const mensagens = dados.detail.map(function (erro) {
            return erro.msg;
        }).filter(Boolean);
        return mensagens.join(" ") || mensagemPadrao;
    }

    return mensagemPadrao;
}

async function login(email, senha) {
    const resposta = await apiFetch(`${API_BASE_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, senha }),
    });

    const dados = await resposta.json().catch(() => ({}));
    if (!resposta.ok) {
        const mensagem = resposta.status === 401
            ? "E-mail ou senha incorretos."
            : resposta.status === 422
                ? "Informe um e-mail válido e preencha a senha."
                : typeof dados.detail === "string"
                    ? dados.detail
                    : "Não foi possível fazer login.";
        throw new Error(mensagem);
    }
    return dados;
}

async function encerrarSessao() {
    return apiFetch(`${API_BASE_URL}/logout`, { method: "POST" });
}

async function solicitarCodigoDesativacao(senha) {
    const resposta = await apiFetch(`${API_BASE_URL}/usuarios/me/desativar/solicitar-codigo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ senha }),
    });
    const dados = await resposta.json();
    if (!resposta.ok) throw new Error(dados.detail || "Não foi possível enviar o código.");
    return dados;
}

async function confirmarDesativacao(codigo) {
    const resposta = await apiFetch(`${API_BASE_URL}/usuarios/me/desativar/confirmar-codigo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ codigo }),
    });
    const dados = await resposta.json();
    if (!resposta.ok) throw new Error(dados.detail || "Não foi possível confirmar a desativação.");
    return dados;
}

async function cadastrarPf(dadosForm) {
    const resposta = await apiFetch(`${API_BASE_URL}/cadastro_pf/solicitar-codigo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(dadosForm),
    });

    const dados = await resposta.json();
    if (!resposta.ok) {
        throw new Error(mensagemDaResposta(dados, "Erro ao cadastrar Pessoa Física"));
    }
    return dados;
}

async function confirmarCadastro(email, codigo) {
    const resposta = await apiFetch(`${API_BASE_URL}/cadastro_pf/confirmar-codigo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, codigo }),
    });
    const dados = await resposta.json();
    if (!resposta.ok) throw new Error(mensagemDaResposta(dados, "Não foi possível confirmar seu e-mail."));
    return dados;
}

async function cadastrarPj(dadosForm) {
    const resposta = await apiFetch(`${API_BASE_URL}/cadastro_pj/solicitar-codigo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(dadosForm),
    });

    const dados = await resposta.json();
    if (!resposta.ok) {
        throw new Error(mensagemDaResposta(dados, "Erro ao cadastrar Pessoa Jurídica"));
    }
    return dados;
}

async function confirmarCadastroPj(email, codigo) {
    const resposta = await apiFetch(`${API_BASE_URL}/cadastro_pj/confirmar-codigo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, codigo }),
    });
    const dados = await resposta.json();
    if (!resposta.ok) throw new Error(mensagemDaResposta(dados, "Não foi possível confirmar seu e-mail."));
    return dados;
}

async function buscarCategorias() {
    const resposta = await apiFetch(`${API_BASE_URL}/categorias`);
    if (!resposta.ok) throw new Error("Erro ao buscar categorias");
    return await resposta.json();
}

async function buscarProfissoesPorCategoria(idCategoria) {
    const resposta = await apiFetch(`${API_BASE_URL}/categorias/${idCategoria}/profissoes`);
    if (!resposta.ok) throw new Error("Erro ao buscar profissões");
    return await resposta.json();
}

async function buscarMinhasProfissoes() {
    const resposta = await apiFetch(`${API_BASE_URL}/profissionais/me/profissoes`);
    const dados = await resposta.json();
    if (!resposta.ok) throw new Error(dados.detail || "Não foi possível carregar seus serviços.");
    return dados;
}

async function salvarMinhasProfissoes(idsProfissoes) {
    const resposta = await apiFetch(`${API_BASE_URL}/profissionais/me/profissoes`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids_profissoes: idsProfissoes }),
    });
    const dados = await resposta.json();
    if (!resposta.ok) throw new Error(dados.detail || "Não foi possível salvar os serviços.");
    return dados;
}

async function buscarProfissionais(idProfissao) {
    const url = idProfissao ? `${API_BASE_URL}/profissionais?profissao=${idProfissao}` : `${API_BASE_URL}/profissionais`;
    const resposta = await apiFetch(url);
    if (!resposta.ok) throw new Error("Erro ao buscar profissionais");
    return await resposta.json();
}

async function buscarFavoritos(idCliente) {
    const resposta = await apiFetch(`${API_BASE_URL}/favoritos/${idCliente}`);
    if (!resposta.ok) throw new Error("Erro ao buscar favoritos");
    return await resposta.json();
}

async function buscarNotificacoes(idUsuario) {
    const resposta = await apiFetch(`${API_BASE_URL}/notificacoes/${idUsuario}`);
    if (!resposta.ok) throw new Error("Erro ao buscar notificações");
    return await resposta.json();
}

async function buscarContratacoes(idUsuario) {
    const resposta = await apiFetch(`${API_BASE_URL}/contratacoes/${idUsuario}`);
    if (!resposta.ok) throw new Error("Erro ao buscar contratações");
    return await resposta.json();
}

async function buscarUsuario(idUsuario) {
    const resposta = await apiFetch(`${API_BASE_URL}/usuarios/${idUsuario}`);
    if (!resposta.ok) throw new Error("Erro ao carregar usuário");
    return resposta.json();
}

async function atualizarPerfil(dados) {
    const resposta = await apiFetch(`${API_BASE_URL}/usuarios/me`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(dados),
    });
    const resultado = await resposta.json();
    if (!resposta.ok) {
        const mensagem = typeof resultado.detail === "string"
            ? resultado.detail
            : "Confira o nome, o e-mail e o telefone.";
        throw new Error(mensagem);
    }
    return resultado;
}

async function enviarFotoPerfil(arquivo) {
    const formulario = new FormData();
    formulario.append("arquivo", arquivo);
    const resposta = await apiFetch(`${API_BASE_URL}/usuarios/me/foto`, {
        method: "POST",
        body: formulario,
    });
    const resultado = await resposta.json();
    if (!resposta.ok) throw new Error(resultado.detail || "Não foi possível enviar a foto.");
    return resultado;
}

async function buscarRelatorio(idUsuario) {
    const resposta = await apiFetch(`${API_BASE_URL}/relatorios/${idUsuario}`);
    if (!resposta.ok) throw new Error("Erro ao carregar relatório");
    return resposta.json();
}

async function buscarNotasPedido(idContratacao, usuarioId) {
    const resposta = await apiFetch(`${API_BASE_URL}/contratacoes/${idContratacao}/notas?usuario_id=${usuarioId}`);
    if (!resposta.ok) throw new Error("Erro ao carregar notas do pedido");
    return resposta.json();
}

async function salvarNotaPedido(idContratacao, usuarioId, texto) {
    const resposta = await apiFetch(`${API_BASE_URL}/contratacoes/${idContratacao}/notas`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ usuario_id: usuarioId, texto }),
    });
    const dados = await resposta.json();
    if (!resposta.ok) throw new Error(dados.detail || "Erro ao salvar nota");
    return dados;
}

async function criarContratacao(dados) {
    const resposta = await apiFetch(`${API_BASE_URL}/contratacoes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(dados),
    });
    const resultado = await resposta.json();
    if (!resposta.ok) throw new Error(resultado.detail || "Erro ao criar pedido");
    return resultado;
}

async function marcarNotificacaoLida(idNotificacao, idUsuario) {
    const resposta = await apiFetch(`${API_BASE_URL}/notificacoes/${idNotificacao}/visualizada?usuario_id=${idUsuario}`, { method: "PATCH" });
    if (!resposta.ok) throw new Error("Erro ao atualizar notificação");
    return resposta.json();
}

async function excluirNotificacoes(idUsuario) {
    const resposta = await apiFetch(`${API_BASE_URL}/notificacoes/${idUsuario}`, { method: "DELETE" });
    if (!resposta.ok) throw new Error("Erro ao excluir notificações");
    return resposta.json();
}

async function marcarTodasNotificacoesLidas(idUsuario) {
    const resposta = await apiFetch(`${API_BASE_URL}/notificacoes/${idUsuario}/visualizadas`, { method: "PATCH" });
    if (!resposta.ok) throw new Error("Erro ao atualizar notificações");
    return resposta.json();
}
