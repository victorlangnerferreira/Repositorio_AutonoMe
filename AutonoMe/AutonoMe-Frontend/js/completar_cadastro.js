const formConfiguracaoInicial = document.getElementById("form-configuracao-inicial");
const campoEstadoInicial = document.getElementById("estado");
const campoCidadeInicial = document.getElementById("cidade");
const campoCidadeManual = document.getElementById("cidade-manual");
const mensagemCidades = document.getElementById("cidade-feedback");
const areaProfissionalInicial = document.getElementById("configuracao-profissional");
const buscaServicosIniciais = document.getElementById("busca-servicos-iniciais");
const listaServicosIniciais = document.getElementById("lista-servicos-iniciais");
const contagemServicosIniciais = document.getElementById("contagem-servicos-iniciais");
const campoPrecoHoraInicial = document.getElementById("preco-hora-inicial");
const botaoSalvarInicial = document.getElementById("btn-salvar-inicial");
const mensagemInicial = document.getElementById("mensagem-inicial");
const servicosIniciaisSelecionados = new Set();
let contaProfissional = false;
let estadosIbgeCarregados = null;
const cidadesPorEstado = new Map();
let requisicaoCidadesAtual = 0;
const normalizarNomeCidade = valor => valor.trim().normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");

async function carregarCidadesDoEstado(siglaEstado, cidadeSalva = "") {
    const requisicao = ++requisicaoCidadesAtual;
    campoCidadeInicial.hidden = false;
    campoCidadeInicial.required = true;
    campoCidadeInicial.disabled = true;
    campoCidadeInicial.replaceChildren(new Option(siglaEstado ? "Carregando cidades..." : "Selecione seu estado primeiro", ""));
    campoCidadeManual.hidden = true;
    campoCidadeManual.required = false;
    mensagemCidades.textContent = "";
    if (!siglaEstado) return;

    try {
        if (!estadosIbgeCarregados) {
            estadosIbgeCarregados = fetch("https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome")
                .then(resposta => {
                    if (!resposta.ok) throw new Error("Falha ao carregar os estados.");
                    return resposta.json();
                });
        }
        const estados = await estadosIbgeCarregados;
        const estado = estados.find(item => item.sigla === siglaEstado);
        if (!estado) throw new Error("Estado não encontrado.");

        let cidades = cidadesPorEstado.get(siglaEstado);
        if (!cidades) {
            const resposta = await fetch(`https://servicodados.ibge.gov.br/api/v1/localidades/estados/${estado.id}/municipios?orderBy=nome`);
            if (!resposta.ok) throw new Error("Falha ao carregar as cidades.");
            cidades = await resposta.json();
            cidadesPorEstado.set(siglaEstado, cidades);
        }
        if (requisicao !== requisicaoCidadesAtual || campoEstadoInicial.value !== siglaEstado) return;

        campoCidadeInicial.replaceChildren(new Option("Selecione sua cidade", ""));
        const cidadeNormalizada = normalizarNomeCidade(cidadeSalva);
        let cidadeCorrespondente = "";
        cidades.forEach(cidade => {
            const opcao = new Option(cidade.nome, cidade.nome);
            campoCidadeInicial.add(opcao);
            if (normalizarNomeCidade(cidade.nome) === cidadeNormalizada) cidadeCorrespondente = cidade.nome;
        });
        if (cidadeSalva && !cidadeCorrespondente) {
            campoCidadeInicial.add(new Option(`${cidadeSalva} (cadastrada)`, cidadeSalva));
            cidadeCorrespondente = cidadeSalva;
        }
        campoCidadeInicial.value = cidadeCorrespondente;
        campoCidadeInicial.disabled = false;
    } catch (erro) {
        if (requisicao !== requisicaoCidadesAtual) return;
        campoCidadeInicial.hidden = true;
        campoCidadeInicial.required = false;
        campoCidadeManual.hidden = false;
        campoCidadeManual.required = true;
        campoCidadeManual.value = cidadeSalva;
        mensagemCidades.textContent = "Não foi possível carregar a lista. Digite sua cidade manualmente.";
    }
}

campoEstadoInicial.addEventListener("change", async () => {
    campoCidadeInicial.value = "";
    campoCidadeManual.value = "";
    botaoSalvarInicial.disabled = true;
    const estadoAtual = campoEstadoInicial.value;
    await carregarCidadesDoEstado(estadoAtual);
    if (campoEstadoInicial.value === estadoAtual) botaoSalvarInicial.disabled = false;
});

function atualizarContagemServicosIniciais() {
    const total = servicosIniciaisSelecionados.size;
    contagemServicosIniciais.textContent = `${total} ${total === 1 ? "serviço selecionado" : "serviços selecionados"}`;
}

function filtrarServicosIniciais() {
    const termo = buscaServicosIniciais.value.trim().toLocaleLowerCase("pt-BR");
    listaServicosIniciais.querySelectorAll(".servicos-categoria").forEach(categoria => {
        let visiveis = 0;
        categoria.querySelectorAll(".servico-opcao").forEach(opcao => {
            const corresponde = opcao.dataset.nome.toLocaleLowerCase("pt-BR").includes(termo);
            opcao.hidden = !corresponde;
            if (corresponde) visiveis++;
        });
        categoria.hidden = visiveis === 0;
    });
}

