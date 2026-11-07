const categories = [
  { name: "Construção Civil", icon: "🧱", services: ["Pedreiro", "Encanador", "Servente de obras", "Eletricista", "Pintor", "Azulejista", "Gesseiro", "Carpinteiro", "Marceneiro", "Serralheiro", "Vidraceiro", "Telhadista", "Instalador de ar-condicionado", "Montador de móveis", "Impermeabilizador"] },
  { name: "Trabalho Doméstico", icon: "🏡", services: ["Diarista", "Faxineiro", "Cozinheiro", "Babá", "Jardineiro", "Cuidador de idosos", "Caseiro", "Passadeira de roupas", "Lavadeira", "Organizador residencial", "Marido de aluguel"] },
  { name: "Entregas e Logística", icon: "🛵", services: ["Entregador de bicicleta", "Entregador de moto", "Motoboy", "Entregador de aplicativo", "Freteiro", "Carreteiro", "Ajudante de mudança", "Carregador", "Coletor de encomendas"] },
  { name: "Beleza e Bem-estar", icon: "💇", services: ["Cabeleireiro", "Barbeiro", "Manicure", "Pedicure", "Designer de sobrancelhas", "Maquiador", "Depilador", "Trancista", "Massoterapeuta", "Personal trainer", "Professor de dança"] },
  { name: "Alimentação", icon: "🍲", services: ["Cozinheiro", "Confeiteiro", "Padeiro artesanal", "Salgadeiro", "Marmiteiro", "Churrasqueiro", "Garçom", "Bartender", "Pizzaiolo", "Vendedor de alimentos"] },
  { name: "Reparos e Assistência", icon: "🧰", services: ["Mecânico de automóveis", "Mecânico de motos", "Borracheiro", "Eletricista automotivo", "Conserto de celulares", "Conserto de computadores", "Técnico de informática", "Conserto de eletrodomésticos", "Costureiro", "Sapateiro", "Chaveiro", "Tapeceiro", "Limpeza de estofados", "Instalador de câmeras"] },
  { name: "Transporte", icon: "🚗", services: ["Motorista particular", "Motorista de aplicativo", "Motorista para eventos", "Transporte escolar", "Motorista de van", "Carreto", "Transporte de animais"] },
  { name: "Entretenimento e Eventos", icon: "🎭", services: ["Músico", "DJ", "Ator", "Animador de festas", "Recreador infantil", "Fotógrafo", "Videomaker", "Decoração de eventos", "Cerimonialista", "Recepcionista de eventos", "Garçom para eventos"] },
  { name: "Aulas e Serviços Digitais", icon: "💻", services: ["Professor particular", "Reforço escolar", "Professor de idiomas", "Professor de música", "Designer gráfico", "Social media", "Editor de vídeo", "Redator", "Tradutor", "Suporte de informática", "Digitação e currículo"] },
  { name: "Pets e Animais", icon: "🐾", services: ["Passeador de cães", "Pet sitter", "Banho e tosa", "Adestrador", "Cuidador de animais", "Transporte de pets"] },
  { name: "Serviços Pessoais", icon: "🤝", services: ["Costureiro", "Lavador de carros", "Cuidador de crianças", "Acompanhante de idosos", "Compras e recados", "Montador de móveis", "Organizador de mudanças"] },
  { name: "Outros serviços", icon: "✦", services: ["Artesanato", "Vendedor autônomo", "Artesão", "Outro serviço"] },
];

const state = {
  view: "auth",
  authMode: "login",
  pendingEmail: "",
  userEmail: "",
  verificationPurpose: "register",
  authInitialized: false,
  user: "Visitante",
  userId: "",
  userRole: "client",
  profileBio: "",
  profileLocation: "",
  profilePhoto: "",
  category: "",
  service: "",
  provider: null,
  bookingAddress: "",
  publicListings: [],
  contracts: [],
  contractTab: "requested",
  messages: [],
  activeChat: null,
  chatMessages: [],
  conversations: [],
  activeConversationId: "",
  favorites: [],
  ownListings: [],
  editingListingId: "",
  providerAvailability: [],
  availableTimes: [],
  availabilityConfigured: false,
  availabilityLoading: false,
  contractNotes: [],
  notifications: [],
  selectedDay: 0,
  selectedTime: "",
  bookingDetails: "",
  selectedStars: 0,
  drawerOpen: false,
  contactType: "Sugestão",
  query: "",
  settings: { "Notificações": true, "Modo Escuro": false, "Permitir localização": false, "Permitir microfone": false, "Permitir câmera": false },
};

const STORAGE_KEY_PREFIX = "autonome-user-state-v1-";

function restoreAppState() {
  if (!state.userId) return;
  try {
    const saved = JSON.parse(localStorage.getItem(`${STORAGE_KEY_PREFIX}${state.userId}`) || "null");
    if (!saved || typeof saved !== "object") return;
    for (const key of ["ownListings", "favorites", "contracts", "messages", "settings"]) {
      if (saved[key] !== undefined) state[key] = saved[key];
    }
    state.contracts = [];
    state.messages = [];
    state.favorites = state.favorites.filter((provider) => !String(provider.id || "").startsWith("demo-"));
    state.settings = { ...state.settings, ...(saved.settings || {}) };
    saveAppState();
  } catch (error) {
    console.error("Não foi possível carregar os dados locais do AutonoMe.", error);
  }
}

function saveAppState() {
  if (!state.userId) return;
  try {
    const saved = Object.fromEntries(["ownListings", "favorites", "contracts", "messages", "settings"].map((key) => [key, state[key]]));
    localStorage.setItem(`${STORAGE_KEY_PREFIX}${state.userId}`, JSON.stringify(saved));
  } catch (error) {
    console.error("Não foi possível salvar os dados locais do AutonoMe.", error);
  }
}

restoreAppState();

const app = document.querySelector("#app");
const weekdays = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
let toastTimer;
let chatPollTimer;
let chatPollBusy = false;

function esc(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function initials(name) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0] || "").join("").toUpperCase();
}

function avatar(label, large = false, photo = "") {
  return `<span class="avatar${large ? " large" : ""}" aria-hidden="true">${photo ? `<img src="${esc(photo)}" alt="">` : esc(label)}</span>`;
}

function button(text, action, options = {}) {
  const classes = ["button", options.variant || "", options.small ? "small" : ""].filter(Boolean).join(" ");
  const extra = options.disabled ? " disabled" : "";
  return `<button class="${classes}" type="button" data-action="${esc(action)}"${extra}>${text}</button>`;
}

function allListings() {
  return state.publicListings;
}

function activeBookings() {
  return state.contracts.filter((contract) => contract.tab === "requested"
    && !["Cancelada", "Concluído", "Pedido negado"].includes(contract.state));
}

function isProviderBooked(provider) {
  return Boolean(provider.isBooked) || activeBookings().some((contract) => (
    (contract.providerId && contract.providerId === provider.id)
    || (contract.name === provider.name && contract.service === provider.service)
  ));
}

