const usuarioAtual = JSON.parse(localStorage.getItem("usuario") || "null");
const formularioPerfil = document.getElementById("form-editar-perfil");
const mensagemPerfil = document.getElementById("feedback-perfil");
const botaoSalvarPerfil = document.getElementById("btn-salvar-perfil");
const campoNomePerfil = document.getElementById("nome");
const avatarPrevia = document.getElementById("avatar-previa");
const campoTelefonePerfil = document.getElementById("telefone");
const campoArquivoFoto = document.getElementById("arquivo-foto-perfil");
const botaoEnviarFoto = document.getElementById("btn-enviar-foto");
const mensagemFoto = document.getElementById("feedback-foto");
const controlesRecorte = document.getElementById("controles-recorte-foto");
const canvasPreviaRecorte = document.getElementById("foto-recorte-preview");
const contextoPreviaRecorte = canvasPreviaRecorte.getContext("2d");
const imagemRecorte = new Image();
const controleZoom = document.getElementById("zoom-foto");
const controleHorizontal = document.getElementById("posicao-horizontal-foto");
const controleVertical = document.getElementById("posicao-vertical-foto");
let fotoPerfilAtual = usuarioAtual && usuarioAtual.foto;
let urlFotoTemporaria = null;
if (usuarioAtual) avatarPrevia.dataset.avatarUsuarioId = usuarioAtual.id;

function formatarTelefone(valor) {
    const numeros = String(valor || "").replace(/\D/g, "").slice(0, 11);
    if (!numeros) return "";
    if (numeros.length <= 2) return `(${numeros}`;
    const ddd = numeros.slice(0, 2);
    const restante = numeros.slice(2);
    if (numeros.length <= 10) {
        return `(${ddd}) ${restante.length > 4 ? `${restante.slice(0, 4)}-${restante.slice(4)}` : restante}`;
    }
    return `(${ddd}) ${restante.slice(0, 5)}-${restante.slice(5)}`;
}

function validarTelefonePerfil() {
    const quantidade = campoTelefonePerfil.value.replace(/\D/g, "").length;
    campoTelefonePerfil.setCustomValidity(
        quantidade && quantidade !== 10 && quantidade !== 11
            ? "Informe um telefone com DDD e 8 ou 9 dígitos."
            : ""
    );
}

function atualizarPreviaAvatar() {
    mostrarAvatar(avatarPrevia, campoNomePerfil.value, fotoPerfilAtual);
}

function atualizarPreviaRecorte() {
    if (!imagemRecorte.naturalWidth) return;
    const recorte = calcularRetanguloRecorte();
    contextoPreviaRecorte.clearRect(0, 0, canvasPreviaRecorte.width, canvasPreviaRecorte.height);
    contextoPreviaRecorte.drawImage(
        imagemRecorte,
        recorte.x, recorte.y, recorte.lado, recorte.lado,
        0, 0, canvasPreviaRecorte.width, canvasPreviaRecorte.height
    );
}

function calcularRetanguloRecorte() {
    const zoom = Number(controleZoom.value) / 100;
    const lado = Math.min(imagemRecorte.naturalWidth, imagemRecorte.naturalHeight) / zoom;
    return {
        lado,
        x: (imagemRecorte.naturalWidth - lado) * Number(controleHorizontal.value) / 100,
        y: (imagemRecorte.naturalHeight - lado) * Number(controleVertical.value) / 100,
    };
}

function criarFotoEnquadrada() {
    const recorte = calcularRetanguloRecorte();
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 512;
    canvas.getContext("2d").drawImage(imagemRecorte, recorte.x, recorte.y, recorte.lado, recorte.lado, 0, 0, 512, 512);
    return new Promise((resolve, reject) => {
        canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error("Não foi possível preparar a foto.")), "image/jpeg", 0.92);
    });
}

campoNomePerfil.addEventListener("input", atualizarPreviaAvatar);
campoTelefonePerfil.addEventListener("input", function () {
    campoTelefonePerfil.value = formatarTelefone(campoTelefonePerfil.value);
    validarTelefonePerfil();
});

