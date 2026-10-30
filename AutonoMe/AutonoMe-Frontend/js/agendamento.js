(function ativarCriacaoDePedido() {
    const botaoAntigo = document.getElementById("btn-contratar");
    const botao = botaoAntigo.cloneNode(true);
    botaoAntigo.replaceWith(botao);
    const dataInput = document.getElementById("data-servico");
    const dataMinima = new Date();
    dataInput.min = new Date(dataMinima.getTime() - dataMinima.getTimezoneOffset() * 60000).toISOString().slice(0, 10);

    botao.addEventListener("click", async () => {
        const usuario = JSON.parse(localStorage.getItem("usuario") || "null");
        const profissionalId = Number(new URLSearchParams(window.location.search).get("profissional_id"));
        const mensagem = document.getElementById("msg-erro");
        const carregando = document.getElementById("msg-carregando");
        mensagem.style.display = "none";
        if (!usuario || !profissionalId) {
            mensagem.textContent = "Faça login e escolha um profissional da lista para pedir o serviço.";
            mensagem.style.display = "block";
            return;
        }
        if (!dataInput.value || !document.getElementById("endereco-servico").value.trim()) {
            mensagem.textContent = "Informe a data e o endereço do serviço.";
            mensagem.style.display = "block";
            return;
        }

        botao.disabled = true;
        carregando.textContent = "Enviando pedido...";
        carregando.style.display = "block";
        try {
        const respostaProfissionais = await apiFetch(`${API_BASE_URL}/profissionais`);
            const profissionais = await respostaProfissionais.json();
            const profissional = profissionais.find(item => Number(item.id_profissional) === profissionalId);
            if (!profissional) throw new Error("Profissional não encontrado.");
            await criarContratacao({
                cliente_id: usuario.id,
                profissional_id: profissionalId,
                data_servico: dataInput.value,
                horario: document.getElementById("horario-servico").value,
                endereco: document.getElementById("endereco-servico").value.trim(),
                valor: profissional.preco_hora || 0,
            });
            carregando.textContent = "Pedido enviado. Veja o histórico para acompanhar e adicionar notas.";
            botao.textContent = "Pedido enviado";
        } catch (erro) {
            carregando.style.display = "none";
            mensagem.textContent = erro.message;
            mensagem.style.display = "block";
            botao.disabled = false;
        }
    });
})();