function normalizedSearch(value) {
  return value.toLocaleLowerCase("pt-BR").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function digitsOnly(value) {
  return value.replace(/\D/g, "");
}

function formatCPF(value) {
  const digits = digitsOnly(value).slice(0, 11);
  return digits
    .replace(/^(\d{3})(\d)/, "$1.$2")
    .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1-$2");
}

function formatBrazilianPhone(value) {
  const digits = digitsOnly(value).slice(0, 11);
  if (digits.length <= 2) return digits ? `(${digits}` : "";
  const areaCode = digits.slice(0, 2);
  const number = digits.slice(2);
  const splitAt = digits.length > 10 ? 5 : 4;
  return `(${areaCode}) ${number.length > splitAt ? `${number.slice(0, splitAt)}-${number.slice(splitAt)}` : number}`;
}

function isValidCPF(value) {
  const cpf = digitsOnly(value);
  if (cpf.length !== 11 || /^(\d)\1{10}$/.test(cpf)) return false;
  const calculateDigit = (length) => {
    const sum = Array.from(cpf.slice(0, length), (digit, index) => Number(digit) * (length + 1 - index))
      .reduce((total, digit) => total + digit, 0);
    const remainder = (sum * 10) % 11;
    return remainder === 10 ? 0 : remainder;
  };
  return calculateDigit(9) === Number(cpf[9]) && calculateDigit(10) === Number(cpf[10]);
}

function isValidBrazilianPhone(value) {
  const phone = digitsOnly(value);
  const areaCode = phone.slice(0, 2);
  const validAreaCodes = new Set([
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "21", "22", "24", "27", "28",
    "31", "32", "33", "34", "35", "37", "38", "41", "42", "43", "44", "45", "46", "47",
    "48", "49", "51", "53", "54", "55", "61", "62", "63", "64", "65", "66", "67", "68",
    "69", "71", "73", "74", "75", "77", "79", "81", "82", "83", "84", "85", "86", "87",
    "88", "89", "91", "92", "93", "94", "95", "96", "97", "98", "99",
  ]);
  if (!validAreaCodes.has(areaCode)) return false;
  const subscriberNumber = phone.slice(2);
  return phone.length === 11 && subscriberNumber.length === 9 && subscriberNumber.startsWith("9");
}

function maskRegistrationInput(input, formatter) {
  const cursor = input.selectionStart ?? input.value.length;
  const digitsBeforeCursor = digitsOnly(input.value.slice(0, cursor)).length;
  input.value = formatter(input.value);
  let newCursor = 0;
  let countedDigits = 0;
  while (newCursor < input.value.length && countedDigits < digitsBeforeCursor) {
    if (/\d/.test(input.value[newCursor])) countedDigits += 1;
    newCursor += 1;
  }
  input.setSelectionRange(newCursor, newCursor);
}

function updateRegistrationFieldValidity(input, isValid, message, hintId) {
  const hint = document.getElementById(hintId);
  const complete = digitsOnly(input.value).length === Number(input.dataset.digits);
  const invalid = complete && !isValid(input.value);
  input.setCustomValidity(invalid ? message : "");
  if (hint) {
    hint.textContent = invalid ? message : "";
    hint.dataset.state = invalid ? "invalid" : "";
  }
}

function roleOptions(selectedRole) {
  const options = [
    ["client", "Quero ser contratante", "Encontrar e contratar profissionais."],
    ["provider", "Quero ser contratado", "Oferecer meus serviços para clientes."],
    ["both", "Quero ser contratante e contratado", "Contratar profissionais e também oferecer meus serviços."],
  ];
  return `<div class="role-options">${options.map(([role, title, description]) => `<label class="role-option ${selectedRole === role ? "selected" : ""}"><input type="radio" name="account-role" value="${role}" ${selectedRole === role ? "checked" : ""}><span class="role-option-copy"><strong>${title}</strong><span>${description}</span></span><span class="role-radio" aria-hidden="true"></span></label>`).join("")}</div>`;
}

function categoryCards() {
  return `<div class="category-grid">${categories.map((category) => `
    <button class="category-card" type="button" data-action="open-category" data-category="${esc(category.name)}">
      <span class="category-icon">${category.icon}</span>
      <span><h3>${esc(category.name)}</h3><p>${[...new Set([...category.services, ...allListings().filter((item) => item.category === category.name).map((item) => item.service)])].length} tipos de serviço</p></span>
      <span class="category-arrow" aria-hidden="true">↗</span>
    </button>`).join("")}</div>`;
}

function sectionHeading(title, subtitle = "", action = "") {
  return `<div class="section-heading"><div><h2>${title}</h2>${subtitle ? `<p>${subtitle}</p>` : ""}</div>${action}</div>`;
}

function providerCard(provider, withFavorite = false) {
  const favorite = state.favorites.some((item) => item.id === provider.id);
  return `<article class="listing-card">
    ${avatar(provider.initials, false, provider.profilePhoto)}
    <div>
      <h3>${esc(provider.name)}</h3><p>${esc(provider.service)} · ${esc(provider.location)}</p>
      <div class="inline-meta"><span class="status done">Novo</span><span>${esc(provider.price)}</span></div>
    </div>
    ${withFavorite
      ? `<span class="listing-actions"><button class="icon-button" type="button" data-action="toggle-favorite" data-provider="${esc(provider.id)}" aria-label="${favorite ? "Remover dos favoritos" : "Adicionar aos favoritos"}">${favorite ? "♥" : "♡"}</button><button class="button secondary small" type="button" data-action="open-provider" data-provider="${esc(provider.id)}">Ver perfil</button></span>`
      : `<button class="button secondary small" type="button" data-action="open-provider" data-provider="${esc(provider.id)}">Ver perfil</button>`}
  </article>`;
}

function contactDetails() {
  return `<aside class="card contact-card">
    <h3>Fale com a equipe</h3>
    <p>Estamos aqui para ajudar com suas dúvidas e sugestões.</p>
    <p><strong>Telefone</strong><br><a href="tel:+5511999999999">+55 11 99999-9999</a></p>
    <p><strong>E-mail</strong><br><a href="mailto:empresateste@gmail.com">empresateste@gmail.com</a></p>
  </aside>`;
}

async function apiRequest(path, options = {}) {
  if (location.protocol === "file:") {
    throw new Error("Este APK ainda não está conectado ao servidor do AutonoMe. O app precisa ser configurado com o endereço HTTPS da versão hospedada antes do login e do cadastro funcionarem.");
  }
  let response;
  try {
    response = await fetch(path, {
      credentials: "same-origin",
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
  } catch (error) {
    throw new Error("Não foi possível conectar ao servidor do AutonoMe. Inicie o backend e tente novamente.");
  }
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || "Não foi possível concluir a solicitação.");
  return result;
}

function setAuthenticatedUser(user) {
  if (state.userId !== user.id) {
    state.ownListings = [];
    state.favorites = [];
    state.contracts = [];
    state.messages = [];
    state.conversations = [];
    state.activeChat = null;
    state.activeConversationId = "";
    state.chatMessages = [];
    state.notifications = [];
    state.providerAvailability = [];
    state.availableTimes = [];
    state.contractNotes = [];
    state.settings = { "Notificações": true, "Modo Escuro": false, "Permitir localização": false, "Permitir microfone": false, "Permitir câmera": false };
    state.userId = user.id;
    restoreAppState();
  }
  state.user = user.name;
  state.userId = user.id;
  state.userEmail = user.email;
  state.userRole = user.role;
  state.profileBio = user.profileBio || "";
  state.profileLocation = user.profileLocation || "";
  state.profilePhoto = user.profilePhoto || "";
  state.authInitialized = true;
  state.view = "home";
  state.pendingEmail = "";
  state.drawerOpen = false;
}

async function refreshRemoteData(migrateLocalListings = false) {
  const legacyListings = migrateLocalListings ? [...state.ownListings] : [];
  const legacyFavorites = [...state.favorites];
  let result = await apiRequest("/api/listings", { method: "GET", headers: {} });
  let ownListings = result.listings.filter((listing) => listing.ownerId === state.userId);
  if (legacyListings.length && !ownListings.length) {
    for (const listing of legacyListings) {
      if (!listing.category || !listing.service || !listing.location || !listing.price || !listing.about) continue;
      const saved = await apiRequest("/api/listings", {
        method: "POST",
        body: JSON.stringify({
          category: listing.category,
          service: listing.service,
          location: listing.location,
          price: listing.price,
          about: listing.about,
        }),
      });
      state.userRole = saved.user.role;
    }
    result = await apiRequest("/api/listings", { method: "GET", headers: {} });
    ownListings = result.listings.filter((listing) => listing.ownerId === state.userId);
  }
  const [contractsResult, initialFavoritesResult, availabilityResult] = await Promise.all([
    apiRequest("/api/contracts", { method: "GET", headers: {} }),
    apiRequest("/api/favorites", { method: "GET", headers: {} }),
    apiRequest("/api/availability", { method: "GET", headers: {} }),
  ]);
  let favoritesResult = initialFavoritesResult;
  const remoteFavoriteIds = new Set(favoritesResult.favorites.map((favorite) => favorite.id));
  const favoritesToMigrate = legacyFavorites.filter((favorite) => (
    favorite.id
    && favorite.ownerId !== state.userId
    && !remoteFavoriteIds.has(favorite.id)
    && result.listings.some((listing) => listing.id === favorite.id)
  ));
  for (const favorite of favoritesToMigrate) {
    await apiRequest("/api/favorites", {
      method: "POST",
      body: JSON.stringify({ listingId: favorite.id }),
    });
  }
  if (favoritesToMigrate.length) favoritesResult = await apiRequest("/api/favorites", { method: "GET", headers: {} });
  state.publicListings = result.listings;
  state.ownListings = ownListings;
  state.contracts = contractsResult.contracts;
  state.favorites = favoritesResult.favorites;
  state.providerAvailability = availabilityResult.availability;
}

async function refreshConversations() {
  const result = await apiRequest("/api/messages", { method: "GET", headers: {} });
  state.conversations = result.conversations;
}

async function refreshNotifications() {
  const result = await apiRequest("/api/notifications", { method: "GET", headers: {} });
  state.notifications = result.notifications;
}

async function openConversation(contractId) {
  const result = await apiRequest(`/api/messages?contractId=${encodeURIComponent(contractId)}`, { method: "GET", headers: {} });
  state.activeConversationId = contractId;
  state.activeChat = result.conversation;
  state.chatMessages = result.messages;
  state.view = "chat";
}

async function loadContractNotes(contractId) {
  const result = await apiRequest(`/api/contracts/${encodeURIComponent(contractId)}/notes`, { method: "GET", headers: {} });
  state.contractNotes = result.notes;
}

async function initializeAuth() {
  if (state.authInitialized) return;
  state.authInitialized = true;
  try {
    const result = await apiRequest("/api/auth/me", { method: "GET", headers: {} });
    if (result.user) {
      setAuthenticatedUser(result.user);
      render();
      try {
        await refreshRemoteData(true);
        render();
      } catch (error) {
        showToast(error.message);
      }
    }
  } catch {
    state.authInitialized = false;
  }
}

function authScreen() {
  const registering = state.authMode === "register";
  return `<main class="auth-wrap">
    <section class="auth-aside">
      <div class="auth-brand-row"><div class="brand-lockup" data-action="auth-home"><img class="brand-mark" src="logo_autonome.png" alt=""><span class="brand-name">AutonoMe</span></div></div>
      <div class="auth-message"><h1>Serviços perto.<br>Conexões de verdade.</h1><p>Encontre profissionais autônomos no seu bairro e combine serviços do seu jeito.</p><div class="auth-art" aria-hidden="true">A</div></div>
      <div class="auth-footer">Uma comunidade que valoriza quem faz acontecer.</div>
    </section>
    <section class="auth-panel">
      <p class="eyebrow">Bem-vindo ao AutonoMe</p>
      <h2>${registering ? "Crie sua conta" : "Que bom ter você aqui"}</h2>
      <p>${registering ? "Cadastre-se para encontrar ou oferecer serviços." : "Entre para encontrar profissionais autônomos perto de você."}</p>
      <form class="form-stack" data-form="auth">
        ${registering ? `<div class="field"><label for="auth-name">Nome completo</label><input id="auth-name" name="name" autocomplete="name" placeholder="Como podemos chamar você?" required></div>` : `<div class="field"><label for="auth-email">E-mail</label><input id="auth-email" name="email" type="email" autocomplete="username" placeholder="voce@email.com" required></div>`}
        ${registering ? `<div class="field"><label for="auth-email">E-mail</label><input id="auth-email" name="email" type="email" autocomplete="email" placeholder="voce@email.com" required></div>
        <div class="field"><label for="auth-cpf">CPF</label><input id="auth-cpf" name="cpf" type="text" inputmode="numeric" autocomplete="off" placeholder="000.000.000-00" maxlength="14" data-digits="11" aria-describedby="auth-cpf-hint" required><small class="field-note">Valida os dígitos do documento. A consulta da situação cadastral oficial ainda requer integração com a Receita Federal.</small><small id="auth-cpf-hint" class="field-hint" aria-live="polite"></small></div>
        <div class="field"><label for="auth-phone">Número de celular</label><input id="auth-phone" name="phone" type="tel" inputmode="numeric" autocomplete="tel-national" placeholder="(11) 99999-9999" maxlength="15" data-digits="11" aria-describedby="auth-phone-hint" required><small id="auth-phone-hint" class="field-hint" aria-live="polite"></small></div>
        <div class="field"><label for="auth-role">Como você quer usar o app?</label><select id="auth-role" name="role"><option value="client">Quero ser contratante</option><option value="provider">Quero ser contratado e oferecer serviços</option><option value="both">Quero contratar e oferecer serviços</option></select></div>` : ""}
        <div class="field"><label for="auth-password">Senha</label><input id="auth-password" name="password" type="password" autocomplete="${registering ? "new-password" : "current-password"}" placeholder="Sua senha" required minlength="${registering ? "8" : "1"}" maxlength="128"></div>
        ${registering ? `<div class="field"><label for="auth-confirm">Confirme a senha</label><input id="auth-confirm" name="confirm" type="password" autocomplete="new-password" placeholder="Digite a senha novamente" required minlength="8"></div>` : ""}
        <button class="button" type="submit">${registering ? "Cadastrar-se" : "Entrar"}</button>
      </form>
      <p class="form-bottom">${registering ? "Já tem uma conta?" : "Ainda não tem uma conta?"} <button class="text-button" type="button" data-action="toggle-auth">${registering ? "Entrar" : "Cadastrar-se"}</button></p>
    </section>
  </main>`;
}

function emailVerificationScreen() {
  const deactivation = state.verificationPurpose === "deactivate";
  const message = deactivation
    ? `Enviamos um código para ${esc(state.userEmail)}. Digite-o para mover sua conta para a lista de usuários desativados.`
    : `Enviamos um código para ${esc(state.pendingEmail)}. Confirme seu e-mail para ativar a conta.`;
  return `<main class="auth-wrap"><section class="auth-aside"><div class="auth-brand-row"><div class="brand-lockup" data-action="auth-home"><img class="brand-mark" src="logo_autonome.png" alt=""><span class="brand-name">AutonoMe</span></div></div><div class="auth-message"><h1>Segurança em primeiro lugar.</h1><p>Confirme que você tem acesso ao e-mail antes de continuar.</p><div class="auth-art" aria-hidden="true">A</div></div><div class="auth-footer">AutonoMe · verificação de conta</div></section>
    <section class="auth-panel"><p class="eyebrow">${deactivation ? "Desativação segura" : "Confirme seu e-mail"}</p><h2>${deactivation ? "Confirme para desativar" : "Digite o código"}</h2><p>${message}</p>
      <form class="form-stack" data-form="auth-verify"><div class="field"><label for="auth-code">Código de 6 caracteres</label><input id="auth-code" name="code" type="text" inputmode="text" autocomplete="one-time-code" autocapitalize="characters" maxlength="6" minlength="6" pattern="[A-Za-z0-9]{6}" placeholder="A1B2C3" required></div>
      <button class="button" type="submit">${deactivation ? "Desativar conta" : "Confirmar e criar conta"}</button></form>
      <p class="field-note">O código expira em 10 minutos e pode ser tentado até 5 vezes. Você pode solicitar outro código após 1 minuto.</p>
      <p class="form-bottom">Não recebeu? <button class="text-button" type="button" data-action="resend-code">Reenviar código</button></p>
      <p class="form-bottom"><button class="text-button" type="button" data-action="cancel-verification">Cancelar e voltar</button></p></section></main>`;
}

function shell(content) {
  const active = ["home", "categories", "listings", "professionals"].includes(state.view) ? "home"
    : ["contracts", "contract-detail"].includes(state.view) ? "contracts"
      : ["messages", "chat"].includes(state.view) ? "messages"
        : state.view === "profile" ? "profile" : "";
  return `<div class="app-frame">
    <header class="topbar">
      <div class="brand-lockup" data-action="go-home" role="button" tabindex="0"><img class="brand-mark" src="logo_autonome.png" alt=""><span class="brand-name">AutonoMe</span></div>
      <div class="top-actions"><div class="user-chip">${avatar(initials(state.user) || "V", false, state.profilePhoto)}<span>${esc(state.user)}</span></div><button class="icon-button" type="button" data-action="open-drawer" aria-label="Abrir menu">☰</button></div>
    </header>
    <main class="page-shell"><div class="content">${content}</div></main>
    <nav class="bottom-nav" aria-label="Navegação principal">
      <button class="nav-item ${active === "home" ? "active" : ""}" data-action="go-home"><span class="nav-icon">⌂</span><span>Início</span></button>
      <button class="nav-item ${active === "contracts" ? "active" : ""}" data-action="contracts"><span class="nav-icon">▤</span><span>Contratos</span></button>
      <button class="nav-item ${active === "messages" ? "active" : ""}" data-action="messages"><span class="nav-icon">☷</span><span>Mensagens</span></button>
      <button class="nav-item ${active === "profile" ? "active" : ""}" data-action="profile"><span class="nav-icon">◉</span><span>Perfil</span></button>
    </nav>
    ${state.drawerOpen ? drawer() : ""}
  </div>`;
}

function drawer() {
  const links = [
    ["⚙", "Configurações", "settings"],
    ["♧", "Notificações", "notifications"],
    ["♡", "Favoritos", "favorites"],
    ["✉", "Fale Conosco", "contact"],
  ];
  return `<div class="drawer-backdrop" data-action="close-drawer"></div><aside class="drawer" aria-label="Menu">
    <div class="drawer-head"><div class="brand-lockup"><img class="brand-mark" src="logo_autonome.png" alt=""><span class="brand-name">AutonoMe</span></div><button class="icon-button" data-action="close-drawer" aria-label="Fechar menu">×</button></div>
    <div class="drawer-user">${avatar(initials(state.user), true, state.profilePhoto)}<div><strong>${esc(state.user)}</strong><span>Minha conta</span></div></div>
    <nav class="drawer-nav">${links.map(([icon, text, target]) => `<button class="drawer-link" data-action="${target}"><span>${icon}</span>${text}</button>`).join("")}
      <button class="drawer-link" data-action="${state.userRole === "provider" || state.userRole === "both" ? "my-services" : "offer-service"}"><span>✦</span>${state.userRole === "provider" || state.userRole === "both" ? "Meus serviços" : "Oferecer meus serviços"}</button>
      <button class="drawer-link logout-link" data-action="logout"><span>↪</span>Sair da conta</button>
    </nav>
    <div class="drawer-footer">AutonoMe · versão 1.5.0</div>
  </aside>`;
}

function homeScreen() {
  return `<section class="hero-card card">
    <div class="hero-copy"><p class="eyebrow">Sua comunidade, suas conexões</p><h1>O talento do seu bairro está aqui.</h1><p>Encontre profissionais autônomos e combine o serviço ideal para você.</p>${button("Explorar serviços", "categories")}</div>
    <div class="hero-art" aria-hidden="true">✦</div>
  </section>
  <div class="quick-grid">
    <button class="quick-card" data-action="contracts"><span class="quick-icon">▤</span><span><strong>Meus contratos</strong><span>Acompanhe seus serviços</span></span></button>
    <button class="quick-card" data-action="messages"><span class="quick-icon">☷</span><span><strong>Mensagens</strong><span>Converse com profissionais</span></span></button>
    <button class="quick-card" data-action="favorites"><span class="quick-icon">♡</span><span><strong>Favoritos</strong><span>Seus profissionais preferidos</span></span></button>
  </div>
  <button class="provider-cta card" data-action="offer-service"><span class="provider-cta-icon">✦</span><span class="provider-cta-copy"><strong>${state.userRole === "provider" || state.userRole === "both" ? "Divulgue mais um serviço" : "Trabalhe por conta própria"}</strong><span>Cadastre seus serviços e seja encontrado por clientes do seu bairro.</span></span><span class="category-arrow" aria-hidden="true">↗</span></button>
  ${sectionHeading("Áreas disponíveis", "Escolha a categoria para começar.", `<button class="text-button" data-action="categories">Ver todas ↗</button>`)}
  ${categoryCards()}`;
}

function categoriesScreen() {
  return `<p class="eyebrow">Encontre o que você precisa</p><h1>Áreas disponíveis</h1><p class="lead">Explore os serviços e encontre o profissional ideal para o seu próximo projeto.</p>${categoryCards()}`;
}

function listingsScreen() {
  const category = categories.find((item) => item.name === state.category);
  const services = [...new Set([...(category?.services || []), ...allListings().filter((item) => item.category === state.category).map((item) => item.service)])];
  const search = normalizedSearch(state.query);
  const categoryListings = allListings().filter((provider) => provider.category === state.category);
  const searchMatches = (provider) => !search || normalizedSearch(`${provider.name} ${provider.service} ${provider.about}`).includes(search);
  const previouslyBooked = categoryListings.some((provider) => provider.ownerId !== state.userId && isProviderBooked(provider) && searchMatches(provider));
  const providers = categoryListings.filter((provider) => provider.ownerId !== state.userId
    && !isProviderBooked(provider)
    && searchMatches(provider));
  return `<p class="eyebrow">${esc(state.category)}</p><h1>Encontre um profissional</h1><p class="lead">Escolha um serviço ou explore os profissionais disponíveis na sua região.</p>
    <div class="search-box"><span aria-hidden="true">⌕</span><input id="provider-search" data-action="search" type="search" placeholder="Buscar serviço ou profissional" value="${esc(state.query)}" aria-label="Buscar serviço ou profissional"></div>
    <div class="section-heading"><div><h2>Serviços</h2><p>O que você está procurando?</p></div></div>
    <div class="category-grid">${services.map((service) => `<button class="category-card" type="button" data-action="select-service" data-service="${esc(service)}"><span class="category-icon">${category?.icon || "✦"}</span><span><h3>${esc(service)}</h3><p>Ver profissionais</p></span><span class="category-arrow">↗</span></button>`).join("")}</div>
    ${providers.length ? sectionHeading("Profissionais da região", `${providers.length} ${providers.length === 1 ? "profissional disponível" : "profissionais disponíveis"} para você conhecer.`) : ""}
    ${providers.length ? `<div class="listing-list">${providers.map((provider) => providerCard(provider)).join("")}</div>` : `<div class="card empty-state"><div class="empty-icon">⌕</div><h3>${previouslyBooked ? "Este profissional já foi contratado" : "Nenhum profissional encontrado"}</h3><p>${previouslyBooked ? "O perfil volta a aparecer quando a contratação for cancelada. Consulte seu pedido em Contratações." : "Experimente buscar por outro termo ou escolha outro serviço."}</p>${previouslyBooked ? `<button class="button secondary" data-action="contracts">Ver minhas contratações</button>` : ""}</div>`}`;
}

function professionalsScreen() {
  const category = categories.find((item) => item.name === state.category);
  const search = normalizedSearch(state.query);
  const matchingService = (provider) => normalizedSearch(provider.service) === normalizedSearch(state.service);
  const matchingSearch = (provider) => !search || normalizedSearch(`${provider.name} ${provider.service} ${provider.about} ${provider.location}`).includes(search);
  const categoryListings = allListings().filter((provider) => provider.category === state.category && matchingService(provider));
  const previouslyBooked = categoryListings.some((provider) => provider.ownerId !== state.userId && isProviderBooked(provider) && matchingSearch(provider));
  const providers = categoryListings.filter((provider) => provider.ownerId !== state.userId
    && !isProviderBooked(provider)
    && matchingSearch(provider));
  return `<button class="text-button back-link" type="button" data-action="back-to-services">← Voltar aos serviços</button>
    <p class="eyebrow">${esc(state.category)}</p><h1>${esc(state.service)}</h1><p class="lead">Profissionais disponíveis para este serviço na sua região.</p>
    <div class="search-box"><span aria-hidden="true">⌕</span><input id="provider-search" data-action="search" type="search" placeholder="Buscar profissional" value="${esc(state.query)}" aria-label="Buscar profissional"></div>
    ${providers.length ? `${sectionHeading("Profissionais disponíveis", `${providers.length} ${providers.length === 1 ? "profissional" : "profissionais"} para você conhecer.`)}<div class="listing-list">${providers.map((provider) => providerCard(provider)).join("")}</div>` : `<div class="card empty-state"><div class="empty-icon">⌕</div><h2>${previouslyBooked ? "Profissional temporariamente indisponível" : "Nenhum profissional encontrado"}</h2><p>${previouslyBooked ? "O profissional tem uma contratação ativa e volta a aparecer quando o pedido for cancelado." : "Tente outra busca ou volte aos serviços para escolher uma opção diferente."}</p>${previouslyBooked ? `<button class="button secondary" data-action="contracts">Ver minhas contratações</button>` : ""}</div>`}`;
}

function profileScreen() {
  const provider = state.provider;
  const ownProfile = state.user !== "Visitante" && state.view === "profile";
  const myListing = !ownProfile && state.user !== "Visitante" && provider.ownerId === state.userId;
  const person = ownProfile ? { name: state.user, initials: initials(state.user), service: state.userRole === "provider" ? "Profissional autônomo" : state.userRole === "both" ? "Contratante e profissional autônomo" : "Contratante", location: state.profileLocation || state.ownListings[0]?.location || "Adicione sua cidade", about: state.profileBio || "Conte um pouco sobre você e os serviços que oferece.", profilePhoto: state.profilePhoto } : provider;
  return `<section class="card profile-hero ${ownProfile ? "my-profile-hero" : ""}">${avatar(person.initials, true, person.profilePhoto)}<div class="profile-hero-copy"><p class="eyebrow">${ownProfile ? "Meu perfil" : "Profissional"}</p><h1>${esc(person.name)}</h1><p>${esc(person.location)}</p>${ownProfile ? `<span class="profile-role-pill">${esc(person.service)}</span>` : ""}</div>${ownProfile ? `<button class="button secondary small profile-edit-button" type="button" data-action="edit-profile">Editar perfil</button>` : ""}</section>
    ${ownProfile ? `<section class="card profile-block"><div class="card-top"><div><p class="eyebrow">Sobre mim</p><h3>Meu perfil</h3></div><button class="text-button" type="button" data-action="edit-profile">Editar</button></div><p>${esc(person.about)}</p></section><section class="card profile-block"><div class="card-top"><div><p class="eyebrow">Minha conta</p><h3>Como você quer usar o AutonoMe?</h3></div></div>${roleOptions(state.userRole)}<button class="text-button" data-action="offer-service">Cadastrar um serviço →</button></section>${state.ownListings.length ? sectionHeading("Meus serviços publicados", `${state.ownListings.length} anúncios`, `<button class="text-button" data-action="my-services">Gerenciar ↗</button>` ) + `<div class="listing-list">${state.ownListings.slice(0, 3).map((listing) => providerCard(listing)).join("")}</div>` : ""}<section class="card profile-block"><h3>Preferências</h3><button class="text-button" data-action="settings">Configurações →</button></section>` : `<section class="card profile-block"><div class="card-top"><h3>Sobre o perfil</h3><span class="status done">Novo</span></div>${person.profileBio ? `<p>${esc(person.profileBio)}</p>` : ""}<p>${esc(person.about)}</p></section><section class="card profile-block"><h3>Serviço</h3><p>${esc(person.service)}<br>${esc(person.price)}</p></section>
    <section class="card profile-block"><h3>Contato e contratação</h3><p>Envie um pedido pelo AutonoMe. O profissional poderá confirmar ou recusar; seus dados pessoais não são exibidos publicamente.</p></section>
    <div style="margin-top:16px;display:flex;flex-wrap:wrap;gap:10px">${myListing ? button("Gerenciar meus serviços", "my-services") : isProviderBooked(provider) ? button("Ver contratação ativa", "contracts", { variant: "secondary" }) : button(state.userRole === "provider" ? "Ative também o perfil contratante" : "Solicitar contratação", "calendar", { disabled: state.userRole === "provider" })}${myListing || isProviderBooked(provider) ? "" : button(state.favorites.some((item) => item.id === provider.id) ? "♥ Salvo nos favoritos" : "♡ Salvar nos favoritos", "favorite-current", { variant: "secondary" })}</div>`}`;
}

function editProfileScreen() {
  return `<button class="text-button back-link" type="button" data-action="profile">← Voltar ao perfil</button><p class="eyebrow">Sua identidade no AutonoMe</p><h1>Editar perfil</h1><p class="lead">Atualize as informações que outros usuários veem sobre você.</p>
    <section class="card profile-editor-card"><div class="profile-photo-editor"><span class="profile-photo-preview">${avatar(initials(state.user), true, state.profilePhoto)}</span><div><strong>Sua foto</strong><p>Uma foto ajuda as pessoas a reconhecerem você.</p><label class="button secondary small profile-photo-label" for="profile-photo">Escolher foto<input id="profile-photo" name="photo" type="file" accept="image/jpeg,image/png,image/webp" hidden></label><button class="text-button" type="button" data-action="remove-profile-photo">Remover foto</button></div></div>
    <form class="form-stack" data-form="profile"><input type="hidden" name="profilePhoto" value="${esc(state.profilePhoto)}">
      <div class="field"><label for="profile-name">Nome de exibição</label><input id="profile-name" name="name" maxlength="120" autocomplete="name" value="${esc(state.user)}" required></div>
      <div class="field"><label for="profile-location">Cidade e estado</label><input id="profile-location" name="profileLocation" maxlength="120" value="${esc(state.profileLocation)}" placeholder="Ex.: São Paulo, SP"></div>
      <div class="field"><label for="profile-bio">Sobre você</label><textarea id="profile-bio" name="profileBio" maxlength="500" rows="5" placeholder="Conte um pouco sobre você e seu trabalho.">${esc(state.profileBio)}</textarea></div>
      <button class="button" type="submit">Salvar alterações</button>
    </form></section>`;
}

function providerSetupScreen() {
  const selectedCategory = categories.find((item) => item.name === state.offerCategory) || categories[0];
  const existing = state.ownListings.find((item) => item.id === state.editingListingId);
  const serviceInCategory = existing && selectedCategory.services.includes(existing.service);
  return `<button class="text-button back-link" type="button" data-action="cancel-listing-edit">← Voltar aos meus serviços</button><p class="eyebrow">Trabalhe por conta própria</p><h1>${existing ? "Editar serviço" : "Ofereça seus serviços"}</h1><p class="lead">${existing ? "Atualize os detalhes do anúncio que os clientes encontram." : "Crie seu anúncio para que clientes da sua região possam encontrar você."}</p>
    <section class="card profile-block"><form class="form-stack" data-form="offer">
      <div class="field"><label for="offer-category">Área de atuação</label><select id="offer-category" name="category" required>${categories.map((category) => `<option value="${esc(category.name)}" ${selectedCategory.name === category.name ? "selected" : ""}>${esc(category.name)}</option>`).join("")}</select></div>
      <div class="field"><label for="offer-service">Serviço oferecido</label><select id="offer-service" name="service" required>${selectedCategory.services.map((service) => `<option value="${esc(service)}" ${existing?.service === service ? "selected" : ""}>${esc(service)}</option>`).join("")}<option value="__custom__" ${existing && !serviceInCategory ? "selected" : ""}>Outro serviço (digitar nome)</option></select></div>
      <div class="field custom-service-field" ${existing && !serviceInCategory ? "" : "hidden"}><label for="offer-custom-service">Nome do serviço</label><input id="offer-custom-service" name="customService" value="${existing && !serviceInCategory ? esc(existing.service) : ""}" placeholder="Ex.: conserto de bicicletas" ${existing && !serviceInCategory ? "required" : ""}></div>
      <div class="field"><label for="offer-location">Cidade e estado</label><input id="offer-location" name="location" autocomplete="address-level2" value="${esc(existing?.location || "")}" placeholder="Ex.: São Paulo, SP" required></div>
      <div class="field"><label for="offer-price">Valor ou forma de cobrança</label><input id="offer-price" name="price" value="${esc(existing?.price || "")}" placeholder="Ex.: a combinar ou valor por hora" required></div>
      <div class="field"><label for="offer-about">Descreva seu serviço</label><textarea id="offer-about" name="about" rows="5" maxlength="500" placeholder="Conte sua experiência e o que você oferece aos clientes." required>${esc(existing?.about || "")}</textarea></div>
      <button class="button" type="submit">${existing ? "Salvar serviço" : "Publicar meu serviço"}</button>
    </form></section>`;
}

function myServicesScreen() {
  return `<p class="eyebrow">Seu trabalho, sua vitrine</p><h1>Meus serviços</h1><p class="lead">Gerencie os anúncios que os clientes podem encontrar.</p>
    <div class="section-heading"><div><h2>Serviços publicados</h2><p>${state.ownListings.length} ${state.ownListings.length === 1 ? "anúncio" : "anúncios"}</p></div>${button("Adicionar serviço", "offer-service", { small: true })}</div>
    <div class="listing-list">${state.ownListings.length ? state.ownListings.map((listing) => `<article class="listing-card">${avatar(listing.initials, false, listing.profilePhoto)}<div><h3>${esc(listing.service)}</h3><p>${esc(listing.category)} · ${esc(listing.location)}</p><div class="inline-meta"><span>${esc(listing.price)}</span></div></div><span class="listing-actions"><button class="button secondary small" data-action="edit-listing" data-listing="${esc(listing.id)}">Editar</button><button class="button danger small" data-action="delete-listing" data-listing="${esc(listing.id)}">Excluir</button></span></article>`).join("") : `<section class="card empty-state"><div class="empty-icon">✦</div><h2>Você ainda não publicou serviços</h2><p>Cadastre seu primeiro serviço para aparecer para clientes da sua região.</p>${button("Cadastrar serviço", "offer-service")}</section>`}</div>
    <section class="card profile-block availability-card"><h2>Horários de atendimento</h2><p>Os clientes só verão os horários que você disponibilizar.</p>
      ${state.providerAvailability.length ? `<div class="availability-list">${state.providerAvailability.map((slot, index) => `<div class="availability-row"><span><strong>${weekdays[slot.weekday]}</strong> · ${esc(slot.time)}</span><button class="text-button" type="button" data-action="remove-availability-slot" data-index="${index}" aria-label="Remover ${weekdays[slot.weekday]} às ${esc(slot.time)}">Remover</button></div>`).join("")}</div>` : `<p class="field-note">Nenhum horário cadastrado. Configure sua disponibilidade para receber pedidos de contratação.</p>`}
      <form class="availability-form" data-form="availability"><div class="two-col"><div class="field"><label for="availability-day">Dia da semana</label><select id="availability-day" name="weekday">${weekdays.map((day, index) => `<option value="${index}">${["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"][index]}</option>`).join("")}</select></div><div class="field"><label for="availability-time">Horário</label><input id="availability-time" name="time" type="time" step="900" required></div></div><button class="button secondary" type="button" data-action="add-availability-slot">Adicionar horário</button><button class="button" type="submit">Salvar disponibilidade</button></form>
    </section>`;
}

function bookingDays() {
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date();
    date.setHours(12, 0, 0, 0);
    date.setDate(date.getDate() + index);
    const value = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    return { day: weekdays[date.getDay()], date: `${String(date.getDate()).padStart(2, "0")}/${String(date.getMonth() + 1).padStart(2, "0")}`, value };
  });
}

