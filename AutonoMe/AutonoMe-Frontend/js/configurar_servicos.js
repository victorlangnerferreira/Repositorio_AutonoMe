const listaCategoriasServicos = document.getElementById("lista-categorias-servicos");
const buscaServicos = document.getElementById("busca-servicos");
const contagemServicos = document.getElementById("total-servicos-selecionados");
const botaoSalvarServicos = document.getElementById("btn-salvar-servicos");
const mensagemServicos = document.getElementById("mensagem-servicos");
const campoPrecoHoraServicos = document.getElementById("preco-hora-servicos");
const campoDescricaoServicos = document.getElementById("descricao-servicos");
const campoExperienciaServicos = document.getElementById("experiencia-servicos");
const resumoServicos = document.getElementById("resumo-servicos");
const diasDisponiveis = document.getElementById("dias-disponiveis");
const novoHorarioDisponivel = document.getElementById("novo-horario-disponivel");
const listaDisponibilidades = document.getElementById("lista-disponibilidades");
const botaoAdicionarHorario = document.getElementById("btn-adicionar-horario");
const botaoSalvarDisponibilidade = document.getElementById("btn-salvar-disponibilidade");
const mensagemDisponibilidade = document.getElementById("mensagem-disponibilidade");
const selecionadas = new Set();
const nomesDias = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"];
let horariosDisponiveis = [];
let modoEdicao = false;
let categoriasAtuais = [];