campoArquivoFoto.addEventListener("change", function () {
    const arquivo = campoArquivoFoto.files[0];
    botaoEnviarFoto.disabled = true;
    mensagemFoto.textContent = "";
    if (!arquivo) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(arquivo.type)) {
        campoArquivoFoto.value = "";
        mensagemFoto.textContent = "Escolha uma imagem JPG, PNG ou WEBP.";
        return;
    }
    if (arquivo.size > 5 * 1024 * 1024) {
        campoArquivoFoto.value = "";
        botaoEnviarFoto.disabled = true;
        mensagemFoto.textContent = "A foto deve ter no máximo 5 MB.";
        return;
    }
    if (urlFotoTemporaria) URL.revokeObjectURL(urlFotoTemporaria);
    urlFotoTemporaria = URL.createObjectURL(arquivo);
    controlesRecorte.hidden = false;
    controleZoom.value = "100";
    controleHorizontal.value = "50";
    controleVertical.value = "50";
    imagemRecorte.src = urlFotoTemporaria;
    atualizarPreviaRecorte();
});

imagemRecorte.addEventListener("load", function () {
    atualizarPreviaRecorte();
    botaoEnviarFoto.disabled = false;
});

imagemRecorte.addEventListener("error", function () {
    botaoEnviarFoto.disabled = true;
    mensagemFoto.textContent = "Não foi possível abrir essa imagem.";
});

[controleZoom, controleHorizontal, controleVertical].forEach(controle => {
    controle.addEventListener("input", atualizarPreviaRecorte);
});

botaoEnviarFoto.addEventListener("click", async function () {
    if (!campoArquivoFoto.files[0] || !imagemRecorte.complete || !imagemRecorte.naturalWidth) return;
    botaoEnviarFoto.disabled = true;
    mensagemFoto.textContent = "Enviando foto...";
    try {
        const fotoEnquadrada = await criarFotoEnquadrada();
        const resposta = await enviarFotoPerfil(new File([fotoEnquadrada], "foto-perfil.jpg", { type: "image/jpeg" }));
        fotoPerfilAtual = resposta.foto;
        usuarioAtual.foto = resposta.foto;
        salvarUsuarioLocal(usuarioAtual);
        mostrarAvatar(avatarPrevia, campoNomePerfil.value, fotoPerfilAtual);
        controlesRecorte.hidden = true;
        campoArquivoFoto.value = "";
        mensagemFoto.textContent = "Foto de perfil atualizada.";
    } catch (erro) {
        mensagemFoto.textContent = erro.message;
        botaoEnviarFoto.disabled = false;
    }
});

async function carregarDadosPerfil() {
    if (!usuarioAtual) {
        window.location.href = "login.html";
        return;
    }

    try {
        const perfil = await buscarUsuario(usuarioAtual.id);
        fotoPerfilAtual = perfil.foto || null;
        usuarioAtual.foto = fotoPerfilAtual;
        salvarUsuarioLocal(usuarioAtual);
        campoNomePerfil.value = perfil.nome || "";
        atualizarPreviaAvatar();
        document.getElementById("email").value = perfil.email || "";
        campoTelefonePerfil.value = formatarTelefone(perfil.telefone || "");
        validarTelefonePerfil();
    } catch (erro) {
        mensagemPerfil.textContent = erro.message;
    }
}

formularioPerfil.addEventListener("submit", async function (evento) {
    evento.preventDefault();
    botaoSalvarPerfil.disabled = true;
    mensagemPerfil.textContent = "Salvando...";

    try {
        const dados = {
            nome: document.getElementById("nome").value.trim(),
            email: document.getElementById("email").value.trim(),
            telefone: document.getElementById("telefone").value.trim() || null,
        };
        const usuarioAtualizado = await atualizarPerfil(dados);
        usuarioAtual.nome = usuarioAtualizado.nome;
        usuarioAtual.email = usuarioAtualizado.email;
        usuarioAtualizado.foto = fotoPerfilAtual || null;
        salvarUsuarioLocal(usuarioAtualizado);
        mensagemPerfil.textContent = "Perfil atualizado com sucesso.";
    } catch (erro) {
        mensagemPerfil.textContent = erro.message;
    } finally {
        botaoSalvarPerfil.disabled = false;
    }
});

carregarDadosPerfil();