async function loadSelectedAvailability() {
  const day = bookingDays()[state.selectedDay];
  if (!day || !state.provider) return;
  state.availabilityLoading = true;
  state.availableTimes = [];
  state.availabilityConfigured = false;
  state.selectedTime = "";
  try {
    const params = new URLSearchParams({
      listingId: state.provider.id,
      date: day.value,
      timezoneOffsetMinutes: String(new Date().getTimezoneOffset()),
    });
    const result = await apiRequest(`/api/availability?${params}`, { method: "GET", headers: {} });
    state.availabilityConfigured = result.configured;
    state.availableTimes = result.times;
  } finally {
    state.availabilityLoading = false;
  }
}

function calendarScreen() {
  const days = bookingDays();
  return `<p class="eyebrow">Agendar serviço</p><h1>Escolha um horário</h1><p class="lead">Veja a disponibilidade de ${esc(state.provider.name)} e envie seu pedido de contratação.</p>
    <section class="card profile-hero">${avatar(state.provider.initials)}<div><h3>${esc(state.provider.name)}</h3><p>${esc(state.provider.service)} · <span class="status done">Novo</span></p></div></section>
    ${sectionHeading("Escolha o dia", "Selecione uma data para consultar a disponibilidade.")}
    <div class="day-picker">${days.map((day, index) => `<button class="day-option ${state.selectedDay === index ? "selected" : ""}" data-action="select-day" data-day="${index}"><span>${day.day}</span><strong>${day.date}</strong></button>`).join("")}</div>
    ${sectionHeading("Horários disponíveis", "Selecione um horário para enviar o pedido.")}
    ${state.availabilityLoading ? `<p class="field-note">Consultando horários...</p>` : !state.availabilityConfigured ? `<div class="booking-summary">Este profissional ainda não configurou os horários de atendimento.</div>` : state.availableTimes.length ? `<div class="time-grid">${state.availableTimes.map((time) => `<button class="time-option ${state.selectedTime === time ? "selected" : ""}" data-action="select-time" data-time="${esc(time)}" aria-pressed="${state.selectedTime === time}">${esc(time)}</button>`).join("")}</div>` : `<div class="booking-summary">Não há horários disponíveis nesta data. Escolha outro dia.</div>`}
    <div class="field"><label for="booking-address">Endereço ou região do atendimento (opcional)</label><input id="booking-address" name="address" maxlength="250" autocomplete="street-address" value="${esc(state.bookingAddress)}" placeholder="Ex.: Rua, número e bairro"></div>
    <div class="field"><label for="booking-details">Conte ao profissional o que você precisa (opcional)</label><textarea id="booking-details" rows="3" maxlength="500" placeholder="Descreva brevemente o serviço ou tire uma dúvida.">${esc(state.bookingDetails)}</textarea></div>
    ${state.selectedTime ? `<div class="booking-summary">Horário selecionado: <strong>${days[state.selectedDay].day}, ${days[state.selectedDay].date} às ${state.selectedTime}</strong></div>` : ""}
    ${state.userRole === "provider" ? `<div class="booking-summary">Seu perfil está configurado apenas para oferecer serviços. Ative também o modo contratante nas configurações para contratar profissionais.</div>` : ""}
    ${isProviderBooked(state.provider) ? `<div class="booking-summary">Este profissional tem uma contratação ativa. Cancele o pedido atual para liberar novos horários.</div>` : ""}
    ${button("Solicitar contratação", "submit-booking", { disabled: !state.selectedTime || state.userRole === "provider" || isProviderBooked(state.provider) })}`;
}

