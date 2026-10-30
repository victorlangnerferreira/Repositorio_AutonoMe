(() => {
    let tokenValido = false;
    try {
        const token = localStorage.getItem("token");
        const parte = token && token.split(".")[1];
        if (parte) {
            const payload = JSON.parse(atob(parte.replace(/-/g, "+").replace(/_/g, "/")));
            tokenValido = Number(payload.exp) * 1000 > Date.now();
        }
    } catch (_) {
        tokenValido = false;
    }

    if (!tokenValido) {
        try {
            localStorage.removeItem("token");
            localStorage.removeItem("usuario");
        } catch (_) { }
        document.documentElement.style.visibility = "hidden";
        window.location.replace("login.html");
    }
})();

const ITENS_MENU_HAMBURGUER = [
    { label: "Configurações", icone: "⚙️", href: "configuracao.html" },
    { label: "Notificações", icone: "🔔", href: "notificacoes.html" },
    { label: "Amigos", icone: "⭐", href: "amigos.html" },
    { label: "Fale Conosco", icone: "☎️", href: "suporte.html" },
];

const ITENS_NAVBAR_DESKTOP = [
    { label: "Início", href: "homepage.html" },
    { label: "Perfil", href: "perfil.html" },
    { label: "Conversas", href: "lista_chats.html" },
    { label: "Configurações", href: "configuracao.html" },
];

const ITENS_BOTTOMBAR = [
    { pagina: "homepage", icone: "🏠", href: "homepage.html", titulo: "Início" },
    { pagina: "perfil", icone: "✏️", href: "perfil.html", titulo: "Perfil" },
    { pagina: "lista_chats", icone: "💬", href: "lista_chats.html", titulo: "Conversas" },
];

function iniciaisDoNome(nome) {
    const partes = String(nome || "").trim().split(/\s+/).filter(Boolean);
    if (!partes.length) return "A";
    if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase();
    return (partes[0][0] + partes[1][0]).toUpperCase();
}

function mostrarAvatar(elemento, nome, foto) {
    if (!elemento) return;
    elemento.replaceChildren();
    if (!foto) {
        elemento.textContent = iniciaisDoNome(nome);
        return;
    }

    const imagem = document.createElement("img");
    const baseApi = window.AUTONOME_API_BASE_URL || "http://127.0.0.1:8000";
    imagem.src = foto.startsWith("blob:") || foto.startsWith("http")
        ? foto
        : `${baseApi}${foto}?v=${Date.now()}`;
    imagem.alt = "";
    imagem.addEventListener("error", function () {
        elemento.textContent = iniciaisDoNome(nome);
    }, { once: true });
    elemento.appendChild(imagem);
}

function salvarUsuarioLocal(usuario) {
    localStorage.setItem("usuario", JSON.stringify(usuario));
    window.dispatchEvent(new Event("autonome:usuario-atualizado"));
}

function atualizarAvataresSalvos() {
    let usuario = null;
    try { usuario = JSON.parse(localStorage.getItem("usuario") || "null"); } catch (_) { }
    if (!usuario) return;

    document.querySelectorAll(".avatar-btn").forEach(avatar => {
        mostrarAvatar(avatar, usuario.nome, usuario.foto);
    });
    document.querySelectorAll("[data-avatar-usuario-id]").forEach(avatar => {
        if (Number(avatar.dataset.avatarUsuarioId) === Number(usuario.id)) {
            mostrarAvatar(avatar, usuario.nome, usuario.foto);
        }
    });
}

window.addEventListener("storage", evento => {
    if (evento.key === "usuario") atualizarAvataresSalvos();
});
window.addEventListener("autonome:usuario-atualizado", atualizarAvataresSalvos);