function atualizarContagemServicos() {
    const total = selecionadas.size;
    contagemServicos.textContent = `${total} ${total === 1 ? "profissão selecionada" : "profissões selecionadas"}`;
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

function atualizarResumo(nomesProfissoes) {
    const nomes = nomesProfissoes.filter(Boolean);
    document.getElementById("resumo-profissoes").textContent = `Profissões: ${nomes.join(", ")}`;
    document.getElementById("resumo-preco").textContent = `Taxa: R$ ${Number(campoPrecoHoraServicos.value).toFixed(2).replace(".", ",")} por hora`;
    document.getElementById("resumo-descricao").textContent = campoDescricaoServicos.value.trim() || "Adicione uma descrição para ajudar clientes a conhecer seu trabalho.";
    resumoServicos.hidden = false;
}

function atualizarModoPublicado(publicado, nomesProfissoes = []) {
    modoEdicao = publicado;
    document.getElementById("titulo-servicos").textContent = publicado ? "Editar meus serviços" : "Disponibilizar meus serviços";
    document.getElementById("instrucao-servicos").textContent = publicado
        ? "Atualize suas profissões, sua taxa e as informações que aparecem para os clientes."
        : "Escolha o que você oferece e publique no seu perfil para que clientes encontrem você.";
    botaoSalvarServicos.textContent = publicado ? "Salvar alterações" : "Disponibilizar serviços";
    botaoSalvarDisponibilidade.disabled = !publicado;
    document.getElementById("instrucao-disponibilidade").textContent = publicado
        ? "Marque um ou mais dias, escolha um horário e adicione. Repita para incluir outros horários."
        : "Publique primeiro seus serviços para depois cadastrar os dias e horários de atendimento.";
    if (publicado) atualizarResumo(nomesProfissoes);
    else resumoServicos.hidden = true;
}

function renderizarDisponibilidades() {
    listaDisponibilidades.replaceChildren();
    horariosDisponiveis
        .sort((a, b) => a.dia_semana - b.dia_semana || a.horario.localeCompare(b.horario))
        .forEach((item, indice) => {
            const linha = document.createElement("li");
            linha.appendChild(document.createTextNode(`${nomesDias[item.dia_semana]} • ${item.horario}`));
            const remover = document.createElement("button");
            remover.type = "button";
            remover.textContent = "Remover";
            remover.setAttribute("aria-label", `Remover ${nomesDias[item.dia_semana]} às ${item.horario}`);
            remover.addEventListener("click", () => {
                horariosDisponiveis.splice(indice, 1);
                renderizarDisponibilidades();
            });
            linha.appendChild(remover);
            listaDisponibilidades.appendChild(linha);
        });
    if (!horariosDisponiveis.length) {
        const vazio = document.createElement("li");
        vazio.textContent = "Nenhum horário adicionado.";
        listaDisponibilidades.appendChild(vazio);
    }
}

botaoAdicionarHorario.addEventListener("click", () => {
    const diasSelecionados = [...diasDisponiveis.querySelectorAll("input:checked")].map(campo => Number(campo.value));
    const horario = novoHorarioDisponivel.value;
    if (!diasSelecionados.length || !horario) {
        mensagemDisponibilidade.textContent = "Selecione pelo menos um dia e um horário.";
        return;
    }
    diasSelecionados.forEach(dia => {
        if (!horariosDisponiveis.some(item => item.dia_semana === dia && item.horario === horario)) {
            horariosDisponiveis.push({ dia_semana: dia, horario });
        }
    });
    mensagemDisponibilidade.textContent = "Horário adicionado. Salve a disponibilidade para publicar.";
    renderizarDisponibilidades();
});

botaoSalvarDisponibilidade.addEventListener("click", async () => {
    botaoSalvarDisponibilidade.disabled = true;
    mensagemDisponibilidade.textContent = "Salvando disponibilidade...";
    try {
        horariosDisponiveis = await salvarMinhasDisponibilidades(horariosDisponiveis);
        mensagemDisponibilidade.textContent = horariosDisponiveis.length
            ? "Disponibilidade salva. Esses horários poderão ser escolhidos pelos clientes."
            : "Disponibilidade removida. Os clientes não verão horários para agendar.";
        renderizarDisponibilidades();
    } catch (erro) {
        mensagemDisponibilidade.textContent = erro.message;
    } finally {
        botaoSalvarDisponibilidade.disabled = !modoEdicao;
    }
});

function renderizarCategorias(categorias) {
    listaCategoriasServicos.replaceChildren();
    categorias.forEach(categoria => {
        const secao = document.createElement("section");
        secao.className = "servicos-categoria";
        const cabecalho = document.createElement("div");
        cabecalho.className = "servicos-categoria-cabecalho";
        const titulo = document.createElement("h3");
        titulo.textContent = categoria.nome;
        const selecionarTodos = document.createElement("button");
        selecionarTodos.type = "button";
        selecionarTodos.className = "btn-selecionar-categoria";
        selecionarTodos.textContent = "Selecionar todos";
        selecionarTodos.addEventListener("click", () => {
            (categoria.profissoes || []).forEach(profissao => selecionadas.add(Number(profissao.id_profissao)));
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

function nomesSelecionados(categorias) {
    return categorias.flatMap(categoria => categoria.profissoes || [])
        .filter(profissao => selecionadas.has(Number(profissao.id_profissao)))
        .map(profissao => profissao.nome);
}

buscaServicos.addEventListener("input", filtrarServicos);

botaoSalvarServicos.addEventListener("click", async () => {
    if (!selecionadas.size) {
        mensagemServicos.textContent = "Selecione pelo menos uma profissão.";
        return;
    }
    const precoHora = Number(campoPrecoHoraServicos.value);
    if (!Number.isFinite(precoHora) || precoHora <= 0) {
        mensagemServicos.textContent = "Informe uma taxa por hora maior que zero.";
        campoPrecoHoraServicos.focus();
        return;
    }
    botaoSalvarServicos.disabled = true;
    mensagemServicos.textContent = modoEdicao ? "Salvando alterações..." : "Publicando seus serviços...";
    try {
        await salvarMinhasProfissoes(
            [...selecionadas],
            precoHora,
            campoDescricaoServicos.value.trim(),
            campoExperienciaServicos.value.trim()
        );
        atualizarModoPublicado(true, nomesSelecionados(categoriasAtuais));
        mensagemServicos.textContent = "Seus serviços estão disponíveis no perfil e nas buscas.";
    } catch (erro) {
        mensagemServicos.textContent = erro.message;
    } finally {
        botaoSalvarServicos.disabled = false;
    }
});

async function carregarServicosProfissional() {
    try {
        const contaAtual = await obterConfiguracaoInicial();
        if (contaAtual.tipo !== "profissional") {
            mensagemServicos.textContent = "Esta área é exclusiva para quem presta serviços. Voltando ao perfil...";
            window.setTimeout(() => { window.location.replace("perfil.html"); }, 1200);
            return;
        }

        listaCategoriasServicos.textContent = "Carregando catálogo...";
        const [categorias, configuracao, horarios] = await Promise.all([
            buscarCategorias(), buscarConfiguracaoProfissional(), obterMinhasDisponibilidades(),
        ]);
        horariosDisponiveis = horarios;
        renderizarDisponibilidades();
        categoriasAtuais = categorias;
        (configuracao.ids_profissoes || []).forEach(id => selecionadas.add(Number(id)));
        if (configuracao.preco_hora !== null && configuracao.preco_hora !== undefined) {
            campoPrecoHoraServicos.value = configuracao.preco_hora;
        }
        campoDescricaoServicos.value = configuracao.descricao || "";
        campoExperienciaServicos.value = configuracao.experiencia || "";
        if (!categorias.length) {
            listaCategoriasServicos.textContent = "Não há profissões cadastradas no catálogo.";
            return;
        }
        renderizarCategorias(categorias);
        atualizarModoPublicado(selecionadas.size > 0 && Number(configuracao.preco_hora) > 0, nomesSelecionados(categorias));
    } catch (erro) {
        listaCategoriasServicos.textContent = erro.message;
    }
}

carregarServicosProfissional();