function contractsScreen() {
  const entries = state.contracts.filter((item) => item.tab === state.contractTab);
  return `<p class="eyebrow">Acompanhe seus serviços</p><h1>Contratos</h1><p class="lead">Consulte seus pedidos, confirmações e serviços anteriores.</p>
    <div class="tabs" role="tablist"><button class="tab ${state.contractTab === "requested" ? "active" : ""}" role="tab" data-action="contract-tab" data-tab="requested">Solicitados</button><button class="tab ${state.contractTab === "hired" ? "active" : ""}" role="tab" data-action="contract-tab" data-tab="hired">Recebidos</button></div>
    <div class="section-heading"><div><h2>${state.contractTab === "hired" ? "Pedidos para seus serviços" : "Pedidos que você enviou"}</h2><p>${entries.length} ${entries.length === 1 ? "pedido" : "pedidos"}</p></div></div>
    <div class="stack">${entries.length ? entries.map((item) => {
      const contractState = item.state.toLowerCase();
      const badge = contractState.includes("confirmado") ? "ok" : contractState.includes("cancel") || contractState.includes("terminado") || contractState.includes("entregue") || contractState.includes("concluído") || contractState.includes("negado") ? "done" : "";
        const canCancel = item.tab === "requested" && ["aguardando confirmação", "esperando confirmação", "confirmado"].includes(contractState);
      return `<article class="card contract-card">${avatar(initials(item.name), false, item.profilePhoto)}<div><h3>${esc(item.name)}</h3><p style="margin:0 0 7px;color:var(--muted);font-size:12px">${esc(item.service)} · ${esc(item.date)}</p><span class="status ${badge}">${esc(item.state)}</span></div><span class="contract-actions"><button class="button secondary small" data-action="contract-detail" data-contract="${esc(item.id)}">Detalhes</button>${canCancel ? `<button class="button danger small" data-action="cancel-contract" data-contract="${esc(item.id)}">Cancelar</button>` : ""}${item.tab === "hired" && item.state === "Aguardando confirmação" ? `<button class="button small" data-action="respond-contract" data-status="confirm" data-contract="${esc(item.id)}">Aceitar</button><button class="button danger small" data-action="respond-contract" data-status="decline" data-contract="${esc(item.id)}">Recusar</button>` : ""}</span></article>`;
    }).join("") : `<div class="card empty-state"><div class="empty-icon">${state.contractTab === "hired" ? "✦" : "▤"}</div><h3>${state.contractTab === "hired" ? "Nenhum pedido para prestar serviço" : "Nenhuma contratação por enquanto"}</h3><p>${state.contractTab === "hired" ? "Quando um cliente solicitar um serviço seu, o pedido aparecerá aqui." : "Encontre um profissional, escolha um horário e acompanhe seu pedido nesta tela."}</p>${state.contractTab === "requested" ? `<button class="button" data-action="categories">Explorar serviços</button>` : ""}</div>`}</div>`;
}