function montarTopbar() {
    const placeholder = document.getElementById("topbar-placeholder");
    if (!placeholder) return;

    const tipo = document.body.dataset.topbar || "default";

    if (tipo === "back") {
        const titulo = document.body.dataset.titulo || "";
        const semEditar = document.body.dataset.semEditar === "true";

        placeholder.innerHTML = `
            <header class="topbar topbar-back">
                <div class="topbar-brand">
                    <button class="icon-btn" onclick="history.back()" aria-label="Voltar">←</button>
                    <a href="homepage.html" class="brand-logo">Autono<span>Me</span></a>
                </div>
                <span class="topbar-titulo">${titulo}</span>
                <div class="topbar-actions">
                    <nav class="desktop-nav">
                        <a href="homepage.html">Início</a>
                        <a href="perfil.html">Perfil</a>
                        <a href="lista_chats.html">Conversas</a>
                    </nav>
                    ${semEditar ? '<span class="icon-btn-espaco"></span>' : '<a href="editar_perfil.html" class="icon-btn" aria-label="Editar perfil">✎</a>'}
                </div>
            </header>`;
    } else {
        placeholder.innerHTML = `
            <header class="topbar">
                <div class="topbar-brand">
                    <a href="homepage.html" class="brand-logo">Autono<span>Me</span></a>
                </div>
                <nav class="desktop-nav">
                    ${ITENS_NAVBAR_DESKTOP.map(item => `<a href="${item.href}">${item.label}</a>`).join("")}
                </nav>
                <form class="topbar-search" action="ramo_especifico.html" method="get" role="search">
                    <label class="visualmente-oculto" for="busca-topbar">Buscar serviços ou profissionais</label>
                    <input type="search" id="busca-topbar" name="busca" placeholder="Buscar serviços ou profissionais..." autocomplete="off" required>
                    <button type="submit" class="btn-topbar-search">Buscar</button>
                </form>
                <div class="topbar-actions">
                    <a href="perfil.html" class="avatar-btn" aria-label="Meu perfil"></a>
                    <button type="button" id="btn-menu-hamburguer" class="icon-btn btn-menu-hamburguer" onclick="toggleMenu()" aria-label="Abrir menu" aria-expanded="false" aria-controls="dropdown-menu">☰</button>
                    <nav id="dropdown-menu" class="dropdown-menu escondido" aria-label="Menu complementar">
                        ${ITENS_MENU_HAMBURGUER.map(
                            (item) => `<a href="${item.href}">${item.icone} ${item.label}</a>`
                        ).join("")}
                    </nav>
                </div>
            </header>`;
    }

    const campoBuscaTopbar = placeholder.querySelector("#busca-topbar");
    if (campoBuscaTopbar) {
        campoBuscaTopbar.addEventListener("keydown", function (evento) {
            if (evento.key !== "Enter" || campoBuscaTopbar.value.trim()) return;
            evento.preventDefault();
            campoBuscaTopbar.value = "";
            const paginaInicial = new URL("homepage.html", window.location.href);
            if (window.location.pathname !== paginaInicial.pathname) {
                window.location.href = paginaInicial.href;
            } else {
                window.history.replaceState(null, "", paginaInicial.pathname);
            }
        });
    }

    const avatar = placeholder.querySelector(".avatar-btn");
    if (avatar) {
        let usuario = null;
        try { usuario = JSON.parse(localStorage.getItem("usuario") || "null"); } catch (_) { }
        mostrarAvatar(avatar, usuario && usuario.nome, usuario && usuario.foto);
    }
}

function montarBottombar() {
    const placeholder = document.getElementById("bottombar-placeholder");
    if (!placeholder) return;

    const paginaAtual = document.body.dataset.pagina || "";

    placeholder.innerHTML = `
        <footer class="bottombar">
            ${ITENS_BOTTOMBAR.map(
                (item) => `
                <a href="${item.href}"
                   class="bottombar-item ${item.pagina === paginaAtual ? "ativo" : ""}"
                   aria-label="${item.titulo}">${item.icone}</a>`
            ).join("")}
        </footer>`;
}

function toggleMenu() {
    const menu = document.getElementById("dropdown-menu");
    const botao = document.getElementById("btn-menu-hamburguer");
    if (!menu || !botao) return;
    const aberto = menu.classList.toggle("escondido") === false;
    botao.setAttribute("aria-expanded", String(aberto));
    botao.setAttribute("aria-label", aberto ? "Fechar menu" : "Abrir menu");
}

document.addEventListener("click", function (evento) {
    const menu = document.getElementById("dropdown-menu");
    const botao = evento.target.closest("#btn-menu-hamburguer");
    if (menu && !menu.classList.contains("escondido") && !menu.contains(evento.target) && !botao) {
        menu.classList.add("escondido");
        const botaoMenu = document.getElementById("btn-menu-hamburguer");
        botaoMenu?.setAttribute("aria-expanded", "false");
        botaoMenu?.setAttribute("aria-label", "Abrir menu");
    }
});

document.addEventListener("DOMContentLoaded", function () {
    montarTopbar();
    montarBottombar();
});

