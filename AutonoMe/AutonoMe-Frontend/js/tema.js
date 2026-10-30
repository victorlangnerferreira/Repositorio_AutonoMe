const chaveTema = "autonome-tema";

function aplicarTema(temaEscuro) {
    if (temaEscuro) document.documentElement.dataset.tema = "escuro";
    else delete document.documentElement.dataset.tema;
}

try {
    aplicarTema(localStorage.getItem(chaveTema) === "escuro");
} catch (_) { }

window.addEventListener("storage", function (evento) {
    if (evento.key === chaveTema || evento.key === null) {
        aplicarTema(evento.newValue === "escuro");
    }
});

document.addEventListener("DOMContentLoaded", function () {
    const alternarTema = document.getElementById("toggle-modo-escuro");
    const botaoSalvar = document.getElementById("btn-salvar-alteracoes");
    const mensagem = document.getElementById("feedback-config");

    if (!alternarTema || !botaoSalvar) return;

    try {
        alternarTema.checked = localStorage.getItem(chaveTema) === "escuro";
    } catch (_) { }

    alternarTema.addEventListener("change", function () {
        aplicarTema(alternarTema.checked);
        mensagem.textContent = "";
    });

    botaoSalvar.addEventListener("click", function () {
        try {
            if (alternarTema.checked) localStorage.setItem(chaveTema, "escuro");
            else localStorage.removeItem(chaveTema);
            mensagem.textContent = "Alterações salvas.";
        } catch (_) {
            mensagem.textContent = "Não foi possível salvar neste navegador.";
        }

        aplicarTema(alternarTema.checked);
    });
});