function contractDetailScreen() {
  const contract = state.contracts.find((item) => item.id === state.detailId);
  const provider = allListings().find((item) => item.id === contract?.listingId) || state.provider || {};
  if (!contract) return `<div class="card empty-state"><h2>Contrato não encontrado</h2>${button("Voltar aos contratos", "contracts", { variant: "secondary" })}</div>`;
  return `<p class="eyebrow">Detalhes do serviço</p><h1>Especificações</h1>
    <section class="card profile-hero">${avatar(initials(contract.name), true, contract.profilePhoto)}<div><p class="eyebrow">Serviço combinado</p><h1>${esc(contract.name)}</h1><p>${esc(contract.service)} · ${esc(contract.date)}</p></div></section>
    <section class="card profile-block"><span class="status ${contract.state === "Confirmado" ? "ok" : ["Cancelada", "Pedido negado", "Concluído"].includes(contract.state) ? "done" : ""}">${esc(contract.state)}</span><h3 style="margin-top:18px">Sobre o serviço</h3><p>${esc(provider.about || "Descrição do serviço a ser ou que foi prestado.")}</p>${contract.details ? `<h3 style="margin-top:20px">Mensagem do cliente</h3><p>${esc(contract.details)}</p>` : ""}${contract.serviceAddress ? `<h3 style="margin-top:20px">Endereço do atendimento</h3><p>${esc(contract.serviceAddress)}</p>` : ""}<h3 style="margin-top:20px">Profissional</h3><p>${esc(contract.service)} · ${esc(provider.location || "Cidade - Estado")}</p></section>
    <section class="card profile-block contract-notes"><h2>Anotações privadas</h2><p>Essas anotações ficam visíveis somente para você.</p>${state.contractNotes.length ? `<div class="note-list">${state.contractNotes.map((note) => `<p class="contract-note">${esc(note.body)}</p>`).join("")}</div>` : `<p class="field-note">Você ainda não adicionou anotações.</p>`}<form class="form-stack" data-form="contract-note"><div class="field"><label for="contract-note">Nova anotação</label><textarea id="contract-note" name="body" maxlength="2000" rows="3" required placeholder="Anote detalhes importantes para esta contratação."></textarea></div><button class="button" type="submit">Salvar anotação</button></form></section>
    <div style="margin-top:15px;display:flex;gap:10px;flex-wrap:wrap">${button("Voltar aos contratos", "contracts", { variant: "secondary" })}${!["Cancelada", "Pedido negado"].includes(contract.state) ? `<button class="button" type="button" data-action="open-contract-chat" data-contract="${esc(contract.id)}">Conversar</button>` : ""}${contract.tab === "requested" && ["Aguardando confirmação", "Confirmado"].includes(contract.state) ? `<button class="button danger" type="button" data-action="cancel-contract" data-contract="${esc(contract.id)}">Cancelar contratação</button>` : ""}${contract.tab === "hired" && contract.state === "Aguardando confirmação" ? `<button class="button" type="button" data-action="respond-contract" data-status="confirm" data-contract="${esc(contract.id)}">Aceitar pedido</button><button class="button danger" type="button" data-action="respond-contract" data-status="decline" data-contract="${esc(contract.id)}">Recusar pedido</button>` : ""}</div>`;
}

function messagesScreen() {
  return `<p class="eyebrow">Contato seguro</p><h1>Mensagens</h1><p class="lead">Converse com segurança sobre os serviços contratados pelo AutonoMe.</p>
    ${state.conversations.length ? `<div class="conversation-list">${state.conversations.map((conversation) => `<button class="card conversation-card" type="button" data-action="open-contract-chat" data-contract="${esc(conversation.contractId)}">${avatar(initials(conversation.name), false, conversation.profilePhoto)}<span class="conversation-copy"><strong>${esc(conversation.name)}</strong><span>${esc(conversation.service)} · ${esc(conversation.state)}</span><span class="conversation-preview">${esc(conversation.preview)}</span></span><span class="conversation-meta">${conversation.unreadCount ? `<span class="unread-badge">${conversation.unreadCount}</span>` : ""}<span class="message-time">${formatMessageTime(conversation.time)}</span><span class="conversation-chevron">›</span></span></button>`).join("")}</div>` : `<section class="card empty-state"><div class="empty-icon">☷</div><h2>Nenhuma conversa ainda</h2><p>Depois que você enviar um pedido de contratação, poderá conversar com o profissional por aqui.</p><button class="button" data-action="categories">Encontrar um profissional</button></section>`}`;
}

function chatScreen() {
  if (!state.activeChat) return `<section class="card empty-state"><h2>Conversa não encontrada</h2>${button("Voltar às mensagens", "messages", { variant: "secondary" })}</section>`;
  return `<button class="text-button back-link" type="button" data-action="messages">← Voltar às mensagens</button><p class="eyebrow">Sobre ${esc(state.activeChat.service)}</p><h1>Conversa</h1><section class="card chat-panel">
    <div class="chat-head">${avatar(initials(state.activeChat.name), false, state.activeChat.profilePhoto)}<div><strong>${esc(state.activeChat.name)}</strong><p>${esc(state.activeChat.service)} · ${esc(state.activeChat.state)}</p></div></div>
    <div class="chat-messages" aria-live="polite">${state.chatMessages.length ? state.chatMessages.map((message) => `<div class="chat-message-row ${message.mine ? "mine" : ""}"><div class="chat-bubble">${esc(message.body)}<span class="chat-message-time">${formatMessageTime(message.createdAt)}</span></div></div>`).join("") : `<div class="chat-empty"><span aria-hidden="true">✦</span><strong>Inicie a conversa</strong><p>Combine os detalhes do serviço com ${esc(state.activeChat.name)}.</p></div>`}</div>
    <form class="chat-form" data-form="chat"><input name="message" aria-label="Escreva sua mensagem" maxlength="2000" placeholder="Escreva uma mensagem..." required autocomplete="off"><button class="button small" type="submit" aria-label="Enviar mensagem">Enviar</button></form>
  </section>`;
}