function renderizarServicosIniciais(categorias) {
    listaServicosIniciais.replaceChildren();
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
            (categoria.profissoes || []).forEach(profissao => servicosIniciaisSelecionados.add(Number(profissao.id_profissao)));
            secao.querySelectorAll("input[type=checkbox]").forEach(caixa => { caixa.checked = true; });
            atualizarContagemServicosIniciais();
        });
        cabecalho.append(titulo, selecionarTodos);

        const descricao = document.createElement("p");
        descricao.className = "servicos-categoria-descricao";
        descricao.textContent = categoria.descricao || "Escolha os serviços que você oferece.";
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
            caixa.checked = servicosIniciaisSelecionados.has(id);
            caixa.addEventListener("change", () => {
                if (caixa.checked) servicosIniciaisSelecionados.add(id);
                else servicosIniciaisSelecionados.delete(id);
                atualizarContagemServicosIniciais();
            });
            const nome = document.createElement("span");
            nome.textContent = profissao.nome || "Profissão";
            opcao.append(caixa, nome);
            opcoes.appendChild(opcao);
        });

        secao.append(cabecalho, descricao, opcoes);
        listaServicosIniciais.appendChild(secao);
    });
    listaServicosIniciais.setAttribute("aria-busy", "false");
    atualizarContagemServicosIniciais();
    filtrarServicosIniciais();
}

buscaServicosIniciais.addEventListener("input", filtrarServicosIniciais);

async function carregarConfiguracaoInicial() {
    botaoSalvarInicial.disabled = true;
    mensagemInicial.textContent = "Carregando seu cadastro...";
    try {
        const configuracao = await obterConfiguracaoInicial();
        if (configuracao.perfil_completo) {
            window.location.replace("homepage.html");
            return;
        }
        campoEstadoInicial.value = configuracao.estado || "";
        await carregarCidadesDoEstado(configuracao.estado || "", configuracao.cidade || "");
        contaProfissional = configuracao.tipo === "profissional";

        if (contaProfissional) {
            areaProfissionalInicial.hidden = false;
            campoPrecoHoraInicial.required = true;
            (configuracao.ids_profissoes || []).forEach(id => servicosIniciaisSelecionados.add(Number(id)));
            if (configuracao.preco_hora) campoPrecoHoraInicial.value = configuracao.preco_hora;
            const categorias = await buscarCategorias();
            renderizarServicosIniciais(categorias);
            if (!categorias.length) listaServicosIniciais.textContent = "O catálogo de serviços está vazio.";
        } else {
            areaProfissionalInicial.hidden = true;
            campoPrecoHoraInicial.required = false;
            listaServicosIniciais.setAttribute("aria-busy", "false");
        }
        mensagemInicial.textContent = "";
        botaoSalvarInicial.disabled = false;
    } catch (erro) {
        mensagemInicial.textContent = erro.message || "Não foi possível carregar seus dados. Tente novamente.";
    }
}

formConfiguracaoInicial.addEventListener("submit", async evento => {
    evento.preventDefault();
    mensagemInicial.textContent = "";

    const dados = {
        estado: campoEstadoInicial.value,
        cidade: campoCidadeManual.hidden ? campoCidadeInicial.value : campoCidadeManual.value.trim(),
    };
    if (!dados.cidade) {
        mensagemInicial.textContent = "Selecione ou informe sua cidade.";
        (campoCidadeManual.hidden ? campoCidadeInicial : campoCidadeManual).focus();
        return;
    }
    if (contaProfissional) {
        const precoHora = Number(campoPrecoHoraInicial.value);
        if (!servicosIniciaisSelecionados.size) {
            mensagemInicial.textContent = "Selecione pelo menos um serviço que você oferece.";
            return;
        }
        if (!Number.isFinite(precoHora) || precoHora <= 0) {
            mensagemInicial.textContent = "Informe uma taxa por hora maior que zero.";
            return;
        }
        dados.ids_profissoes = [...servicosIniciaisSelecionados];
        dados.preco_hora = precoHora;
    }

    botaoSalvarInicial.disabled = true;
    mensagemInicial.textContent = "Salvando...";
    try {
        const resultado = await salvarConfiguracaoInicial(dados);
        const usuario = JSON.parse(localStorage.getItem("usuario") || "{}");
        localStorage.setItem("usuario", JSON.stringify({
            ...usuario,
            estado: resultado.estado,
            cidade: resultado.cidade,
            perfil_completo: resultado.perfil_completo,
        }));
        mensagemInicial.textContent = "Cadastro salvo. Abrindo o AutonoMe...";
        window.location.replace("homepage.html");
    } catch (erro) {
        mensagemInicial.textContent = erro.message || "Não foi possível salvar seus dados.";
        botaoSalvarInicial.disabled = false;
    }
});

carregarConfiguracaoInicial();
