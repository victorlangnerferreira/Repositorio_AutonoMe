const botaoLogoff = document.getElementById("btn-logoff");
const toastLogoff = document.createElement("div");
toastLogoff.className = "toast toast-sucesso";
toastLogoff.setAttribute("role", "status");
toastLogoff.setAttribute("aria-live", "polite");
document.body.appendChild(toastLogoff);

function limparSessaoEIrParaLogin() {
    localStorage.removeItem("token");
    localStorage.removeItem("usuario");
    window.location.replace("login.html");
}

botaoLogoff.addEventListener("click", async function () {
    botaoLogoff.disabled = true;
    try { await encerrarSessao(); } catch (_) { }
    toastLogoff.textContent = "Você saiu da sua conta.";
    toastLogoff.classList.add("toast-visivel");
    window.setTimeout(limparSessaoEIrParaLogin, 800);
});

const botaoDesativar = document.getElementById("btn-desativar-conta");
const senhaDesativacao = document.getElementById("senha-desativacao");
const checkboxConfirmarDesativacao = document.getElementById("confirmar-desativacao");
const feedbackDesativacao = document.getElementById("feedback-desativacao");
const codigoDesativacaoArea = document.getElementById("codigo-desativacao-area");
const campoCodigoDesativacao = document.getElementById("codigo-desativacao");
const botaoReenviarCodigo = document.getElementById("btn-reenviar-codigo-desativacao");
let codigoDesativacaoEnviado = false;

campoCodigoDesativacao.addEventListener("input", function () {
    campoCodigoDesativacao.value = campoCodigoDesativacao.value.replace(/[^a-z0-9]/gi, "").slice(0, 6).toUpperCase();
});

botaoReenviarCodigo.addEventListener("click", async function () {
    botaoReenviarCodigo.disabled = true;
    try {
        await solicitarCodigoDesativacao(senhaDesativacao.value);
        feedbackDesativacao.textContent = "Enviamos um novo código para seu e-mail.";
    } catch (erro) {
        feedbackDesativacao.textContent = erro.message;
    } finally {
        botaoReenviarCodigo.disabled = false;
    }
});

botaoDesativar.addEventListener("click", async function () {
    feedbackDesativacao.textContent = "";
    if (!codigoDesativacaoEnviado) {
        if (!senhaDesativacao.value || !checkboxConfirmarDesativacao.checked) {
            feedbackDesativacao.textContent = "Informe sua senha e marque a confirmação para continuar.";
            return;
        }
        if (!window.confirm("Enviar um código para confirmar a desativação da sua conta?")) return;
    } else if (!campoCodigoDesativacao.value) {
        feedbackDesativacao.textContent = "Informe o código de 6 caracteres enviado ao seu e-mail.";
        return;
    }

    botaoDesativar.disabled = true;
    botaoDesativar.textContent = codigoDesativacaoEnviado ? "Confirmando..." : "Enviando código...";
    try {
        if (!codigoDesativacaoEnviado) {
            await solicitarCodigoDesativacao(senhaDesativacao.value);
            codigoDesativacaoEnviado = true;
            codigoDesativacaoArea.hidden = false;
            campoCodigoDesativacao.disabled = false;
            campoCodigoDesativacao.required = true;
            senhaDesativacao.disabled = true;
            checkboxConfirmarDesativacao.disabled = true;
            botaoDesativar.textContent = "Confirmar código e desativar";
            feedbackDesativacao.textContent = "Código enviado. Digite-o para concluir a desativação.";
        } else {
            await confirmarDesativacao(campoCodigoDesativacao.value);
            limparSessaoEIrParaLogin();
        }
    } catch (erro) {
        feedbackDesativacao.textContent = erro.message;
    } finally {
        botaoDesativar.disabled = false;
        if (!codigoDesativacaoEnviado) botaoDesativar.textContent = "Desativar conta";
    }
});