function formatMessageTime(timestamp) {
  if (!timestamp) return "";
  return new Date(Number(timestamp) * 1000).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function formatNotificationTime(timestamp) {
  if (!timestamp) return "";
  return new Date(Number(timestamp) * 1000).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function notificationsScreen() {
  const hasUnread = state.notifications.some((notification) => !notification.read);
  return `<div class="section-heading"><div><p class="eyebrow">Fique por dentro</p><h1>Notificações</h1></div>${state.notifications.length ? `<span class="notification-header-actions">${hasUnread ? `<button class="text-button" data-action="mark-all-notifications-read">Marcar todas como lidas</button>` : ""}<button class="text-button" data-action="clear-notifications">Excluir todas</button></span>` : ""}</div>
    ${state.notifications.length ? `<div class="stack">${state.notifications.map((notification) => `<article class="card notification-card ${notification.read ? "" : "notification-unread"}"><div class="card-top"><h3>${esc(notification.title)}</h3><span class="message-time">${esc(formatNotificationTime(notification.time))}</span></div><p>${esc(notification.text)}</p><div class="notification-actions">${notification.contractId ? `<button class="button secondary small" data-action="open-notification-contract" data-contract="${esc(notification.contractId)}">Ver contratação</button>` : ""}${notification.read ? "" : `<button class="text-button" data-action="mark-notification-read" data-notification="${esc(notification.id)}">Marcar como lida</button>`}</div></article>`).join("")}</div>` : `<section class="card empty-state"><div class="empty-icon">♧</div><h2>Sem notificações</h2><p>Quando tiver novidades sobre seus serviços, elas aparecerão aqui.</p></section>`}`;
}

function settingsScreen() {
  return `<p class="eyebrow">Sua conta, do seu jeito</p><h1>Configurações</h1><p class="lead">Gerencie suas preferências no AutonoMe.</p>
    <section class="card profile-block"><h3>Como você quer usar o app?</h3><p>Você pode alterar esse perfil quando quiser.</p>${roleOptions(state.userRole)}</section>
    <section class="card profile-block"><h3>Preferências</h3>${Object.entries(state.settings).map(([name, enabled]) => `<div class="switch-row"><div class="switch-copy"><strong>${esc(name)}</strong><span>${name === "Modo Escuro" ? "Ajuste a aparência do aplicativo." : name === "Notificações" ? "Receba novidades sobre seus serviços." : `Controle o acesso do app a ${name.replace("Permitir ", "").toLowerCase()}.`}</span></div><button class="switch" type="button" role="switch" aria-checked="${enabled}" aria-label="${esc(name)}" data-action="toggle-setting" data-setting="${esc(name)}"></button></div>`).join("")}</section>
    <section class="card profile-block danger-zone"><h3>Desativar conta</h3><p>Sua conta será movida para a lista segura de usuários desativados. Você precisará confirmar a ação com um código enviado ao e-mail cadastrado.</p>${button("Solicitar desativação", "delete-account", { variant: "danger" })}</section>
    <section class="card profile-block"><h3>Sobre o app</h3><p>AutonoMe · versão 1.5.0</p></section>`;
}

function favoritesScreen() {
  const availableFavorites = state.favorites.filter((provider) => !isProviderBooked(provider));
  return `<p class="eyebrow">Seus profissionais preferidos</p><h1>Favoritos</h1><p class="lead">Guarde aqui quem você quer encontrar de novo.</p>
    <div class="listing-list">${availableFavorites.length ? availableFavorites.map((provider) => providerCard(provider, true)).join("") : `<section class="card empty-state"><div class="empty-icon">♡</div><h2>${state.favorites.length ? "Seus favoritos estão contratados" : "Nenhum favorito por enquanto"}</h2><p>${state.favorites.length ? "Eles voltam a aparecer quando os pedidos ativos forem cancelados." : "Ao encontrar um profissional, toque no coração para adicioná-lo à sua lista."}</p><button class="button" data-action="${state.favorites.length ? "contracts" : "categories"}">${state.favorites.length ? "Ver minhas contratações" : "Encontrar profissionais"}</button></section>`}</div>`;
}

function contactScreen() {
  return `<p class="eyebrow">Estamos aqui para ouvir você</p><h1>Fale com a gente</h1><p class="lead">Deixe sugestões, comentários ou conte com a nossa equipe quando precisar.</p>
    <div class="support-grid">
      <button class="support-option" data-action="contact-form" data-type="Sugestão"><span class="support-icon">✦</span><strong>Dar uma sugestão <span aria-hidden="true">↗</span></strong></button>
      <button class="support-option" data-action="contact-form" data-type="Feedback"><span class="support-icon">☷</span><strong>Enviar feedback <span aria-hidden="true">↗</span></strong></button>
      <button class="support-option" data-action="contact-form" data-type="Reclamação"><span class="support-icon">♡</span><strong>Fazer uma reclamação <span aria-hidden="true">↗</span></strong></button>
    </div>
    <section style="margin-top:15px" class="card profile-block"><h3>Precisa de ajuda?</h3><p>Consulte nossos canais de atendimento.</p><button class="text-button" data-action="help">Ver informações de ajuda →</button></section>
    <div style="margin-top:15px">${contactDetails()}</div>`;
}

function contactFormScreen() {
  return `<p class="eyebrow">Fale com a equipe</p><h1>${esc(state.contactType)}</h1><p class="lead">Sua mensagem ajuda a melhorar o AutonoMe para todo mundo.</p>
    <section class="card profile-block"><form class="form-stack" data-form="contact"><div class="field"><label for="contact-name">Nome completo</label><input id="contact-name" name="name" autocomplete="name" value="${state.user !== "Visitante" ? esc(state.user) : ""}" required placeholder="Seu nome"></div>
    <div class="field"><label for="contact-message">${esc(state.contactType === "Sugestão" ? "Comentário" : state.contactType)}</label><textarea id="contact-message" name="message" rows="6" required placeholder="Escreva sua mensagem..."></textarea></div>
    <button class="button" type="submit">Enviar</button></form></section><div style="margin-top:15px">${contactDetails()}</div>`;
}

function helpScreen() {
  return `<p class="eyebrow">Conte com a gente</p><h1>Ajuda</h1><section class="card profile-block"><h3>Como podemos ajudar?</h3><p>Para solicitar ajuda, entre em contato por um dos nossos canais de atendimento. Nossa equipe está pronta para ouvir você.</p></section><div style="margin-top:15px">${contactDetails()}</div>`;
}

function reviewScreen() {
  return `<p class="eyebrow">Sua experiência importa</p><h1>Avaliação</h1><section class="card rating-prompt"><h2>Como foi o serviço?</h2><p class="lead">Quantas estrelas você dá para este profissional?</p><div class="rating-stars" role="group" aria-label="Selecione uma nota de 1 a 5">${[1, 2, 3, 4, 5].map((star) => `<button class="star-button ${star <= state.selectedStars ? "selected" : ""}" data-action="rate" data-stars="${star}" aria-label="${star} ${star === 1 ? "estrela" : "estrelas"}" aria-pressed="${star === state.selectedStars}">★</button>`).join("")}</div>
    <form class="form-stack" data-form="review"><div class="field"><label for="review-comment">Alguma observação ou comentário?</label><textarea id="review-comment" name="comment" rows="5" placeholder="Conte um pouco sobre sua experiência..."></textarea></div><button class="button" type="submit" ${state.selectedStars ? "" : "disabled"}>Enviar avaliação</button></form></section>`;
}

function successScreen() {
  return `<section class="card success-card"><div class="empty-icon">✓</div><p class="eyebrow">Mensagem recebida</p><h1>Sua mensagem foi enviada!</h1><p>Obrigado por entrar em contato. Nossa equipe vai ler sua mensagem e responder assim que possível.</p>${button("Voltar para o início", "go-home")}</section>`;
}

function pageContent() {
  switch (state.view) {
    case "home": return homeScreen();
    case "categories": return categoriesScreen();
    case "listings": return listingsScreen();
    case "professionals": return professionalsScreen();
    case "profile": return profileScreen();
    case "edit-profile": return editProfileScreen();
    case "provider-profile": return profileScreen();
    case "calendar": return calendarScreen();
    case "contracts": return contractsScreen();
    case "contract-detail": return contractDetailScreen();
    case "messages": return messagesScreen();
    case "chat": return chatScreen();
    case "notifications": return notificationsScreen();
    case "settings": return settingsScreen();
    case "provider-setup": return providerSetupScreen();
    case "my-services": return myServicesScreen();
    case "favorites": return favoritesScreen();
    case "contact": return contactScreen();
    case "contact-form": return contactFormScreen();
    case "help": return helpScreen();
    case "review": return reviewScreen();
    case "success": return successScreen();
    default: return homeScreen();
  }
}

function render() {
  clearInterval(chatPollTimer);
  document.body.classList.toggle("dark", Boolean(state.settings["Modo Escuro"]));
  saveAppState();
  app.innerHTML = state.view === "auth" ? authScreen()
    : state.view === "verify-email" ? emailVerificationScreen()
      : shell(pageContent());
  if (state.view === "chat") {
    const messageList = document.querySelector(".chat-messages");
    if (messageList) messageList.scrollTop = messageList.scrollHeight;
    chatPollTimer = setInterval(async () => {
      if (chatPollBusy || document.hidden || !state.activeConversationId) return;
      chatPollBusy = true;
      try {
        const result = await apiRequest(`/api/messages?contractId=${encodeURIComponent(state.activeConversationId)}`, { method: "GET", headers: {} });
        const previousLastId = state.chatMessages[state.chatMessages.length - 1]?.id || "";
        const nextLastId = result.messages[result.messages.length - 1]?.id || "";
        state.activeChat = result.conversation;
        if (previousLastId !== nextLastId || state.chatMessages.length !== result.messages.length) {
          state.chatMessages = result.messages;
          render();
        }
      } catch (error) {
        clearInterval(chatPollTimer);
        showToast(error.message);
      } finally {
        chatPollBusy = false;
      }
    }, 5000);
  }
  initializeAuth();
}

app.addEventListener("change", async (event) => {
  if (event.target.matches('input[name="account-role"]')) {
    const previousRole = state.userRole;
    try {
      await apiRequest("/api/auth/role", { method: "POST", body: JSON.stringify({ role: event.target.value }) });
      state.userRole = event.target.value;
      if (state.userRole !== "client" && !state.ownListings.length) state.view = "provider-setup";
      render();
      showToast("Perfil atualizado. Agora você pode publicar seus serviços.");
    } catch (error) {
      state.userRole = previousRole;
      render();
      showToast(error.message);
    }
    return;
  }
  if (event.target.matches("#offer-category")) {
    state.offerCategory = event.target.value;
    state.offerService = "";
    render();
  }
  if (event.target.matches("#profile-photo")) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 10 * 1024 * 1024) {
      showToast("Escolha uma foto JPEG, PNG ou WebP de até 10 MB.");
      event.target.value = "";
      return;
    }
    try {
      const photo = await compressProfilePhoto(file);
      state.profilePhoto = photo;
      document.querySelector('input[name="profilePhoto"]').value = photo;
      document.querySelector(".profile-photo-preview").innerHTML = avatar(initials(state.user), true, photo);
    } catch (error) {
      showToast(error.message);
      event.target.value = "";
    }
    return;
  }
  if (event.target.matches("#offer-service")) {
    const customField = document.querySelector(".custom-service-field");
    const customInput = document.querySelector("#offer-custom-service");
    const isCustom = event.target.value === "__custom__";
    customField.hidden = !isCustom;
    customInput.required = isCustom;
    if (isCustom) customInput.focus();
  }
});

