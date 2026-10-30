const usuarioServicos = JSON.parse(localStorage.getItem("usuario") || "null");
const listaCategoriasServicos = document.getElementById("lista-categorias-servicos");
const buscaServicos = document.getElementById("busca-servicos");
const contagemServicos = document.getElementById("total-servicos-selecionados");
const botaoSalvarServicos = document.getElementById("btn-salvar-servicos");
const mensagemServicos = document.getElementById("mensagem-servicos");
const selecionadas = new Set();

function atualizarContagemServicos() {
    const total = selecionadas.size;
    contagemServicos.textContent = `${total} ${total === 1 ? "serviço selecionado" : "serviços selecionados"}`;
}

function filtrarServicos() {
    const termo = buscaServicos.value.trim().toLocaleLowerCase("pt-BR");
    listaCategoriasServicos.querySelectorAll(".servicos-categoria").forEach(categoria => {
        let visiveis = 0;
        categoria.querySelectorAll(".servico-opcao").forEach(opcao => {
            const corresponde = opcao.dataset.nome.toLocaleLowerCase("pt-BR").includes(termo);
            opcao.hidden = !corresponde;
            if (corresponde) visiveis++;
        });
        categoria.hidden = visiveis === 0;
    });
}

function renderizarCategorias(categorias) {
    listaCategoriasServicos.replaceChildren();
    categorias.forEach(categoria => {
        const secao = document.createElement("section");
        secao.className = "servicos-categoria";
        const cabecalho = document.createElement("div");
        cabecalho.className = "servicos-categoria-cabecalho";
        const titulo = document.createElement("h2");
        titulo.textContent = categoria.nome;
        const selecionarTodos = document.createElement("button");
        selecionarTodos.type = "button";
        selecionarTodos.className = "btn-selecionar-categoria";
        selecionarTodos.textContent = "Selecionar todos";
        selecionarTodos.addEventListener("click", () => {
            categoria.profissoes.forEach(profissao => selecionadas.add(Number(profissao.id_profissao)));
            secao.querySelectorAll("input[type=checkbox]").forEach(caixa => { caixa.checked = true; });
            atualizarContagemServicos();
        });
        cabecalho.append(titulo, selecionarTodos);

        const descricao = document.createElement("p");
        descricao.className = "servicos-categoria-descricao";
        descricao.textContent = categoria.descricao || "Escolha as profissões que você oferece.";
        const opcoes = document.createElement("div");
        opcoes.className = "servicos-opcoes";

        (categoria.profissoes || []).forEach(profissao => {
            const id = Number(profissao.id_profissao);
            const opcao = document.createElement("label");
            opcao.className = "servico-opcao";
            opcao.dataset.nome = profissao.nome || "";
            const caixa = document.createElement("input");
            caixa.type = "checkbox";
            caixa.value = String(id);
            caixa.checked = selecionadas.has(id);
            caixa.addEventListener("change", () => {
                if (caixa.checked) selecionadas.add(id);
                else selecionadas.delete(id);
                atualizarContagemServicos();
            });
            const nome = document.createElement("span");
            nome.textContent = profissao.nome || "Profissão";
            opcao.append(caixa, nome);
            opcoes.appendChild(opcao);
        });

        secao.append(cabecalho, descricao, opcoes);
        listaCategoriasServicos.appendChild(secao);
    });
    listaCategoriasServicos.setAttribute("aria-busy", "false");
    botaoSalvarServicos.disabled = false;
    atualizarContagemServicos();
    filtrarServicos();
}

buscaServicos.addEventListener("input", filtrarServicos);

botaoSalvarServicos.addEventListener("click", async () => {
    if (!selecionadas.size) {
        mensagemServicos.textContent = "Selecione pelo menos um serviço.";
        return;
    }
    botaoSalvarServicos.disabled = true;
    mensagemServicos.textContent = "Salvando serviços...";
    try {
        await salvarMinhasProfissoes([...selecionadas]);
        mensagemServicos.textContent = "Serviços salvos no seu perfil.";
    } catch (erro) {
        mensagemServicos.textContent = erro.message;
    } finally {
        botaoSalvarServicos.disabled = false;
    }
});

async function carregarServicosProfissional() {
    if (!usuarioServicos || usuarioServicos.tipo !== "profissional") {
        mensagemServicos.textContent = "Entre em uma conta profissional para configurar os serviços.";
        window.setTimeout(() => { window.location.href = "perfil.html"; }, 1200);
        return;
    }
    listaCategoriasServicos.textContent = "Carregando catálogo...";
    try {
        const [categorias, idsSalvos] = await Promise.all([buscarCategorias(), buscarMinhasProfissoes()]);
        idsSalvos.forEach(id => selecionadas.add(Number(id)));
        if (!categorias.length) {
            listaCategoriasServicos.textContent = "Não há serviços cadastrados no catálogo.";
            return;
        }
        renderizarCategorias(categorias);
    } catch (erro) {
        listaCategoriasServicos.textContent = erro.message;
    }
}

carregarServicosProfissional();
