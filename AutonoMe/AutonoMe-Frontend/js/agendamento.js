(function ativarCriacaoDePedido() {
    const botaoAntigo = document.getElementById("btn-contratar");
    const botao = botaoAntigo.cloneNode(true);
    botaoAntigo.replaceWith(botao);
    const dataInput = document.getElementById("data-servico");
    const horarioSelect = document.getElementById("horario-servico");
    const mensagemHorarios = document.getElementById("msg-horarios");
    const profissionalId = Number(new URLSearchParams(window.location.search).get("profissional_id"));
    const dataMinima = new Date();
    dataInput.min = new Date(dataMinima.getTime() - dataMinima.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    let requisicaoHorarios = 0;

    async function carregarHorariosDisponiveis() {
        const requisicao = ++requisicaoHorarios;
        horarioSelect.disabled = true;
        horarioSelect.replaceChildren(new Option(dataInput.value ? "Carregando horários..." : "Escolha uma data primeiro", ""));
        mensagemHorarios.textContent = "";
        if (!dataInput.value || !profissionalId) return;
        try {
            const horarios = await buscarDisponibilidadesProfissional(profissionalId, dataInput.value);
            if (requisicao !== requisicaoHorarios) return;
            if (!horarios.length) {
                horarioSelect.replaceChildren(new Option("Sem horários disponíveis", ""));
                mensagemHorarios.textContent = "Este prestador não tem horários livres nessa data.";
                return;
            }
            horarioSelect.replaceChildren(new Option("Selecione um horário", ""));
            horarios.forEach(item => horarioSelect.add(new Option(item.horario, item.horario)));
            horarioSelect.disabled = false;
            mensagemHorarios.textContent = `${horarios.length} horário(s) disponível(is).`;
        } catch (erro) {
            if (requisicao !== requisicaoHorarios) return;
            horarioSelect.replaceChildren(new Option("Horários indisponíveis", ""));
            mensagemHorarios.textContent = erro.message;
        }
    }

    dataInput.addEventListener("change", carregarHorariosDisponiveis);

    botao.addEventListener("click", async () => {
        const usuario = JSON.parse(localStorage.getItem("usuario") || "null");
        const mensagem = document.getElementById("msg-erro");
        const carregando = document.getElementById("msg-carregando");
        mensagem.style.display = "none";
        if (!usuario || !profissionalId) {
            mensagem.textContent = "Faça login e escolha um profissional da lista para pedir o serviço.";
            mensagem.style.display = "block";
            return;
        }
        if (!["cliente", "profissional"].includes(usuario.tipo)) {
            mensagem.textContent = "Entre em uma conta de contratante ou prestador para marcar um serviço.";
            mensagem.style.display = "block";
            return;
        }
        if (!dataInput.value || !horarioSelect.value || !document.getElementById("endereco-servico").value.trim()) {
            mensagem.textContent = "Informe a data, escolha um horário disponível e preencha o endereço.";
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
                horario: horarioSelect.value,
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