async function compressProfilePhoto(file) {
  const source = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("Não foi possível ler a foto selecionada."));
    reader.readAsDataURL(file);
  });
  const image = await new Promise((resolve, reject) => {
    const element = new Image();
    element.onload = () => resolve(element);
    element.onerror = () => reject(new Error("A foto selecionada não pôde ser aberta."));
    element.src = source;
  });
  const scale = Math.min(1, 640 / Math.max(image.naturalWidth, image.naturalHeight));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Não foi possível preparar a foto neste dispositivo.");
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  for (const quality of [0.82, 0.68, 0.54, 0.4]) {
    const dataUrl = canvas.toDataURL("image/jpeg", quality);
    if (dataUrl.length <= 385 * 1024) return dataUrl;
  }
  throw new Error("A foto ficou muito grande mesmo após a compressão. Escolha outra imagem.");
}

function showToast(message) {
  document.querySelector(".toast")?.remove();
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.setAttribute("role", "status");
  toast.textContent = message;
  document.body.append(toast);
  clearTimeout(toastTimer);
  const duration = Math.max(3200, Math.min(9000, message.length * 35));
  toastTimer = setTimeout(() => toast.remove(), duration);
}

function openProvider(id) {
  state.provider = allListings().find((item) => item.id === id) || state.provider;
  state.view = "provider-profile";
  state.drawerOpen = false;
  render();
}

app.addEventListener("input", (event) => {
  if (event.target.matches("#booking-address")) {
    state.bookingAddress = event.target.value;
    return;
  }
  if (event.target.matches("#booking-details")) {
    state.bookingDetails = event.target.value;
    return;
  }
  if (event.target.matches("#auth-cpf, #auth-phone")) {
    const input = event.target;
    const cpfInput = input.id === "auth-cpf";
    maskRegistrationInput(input, cpfInput ? formatCPF : formatBrazilianPhone);
    updateRegistrationFieldValidity(
      input,
      cpfInput ? isValidCPF : isValidBrazilianPhone,
      cpfInput ? "Digite um CPF válido com 11 dígitos verificadores." : "Digite um celular válido com DDD e número brasileiro.",
      cpfInput ? "auth-cpf-hint" : "auth-phone-hint",
    );
    return;
  }
  if (event.target.matches("#auth-code")) {
    event.target.value = event.target.value.replace(/[^a-z\d]/gi, "").slice(0, 6).toUpperCase();
    return;
  }
  if (event.target.matches("#provider-search")) {
    const cursor = event.target.selectionStart;
    state.query = event.target.value;
    const listings = document.querySelector(".content");
    listings.innerHTML = state.view === "professionals" ? professionalsScreen() : listingsScreen();
    const search = document.querySelector("#provider-search");
    search?.focus();
    search?.setSelectionRange(cursor, cursor);
  }
});

