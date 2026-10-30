async function carregarHistoricoPedidos() {
    const container = document.getElementById("painel-contratados");
    const relatorio = document.getElementById("relatorio-pedidos");
    const usuario = JSON.parse(localStorage.getItem("usuario") || "null");
    if (!usuario) {
        container.textContent = "Entre na sua conta para ver pedidos e notas.";
        return;
    }

    try {
        const [pedidos, resumo] = await Promise.all([
            buscarContratacoes(usuario.id),
            buscarRelatorio(usuario.id),
        ]);
        [
            [resumo.total_pedidos, "Pedidos"],
            [resumo.pendentes, "Pendentes"],
            [resumo.concluidos, "Concluídos"],
            [`R$ ${Number(resumo.valor_total).toFixed(2)}`, "Valor total"],
            [resumo.notificacoes_nao_lidas, "Notificações novas"],
            [resumo.mensagens_enviadas, "Mensagens enviadas"],
        ].forEach(([valor, titulo]) => {
            const indicador = document.createElement("div");
            indicador.className = "relatorio-indicador";
            const dado = document.createElement("strong");
            dado.textContent = valor;
            const legenda = document.createElement("span");
            legenda.textContent = titulo;
            indicador.append(dado, legenda);
            relatorio.appendChild(indicador);
        });

        if (!pedidos.length) {
            container.textContent = "Nenhum pedido registrado.";
            return;
        }

        container.replaceChildren();
        for (const pedido of pedidos) {
            const souCliente = Number(pedido.id_cliente) === Number(usuario.id);
            const outroId = souCliente ? pedido.profissional_usuario_id : pedido.id_cliente;
            const outroNome = souCliente ? pedido.profissional_nome : pedido.cliente_nome;
            const card = document.createElement("section");
            card.className = "pedido-card";

            const titulo = document.createElement("h3");
            titulo.append("Pedido com ");
            const perfil = document.createElement("a");
            perfil.href = `perfil.html?usuario_id=${outroId}`;
            perfil.textContent = outroNome;
            titulo.appendChild(perfil);

            const resumoPedido = document.createElement("p");
            resumoPedido.className = "pedido-resumo";
            resumoPedido.textContent = `${pedido.data_servico || "Data a definir"} · ${pedido.status} · R$ ${Number(pedido.valor).toFixed(2)}`;

            const tituloNotas = document.createElement("strong");
            tituloNotas.textContent = "Notas do pedido";
            const notas = document.createElement("div");
            notas.className = "notas-lista";
            const campo = document.createElement("textarea");
            campo.maxLength = 2000;
            campo.placeholder = "Anote detalhes deste pedido";
            const salvar = document.createElement("button");
            salvar.type = "button";
            salvar.className = "btn-submit";
            salvar.textContent = "Salvar nota";
            const aviso = document.createElement("span");
            aviso.className = "mensagem-nota";
            card.append(titulo, resumoPedido, tituloNotas, notas, campo, salvar, aviso);

            const carregarNotas = async () => {
                const lista = await buscarNotasPedido(pedido.id_contratacao, usuario.id);
                notas.replaceChildren();
                lista.forEach(nota => {
                    const linha = document.createElement("p");
                    linha.textContent = `${nota.texto} · ${new Date(nota.data_criacao).toLocaleString()}`;
                    notas.appendChild(linha);
                });
            };
            salvar.addEventListener("click", async () => {
                if (!campo.value.trim()) return;
                salvar.disabled = true;
                try {
                    await salvarNotaPedido(pedido.id_contratacao, usuario.id, campo.value.trim());
                    campo.value = "";
                    aviso.textContent = "Nota salva.";
                    await carregarNotas();
                } catch (erro) {
                    aviso.textContent = erro.message;
                } finally {
                    salvar.disabled = false;
                }
            });
            await carregarNotas();
            container.appendChild(card);
        }
    } catch (erro) {
        container.textContent = `Não foi possível carregar o histórico: ${erro.message}`;
    }
}

carregarHistoricoPedidos();
