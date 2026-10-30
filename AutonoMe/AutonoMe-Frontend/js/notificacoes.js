(async function ativarNotificacoes() {
    const container = document.getElementById("lista-notificacoes");
    const usuario = JSON.parse(localStorage.getItem("usuario") || "null");
    const botaoAntigo = document.querySelector(".btn-perigo");
    if (botaoAntigo) {
        const botao = botaoAntigo.cloneNode(true);
        botao.removeAttribute("onclick");
        botao.textContent = "Marcar todas como lidas";
        botaoAntigo.replaceWith(botao);
        botao.addEventListener("click", async () => {
            if (!usuario) return;
            try {
                await marcarTodasNotificacoesLidas(usuario.id);
                await carregar();
            } catch (erro) { container.textContent = erro.message; }
        });
    }
    if (!usuario) {
        container.textContent = "Entre na sua conta para ver notificações.";
        return;
    }

    async function carregar() {
        try {
            const itens = await buscarNotificacoes(usuario.id);
            container.replaceChildren();
            if (!itens.length) {
                container.textContent = "Sem notificações.";
                return;
            }
            itens.forEach(item => {
                const linha = document.createElement("div");
                linha.className = "item-notificacao";
                linha.classList.toggle("notificacao-lida", item.visualizada);
                const texto = document.createElement("div");
                const titulo = document.createElement("strong");
                titulo.textContent = item.titulo || "Notificação";
                const mensagem = document.createElement("p");
                mensagem.textContent = item.mensagem || "";
                texto.append(titulo, mensagem);
                const botao = document.createElement("button");
                botao.type = "button";
                botao.textContent = item.visualizada ? "Lida" : "Marcar como lida";
                botao.disabled = item.visualizada;
                botao.addEventListener("click", async () => {
                    try {
                        await marcarNotificacaoLida(item.id_notificacao, usuario.id);
                        await carregar();
                    } catch (erro) { mensagem.textContent = erro.message; }
                });
                linha.append(texto, botao);
                container.appendChild(linha);
            });
        } catch (erro) {
            container.textContent = `Erro ao carregar notificações: ${erro.message}`;
        }
    }

    carregar();
})();