app.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const { action } = target.dataset;
  switch (action) {
    case "auth-home": break;
    case "toggle-auth":
      state.authMode = state.authMode === "login" ? "register" : "login";
      break;
    case "cancel-verification":
      state.view = state.verificationPurpose === "deactivate" ? "settings" : "auth";
      if (state.verificationPurpose === "register") state.authMode = "register";
      state.pendingEmail = "";
      break;
    case "resend-code":
      try {
        const result = await apiRequest("/api/auth/verification/resend", {
          method: "POST",
          body: JSON.stringify({
            purpose: state.verificationPurpose,
            ...(state.verificationPurpose === "register" ? { email: state.pendingEmail } : {}),
          }),
        });
        showToast(result.message);
      } catch (error) {
        showToast(error.message);
      }
      return;
    case "go-home":
      state.view = state.user === "Visitante" ? "auth" : "home";
      state.drawerOpen = false;
      state.query = "";
      break;
    case "open-drawer": state.drawerOpen = true; break;
    case "close-drawer": state.drawerOpen = false; break;
    case "categories":
      try {
        await refreshRemoteData();
      } catch (error) {
        showToast(error.message);
      }
      state.view = "categories";
      break;
    case "open-category":
      try {
        await refreshRemoteData();
      } catch (error) {
        showToast(error.message);
      }
      state.category = target.dataset.category;
      state.service = "";
      state.query = "";
      state.view = "listings";
      break;
    case "select-service":
      state.service = target.dataset.service;
      state.query = "";
      state.view = "professionals";
      break;
    case "back-to-services":
      state.service = "";
      state.query = "";
      state.view = "listings";
      break;
    case "open-provider":
      openProvider(target.dataset.provider || allListings()[0]?.id);
      return;
    case "offer-service":
      state.editingListingId = "";
      state.view = "provider-setup";
      state.offerCategory = state.ownListings[0]?.category || categories[0].name;
      state.drawerOpen = false;
      break;
    case "my-services": state.view = "my-services"; state.drawerOpen = false; break;
    case "edit-profile":
      state.view = "edit-profile";
      break;
    case "remove-profile-photo":
      state.profilePhoto = "";
      document.querySelector('input[name="profilePhoto"]').value = "";
      document.querySelector(".profile-photo-preview").innerHTML = avatar(initials(state.user), true);
      break;
    case "cancel-listing-edit":
      state.editingListingId = "";
      state.view = "my-services";
      break;
    case "edit-listing": {
      const listing = state.ownListings.find((item) => item.id === target.dataset.listing);
      if (!listing) {
        showToast("Não foi possível encontrar esse anúncio.");
        return;
      }
      state.editingListingId = listing.id;
      state.offerCategory = listing.category;
      state.view = "provider-setup";
      break;
    }
    case "delete-listing": {
      if (!window.confirm("Deseja excluir este anúncio?")) return;
      try {
        await apiRequest(`/api/listings/${encodeURIComponent(target.dataset.listing)}`, { method: "DELETE" });
        await refreshRemoteData();
        showToast("Anúncio removido.");
      } catch (error) {
        showToast(error.message);
      }
      break;
    }
    case "mark-all-notifications-read":
      try {
        await apiRequest("/api/notifications", { method: "POST", body: "{}" });
        await refreshNotifications();
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    case "delete-account":
      if (!window.confirm("Deseja mesmo desativar sua conta? Você precisará confirmar essa ação pelo código enviado ao seu e-mail.")) return;
      try {
        await apiRequest("/api/auth/deactivate/start", { method: "POST", body: "{}" });
        state.verificationPurpose = "deactivate";
        state.view = "verify-email";
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    case "logout":
      try {
        await apiRequest("/api/auth/logout", { method: "POST", body: "{}" });
      } catch (error) {
        showToast(error.message);
        return;
      }
      state.user = "Visitante";
      state.userId = "";
      state.userRole = "client";
      state.profileBio = "";
      state.profileLocation = "";
      state.profilePhoto = "";
      state.publicListings = [];
      state.userEmail = "";
      state.ownListings = [];
      state.favorites = [];
      state.contracts = [];
      state.messages = [];
      state.conversations = [];
      state.activeChat = null;
      state.activeConversationId = "";
      state.chatMessages = [];
      state.notifications = [];
      state.providerAvailability = [];
      state.availableTimes = [];
      state.contractNotes = [];
      state.view = "auth";
      state.authMode = "login";
      state.drawerOpen = false;
      state.query = "";
      showToast("Você saiu da sua conta.");
      break;
    case "profile": state.view = "profile"; break;
    case "calendar":
      if (state.userRole === "provider") {
        showToast("Ative também o modo contratante em Perfil ou Configurações para agendar.");
        return;
      }
      if (isProviderBooked(state.provider)) {
        state.view = "contracts";
        state.contractTab = "requested";
        showToast("Este profissional já tem uma contratação ativa.");
        break;
      }
      state.view = "calendar";
      state.selectedTime = "";
      state.selectedDay = 0;
      state.bookingDetails = "";
      state.bookingAddress = "";
      try {
        await loadSelectedAvailability();
      } catch (error) {
        showToast(error.message);
      }
      break;
    case "select-day":
      state.selectedDay = Number(target.dataset.day);
      try {
        await loadSelectedAvailability();
      } catch (error) {
        showToast(error.message);
      }
      break;
    case "select-time":
      if (state.availableTimes.includes(target.dataset.time)) state.selectedTime = target.dataset.time;
      break;
    case "submit-booking": {
      if (!state.selectedTime) return;
      if (!["client", "both"].includes(state.userRole)) {
        showToast("Ative o modo contratante no seu perfil para agendar.");
        return;
      }
      if (state.provider.ownerId === state.userId) {
        showToast("Você não pode contratar o seu próprio serviço.");
        return;
      }
      if (isProviderBooked(state.provider)) {
        showToast("Este profissional já está ocupado. Escolha outro ou cancele seu pedido ativo.");
        state.view = "listings";
        render();
        return;
      }
      try {
        const selectedDate = bookingDays()[state.selectedDay];
        await apiRequest("/api/contracts", {
          method: "POST",
          body: JSON.stringify({
            listingId: state.provider.id,
            serviceDate: selectedDate.value,
            time: state.selectedTime,
            timezoneOffsetMinutes: new Date().getTimezoneOffset(),
            address: state.bookingAddress.trim(),
            details: state.bookingDetails,
          }),
        });
        await refreshRemoteData();
        state.bookingDetails = "";
        state.bookingAddress = "";
        state.contractTab = "requested";
        state.view = "contracts";
        showToast("Pedido enviado ao profissional.");
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    }
    case "contracts":
      try {
        await refreshRemoteData();
      } catch (error) {
        showToast(error.message);
      }
      state.view = "contracts";
      state.contractTab = "requested";
      break;
    case "contract-tab":
      try {
        await refreshRemoteData();
      } catch (error) {
        showToast(error.message);
      }
      state.contractTab = target.dataset.tab;
      break;
    case "contract-detail":
      state.detailId = target.dataset.contract;
      state.contractNotes = [];
      try {
        await loadContractNotes(state.detailId);
      } catch (error) {
        showToast(error.message);
      }
      state.view = "contract-detail";
      break;
    case "cancel-contract": {
      const contract = state.contracts.find((item) => item.id === target.dataset.contract);
      if (!contract || contract.tab !== "requested" || !["Aguardando confirmação", "Esperando confirmação", "Confirmado"].includes(contract.state)) return;
      if (!window.confirm(`Cancelar a contratação de ${contract.name}? O profissional voltará a aparecer nos resultados.`)) return;
      try {
        await apiRequest(`/api/contracts/${encodeURIComponent(contract.id)}/status`, {
          method: "POST",
          body: JSON.stringify({ status: "cancel" }),
        });
        await refreshRemoteData();
      } catch (error) {
        showToast(error.message);
        return;
      }
      state.contractTab = "requested";
      state.view = "contracts";
      showToast("Contratação cancelada. O profissional está disponível novamente.");
      break;
    }
    case "respond-contract": {
      try {
        await apiRequest(`/api/contracts/${encodeURIComponent(target.dataset.contract)}/status`, {
          method: "POST",
          body: JSON.stringify({ status: target.dataset.status }),
        });
        await refreshRemoteData();
        state.contractTab = "hired";
        state.view = "contracts";
        showToast(target.dataset.status === "confirm" ? "Pedido aceito." : "Pedido recusado.");
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    }
    case "messages":
      try {
        await refreshConversations();
      } catch (error) {
        showToast(error.message);
      }
      state.view = "messages";
      break;
    case "open-contract-chat":
      try {
        await openConversation(target.dataset.contract);
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    case "notifications":
      try {
        await refreshNotifications();
      } catch (error) {
        showToast(error.message);
      }
      state.view = "notifications";
      state.drawerOpen = false;
      break;
    case "clear-notifications":
      try {
        await apiRequest("/api/notifications", { method: "DELETE" });
        state.notifications = [];
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    case "mark-notification-read":
      try {
        await apiRequest(`/api/notifications/${encodeURIComponent(target.dataset.notification)}/read`, { method: "POST", body: "{}" });
        await refreshNotifications();
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    case "open-notification-contract":
      try {
        await refreshRemoteData();
        const contract = state.contracts.find((item) => item.id === target.dataset.contract);
        if (!contract) {
          showToast("Esta contratação não está mais disponível.");
          return;
        }
        state.detailId = contract.id;
        await loadContractNotes(contract.id);
        state.view = "contract-detail";
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    case "add-availability-slot": {
      const weekday = Number(document.querySelector("#availability-day")?.value);
      const timeInput = document.querySelector("#availability-time");
      const serviceTime = timeInput?.value || "";
      if (!Number.isInteger(weekday) || weekday < 0 || weekday > 6 || !serviceTime || !timeInput.checkValidity()) {
        showToast("Escolha um dia e um horário.");
        return;
      }
      if (!state.providerAvailability.some((slot) => slot.weekday === weekday && slot.time === serviceTime)) {
        state.providerAvailability.push({ weekday, time: serviceTime });
        state.providerAvailability.sort((a, b) => a.weekday - b.weekday || a.time.localeCompare(b.time));
      }
      break;
    }
    case "remove-availability-slot":
      state.providerAvailability.splice(Number(target.dataset.index), 1);
      break;
    case "settings":
      state.view = "settings";
      state.drawerOpen = false;
      break;
    case "toggle-setting": {
      const setting = target.dataset.setting;
      state.settings[setting] = !state.settings[setting];
      break;
    }
    case "favorites": state.view = "favorites"; state.drawerOpen = false; break;
    case "toggle-favorite": {
      const provider = allListings().find((item) => item.id === target.dataset.provider);
      if (!provider) return;
      const existing = state.favorites.findIndex((item) => item.id === provider.id);
      try {
        await apiRequest(existing >= 0 ? `/api/favorites/${encodeURIComponent(provider.id)}` : "/api/favorites", {
          method: existing >= 0 ? "DELETE" : "POST",
          ...(existing >= 0 ? {} : { body: JSON.stringify({ listingId: provider.id }) }),
        });
        await refreshRemoteData();
        showToast(existing >= 0 ? "Profissional removido dos favoritos." : "Profissional adicionado aos favoritos.");
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    }
    case "favorite-current": {
      const existing = state.favorites.findIndex((item) => item.id === state.provider.id);
      try {
        await apiRequest(existing >= 0 ? `/api/favorites/${encodeURIComponent(state.provider.id)}` : "/api/favorites", {
          method: existing >= 0 ? "DELETE" : "POST",
          ...(existing >= 0 ? {} : { body: JSON.stringify({ listingId: state.provider.id }) }),
        });
        await refreshRemoteData();
        showToast(existing >= 0 ? "Profissional removido dos favoritos." : "Profissional adicionado aos favoritos.");
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    }
    case "contact": state.view = "contact"; state.drawerOpen = false; break;
    case "contact-form":
      state.contactType = target.dataset.type;
      state.view = "contact-form";
      state.drawerOpen = false;
      break;
    case "help": state.view = "help"; break;
    case "rate": state.selectedStars = Number(target.dataset.stars); break;
    case "review": state.view = "review"; break;
  }
  render();
});

app.addEventListener("submit", async (event) => {
  const form = event.target.closest("[data-form]");
  if (!form) return;
  event.preventDefault();
  const data = new FormData(form);
  switch (form.dataset.form) {
    case "auth": {
      const name = String(data.get("name") || "").trim();
      if (state.authMode === "register" && (!isValidCPF(String(data.get("cpf") || "")) || !isValidBrazilianPhone(String(data.get("phone") || "")))) {
        showToast("Confira o CPF e o número de celular informados.");
        return;
      }
      if (state.authMode === "register" && data.get("password") !== data.get("confirm")) {
        showToast("As senhas não coincidem. Confira e tente novamente.");
        return;
      }
      try {
        if (state.authMode === "register") {
          const result = await apiRequest("/api/auth/register/start", {
            method: "POST",
            body: JSON.stringify({
              name,
              email: data.get("email"),
              cpf: data.get("cpf"),
              phone: data.get("phone"),
              role: data.get("role"),
              password: data.get("password"),
            }),
          });
          state.pendingEmail = String(data.get("email") || "").trim().toLowerCase();
          state.verificationPurpose = "register";
          state.view = "verify-email";
          showToast(result.message);
          render();
          return;
        }
        const result = await apiRequest("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: data.get("email"), password: data.get("password") }),
        });
        setAuthenticatedUser(result.user);
        state.view = state.userRole !== "client" ? "provider-setup" : "home";
        try {
          await refreshRemoteData(true);
        } catch (error) {
          showToast(error.message);
        }
        state.view = state.userRole !== "client" && !state.ownListings.length ? "provider-setup" : "home";
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    }
    case "auth-verify": {
      try {
        if (state.verificationPurpose === "register") {
          const result = await apiRequest("/api/auth/register/verify", {
            method: "POST",
            body: JSON.stringify({ email: state.pendingEmail, code: data.get("code") }),
          });
          setAuthenticatedUser(result.user);
          state.view = state.userRole !== "client" ? "provider-setup" : "home";
          try {
            await refreshRemoteData();
          } catch (error) {
            showToast(error.message);
          }
          state.view = state.userRole !== "client" ? "provider-setup" : "home";
        } else {
          await apiRequest("/api/auth/deactivate/verify", {
            method: "POST",
            body: JSON.stringify({ code: data.get("code") }),
          });
          localStorage.removeItem(`${STORAGE_KEY_PREFIX}${state.userId}`);
          ["autonome-app-state-v4", "autonome-app-state-v3", "autonome-app-state-v2"].forEach((key) => localStorage.removeItem(key));
          Object.assign(state, {
            user: "Visitante",
            userId: "",
            userEmail: "",
            userRole: "client",
            ownListings: [],
            favorites: [],
            contracts: [],
            messages: [],
            notifications: [],
            view: "auth",
            authMode: "login",
            pendingEmail: "",
            drawerOpen: false,
          });
          showToast("Conta desativada. Seus dados foram movidos para a lista de usuários desativados.");
        }
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    }
    case "offer": {
      const category = String(data.get("category") || "");
      const selectedService = String(data.get("service") || "");
      const service = selectedService === "__custom__" ? String(data.get("customService") || "").trim() : selectedService;
      if (!categories.some((item) => item.name === category) || !service) {
        showToast("Escolha uma área e informe o serviço que você oferece.");
        return;
      }
      const listing = {
        service,
        category,
        location: String(data.get("location") || "").trim(),
        about: String(data.get("about") || "").trim(),
        price: String(data.get("price") || "").trim(),
      };
      const editingListingId = state.editingListingId;
      try {
        const result = await apiRequest(editingListingId ? `/api/listings/${encodeURIComponent(editingListingId)}` : "/api/listings", {
          method: "POST",
          body: JSON.stringify(listing),
        });
        if (result.user) state.userRole = result.user.role;
        await refreshRemoteData();
      } catch (error) {
        showToast(error.message);
        return;
      }
      state.editingListingId = "";
      state.view = "my-services";
      showToast(editingListingId ? "Serviço atualizado." : "Seu serviço foi publicado!");
      break;
    }
    case "availability": {
      try {
        const result = await apiRequest("/api/availability", {
          method: "POST",
          body: JSON.stringify({ availability: state.providerAvailability }),
        });
        state.providerAvailability = result.availability;
        showToast("Sua disponibilidade foi atualizada.");
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    }
    case "contract-note": {
      const body = String(data.get("body") || "").trim();
      try {
        await apiRequest(`/api/contracts/${encodeURIComponent(state.detailId)}/notes`, {
          method: "POST",
          body: JSON.stringify({ body }),
        });
        await loadContractNotes(state.detailId);
        showToast("Anotação privada salva.");
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    }
    case "profile": {
      try {
        const result = await apiRequest("/api/auth/profile", {
          method: "POST",
          body: JSON.stringify({
            name: String(data.get("name") || "").trim(),
            profileBio: String(data.get("profileBio") || "").trim(),
            profileLocation: String(data.get("profileLocation") || "").trim(),
            profilePhoto: String(data.get("profilePhoto") || ""),
          }),
        });
        state.user = result.user.name;
        state.profileBio = result.user.profileBio || "";
        state.profileLocation = result.user.profileLocation || "";
        state.profilePhoto = result.user.profilePhoto || "";
        await refreshRemoteData();
        state.view = "profile";
        showToast("Seu perfil foi atualizado.");
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
    }
    case "chat": {
      const message = String(data.get("message") || "").trim();
      if (!message) return;
      try {
        await apiRequest("/api/messages", {
          method: "POST",
          body: JSON.stringify({ contractId: state.activeConversationId, body: message }),
        });
        await openConversation(state.activeConversationId);
        await refreshConversations();
      } catch (error) {
        showToast(error.message);
        return;
      }
      break;
      break;
    }
    case "contact":
      state.view = "success";
      break;
    case "review":
      if (!state.selectedStars) return;
      state.view = "success";
      showToast("Obrigado por avaliar o serviço!");
      break;
  }
  render();
});

app.addEventListener("keydown", (event) => {
  const target = event.target.closest(".brand-lockup[role='button']");
  if (target && (event.key === "Enter" || event.key === " ")) {
    event.preventDefault();
    state.view = "home";
    render();
  }
});

render();

if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
  navigator.serviceWorker.register("./service-worker.js")
    .catch((error) => {
      console.error("Não foi possível ativar o modo offline do AutonoMe.", error);
      showToast("O app abriu, mas não foi possível habilitar o acesso offline.");
    });
}
