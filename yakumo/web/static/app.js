"use strict";

// --- Тексты интерфейса (ru/en) ---

const TEXTS = {
  ru: {
    home: "Главная", files: "Файлы", modules: "Модули", log: "Журнал", settings: "Настройки",
    loading: "Загрузка…", running: "работает", offline: "нет связи", connecting: "подключение…",
    filesSoon: "Здесь будет файловый менеджер рабочей папки.",
    modulesSoon: "Здесь будет список модулей и их страницы.",
    logSoon: "Здесь будет журнал в реальном времени.",
    settingsHint: "Изменения сохраняются сразу.",
    startup: "Запуск", appearance: "Внешний вид", paths: "Пути",
    openBrowser: "Открывать браузер при старте",
    openBrowserHint: "После запуска Yakumo сразу откроется эта страница.",
    tray: "Значок в трее", trayHint: "Меню у часов: открыть, папки, выход.",
    trayMissing: "Нужны библиотеки pystray и Pillow (есть в портативной сборке).",
    autostart: "Запускать вместе с Windows",
    autostartHint: "Yakumo стартует без окна консоли и без браузера.",
    autostartMissing: "Работает только в Windows.",
    language: "Язык", languageHint: "Язык веб-версии и меню в трее.",
    fontSize: "Размер шрифта", compact: "Компактный режим",
    compactHint: "Меньше отступов, больше помещается на экран.",
    restart: "Нужен перезапуск Yakumo, чтобы изменение вступило в силу.",
    saved: "Сохранено", saveError: "Не сохранилось",
    avatar: "Yakumo: открыть чат", chatClose: "Закрыть чат", chatPlaceholder: "Напишите сообщение…",
    send: "Отправить", chatSub: "чат пока без собеседника",
    greeting: "Привет! Я Yakumo. Меня можно перетащить куда угодно, а по нажатию открывается этот чат.",
    stubReply: "Я пока только учусь отвечать. Скоро здесь появится настоящий собеседник.",
    pathNames: { app: "Программа", data: "Данные", config: "Настройки", logs: "Журналы", cache: "Кэш",
                 temp: "Временные", workspace: "Рабочая папка", modules: "Модули", web: "Веб-страницы" },
  },
  en: {
    home: "Home", files: "Files", modules: "Modules", log: "Log", settings: "Settings",
    loading: "Loading…", running: "running", offline: "offline", connecting: "connecting…",
    filesSoon: "A file manager for the workspace will be here.",
    modulesSoon: "The module list and module pages will be here.",
    logSoon: "A live log will be here.",
    settingsHint: "Changes are saved immediately.",
    startup: "Startup", appearance: "Appearance", paths: "Paths",
    openBrowser: "Open browser on start",
    openBrowserHint: "This page opens right after Yakumo starts.",
    tray: "Tray icon", trayHint: "Menu near the clock: open, folders, exit.",
    trayMissing: "Requires pystray and Pillow (included in the portable build).",
    autostart: "Start with Windows",
    autostartHint: "Yakumo starts without a console window or browser.",
    autostartMissing: "Windows only.",
    language: "Language", languageHint: "Language of the web version and tray menu.",
    fontSize: "Font size", compact: "Compact mode",
    compactHint: "Less spacing, more fits on screen.",
    restart: "Restart Yakumo for this change to take effect.",
    saved: "Saved", saveError: "Not saved",
    avatar: "Yakumo: open chat", chatClose: "Close chat", chatPlaceholder: "Type a message…",
    send: "Send", chatSub: "chat has no one to talk to yet",
    greeting: "Hi! I'm Yakumo. Drag me anywhere; click me to open this chat.",
    stubReply: "I'm still learning to reply. A real conversation partner is coming soon.",
    pathNames: { app: "Program", data: "Data", config: "Settings", logs: "Logs", cache: "Cache",
                 temp: "Temp", workspace: "Workspace", modules: "Modules", web: "Web pages" },
  },
};
let T = TEXTS.ru;

// Разделы верхнего меню. «Настройки» живут отдельно, в левой полосе.
const SECTIONS = [
  { id: "home", icon: "i-home" },
  { id: "files", icon: "i-files" },
  { id: "modules", icon: "i-modules" },
  { id: "log", icon: "i-log" },
];
const SETTINGS = { id: "settings", icon: "i-settings" };

const content = document.getElementById("content");
const avatarBtn = document.getElementById("avatar");
const avatarImg = avatarBtn.querySelector("img");
const chatBox = document.getElementById("chat");
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const statusEl = document.getElementById("status");
let status = null;
let settings = null;
let online = null;

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, "");
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c != null && c !== "") el.append(c instanceof Node ? c : String(c));
  return el;
}

function icon(id) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", "#" + id);
  svg.append(use);
  return svg;
}

function buildMenu() {
  const nav = document.querySelector("[data-menu]");
  nav.replaceChildren(...SECTIONS.map((s) => {
    const a = h("a", { class: "icon-btn", href: "#/" + s.id, "data-route": s.id,
                       "data-label": T[s.id], "aria-label": T[s.id] });
    a.append(icon(s.icon));
    return a;
  }));
  const gear = document.querySelector(".rail-settings");
  gear.dataset.label = T.settings;
  gear.setAttribute("aria-label", T.settings);
  avatarBtn.setAttribute("aria-label", T.avatar);
  chatBox.setAttribute("aria-label", T.avatar);
  document.getElementById("chat-close").setAttribute("aria-label", T.chatClose);
  document.getElementById("chat-sub").textContent = T.chatSub;
  chatInput.placeholder = T.chatPlaceholder;
  chatForm.querySelector(".chat-send").setAttribute("aria-label", T.send);
}

// --- Внешний вид из настроек ---

function applyLook() {
  const v = settings?.values;
  if (!v) return;
  T = TEXTS[v.language] || TEXTS.ru;
  document.documentElement.lang = v.language;
  document.documentElement.style.setProperty("--scale", v.font_scale / 100);
  document.body.classList.toggle("compact", v.compact);
  buildMenu();
  placeAvatar();
  showOnline();
}

// --- Страницы ---

function placeholder(section, text) {
  const box = h("div", { class: "empty" });
  box.append(icon(section.icon), h("strong", {}, T[section.id]), h("span", {}, text));
  return box;
}

function toggle(key, title, hint, { disabled = false, note = null } = {}) {
  const value = settings.values[key] && !disabled;  // недоступное показываем выключенным
  const input = h("input", { type: "checkbox", role: "switch", checked: value, disabled,
                             onchange: (e) => save({ [key]: e.target.checked }) });
  return h("label", { class: "row" + (disabled ? " disabled" : "") },
    h("span", { class: "row-text" }, h("span", { class: "row-title" }, title),
      h("span", { class: "row-hint" }, note || hint), restartNote(key)),
    h("span", { class: "switch" }, input, h("span", { class: "knob" })));
}

function choice(key, title, hint, labels) {
  const current = settings.values[key];
  const group = h("span", { class: "segmented", role: "radiogroup", "aria-label": title },
    settings.options[key].map((opt) => h("button", {
      type: "button", role: "radio", "aria-checked": String(opt === current),
      class: opt === current ? "on" : "", onclick: () => opt !== current && save({ [key]: opt }),
    }, labels(opt))));
  return h("div", { class: "row" },
    h("span", { class: "row-text" }, h("span", { class: "row-title" }, title),
      hint ? h("span", { class: "row-hint" }, hint) : "", restartNote(key)),
    group);
}

function restartNote(key) {
  return settings.restart_needed.includes(key) ? h("span", { class: "row-warn" }, T.restart) : "";
}

const PAGES = {
  home: () => [],  // пока пустая
  files: () => [h("h1", {}, T.files), placeholder(SECTIONS[1], T.filesSoon)],
  modules: () => [h("h1", {}, T.modules), placeholder(SECTIONS[2], T.modulesSoon)],
  log: () => [h("h1", {}, T.log), placeholder(SECTIONS[3], T.logSoon)],
  settings() {
    if (!settings) return [h("h1", {}, T.settings), h("p", { class: "subtitle" }, T.loading)];
    const paths = status ? Object.entries(status.paths) : [];
    return [
      h("h1", {}, T.settings),
      h("p", { class: "subtitle" }, T.settingsHint, " ", h("span", { class: "saved", id: "saved" })),
      h("section", { class: "card group" },
        h("h2", {}, T.startup),
        toggle("open_browser", T.openBrowser, T.openBrowserHint),
        toggle("tray", T.tray, T.trayHint,
               { disabled: !settings.tray_available, note: settings.tray_available ? null : T.trayMissing }),
        toggle("autostart", T.autostart, T.autostartHint,
               { disabled: !settings.autostart_supported,
                 note: settings.autostart_supported ? null : T.autostartMissing })),
      h("section", { class: "card group" },
        h("h2", {}, T.appearance),
        choice("language", T.language, T.languageHint, (v) => ({ ru: "Русский", en: "English" })[v]),
        choice("font_scale", T.fontSize, null, (v) => `${v}%`),
        toggle("compact", T.compact, T.compactHint)),
      h("section", { class: "card group" },
        h("h2", {}, T.paths),
        h("table", { class: "kv" }, paths.map(([k, v]) => h("tr", {}, h("td", {}, T.pathNames[k] || k), h("td", {}, v))))),
    ];
  },
};

function currentPage() {
  const id = location.hash.replace(/^#\/?/, "") || "home";
  return PAGES[id] ? id : "home";
}

function render() {
  const page = currentPage();
  for (const a of document.querySelectorAll("[data-route]")) {
    const active = a.dataset.route === page;
    a.classList.toggle("active", active);
    if (active) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  document.title = `${T[page]} · Yakumo`;
  content.replaceChildren(...PAGES[page]());
}

// --- Данные с сервера ---

function showOnline() {
  statusEl.className = "status" + (online === true ? " ok" : online === false ? " bad" : "");
  const text = online === true ? T.running : online === false ? T.offline : T.connecting;
  statusEl.querySelector(".status-text").textContent = text;
  statusEl.title = text;
}

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function refreshStatus() {
  try {
    status = await getJSON("/api/status");
    online = true;
  } catch {
    online = false;
  }
  showOnline();
}

async function save(changes) {
  const flag = () => document.getElementById("saved");
  try {
    const r = await fetch("/api/settings", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
    settings = data;
    applyLook();
    render();
    flag().textContent = "✓ " + T.saved;
    flag().className = "saved ok";
  } catch (e) {
    render();  // вернуть переключатели в сохранённое состояние
    flag().textContent = `${T.saveError}: ${e.message}`;
    flag().className = "saved bad";
  }
}

async function start() {
  buildMenu();
  render();
  try {
    settings = await getJSON("/api/settings");
    applyLook();
  } catch { /* без настроек работаем со значениями по умолчанию */ }
  await refreshStatus();
  render();
  // Главную обновляем по таймеру; формы настроек не трогаем, чтобы не сбить ввод.
  // Следующий опрос только после завершения предыдущего, чтобы запросы не копились.
  const poll = async () => {
    const hadStatus = status !== null;
    await refreshStatus();
    if (!hadStatus && currentPage() === "settings") render();
    setTimeout(poll, 10000);
  };
  setTimeout(poll, 10000);
}

// --- Аватар и чат ---
// Позиция аватара и переписка хранятся в браузере: это личное удобство, не настройки Yakumo.

function stored(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function store(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* приватный режим */ }
}

// Позиция в долях свободного места (0..1), чтобы аватар оставался на своём месте при смене размера окна.
let avatarPos = stored("yakumo.avatar", { x: 1, y: 1 });
let messages = stored("yakumo.chat", []);

// Страница масштабируется через zoom, поэтому размеры окна переводим в CSS-пиксели страницы.
function zoom() { return (settings?.values.font_scale || 100) / 100; }
function viewport() { return { w: innerWidth / zoom(), h: innerHeight / zoom() }; }
function margins() { return { top: document.querySelector(".topbar").offsetHeight + 4, side: 8 }; }

function placeAvatar() {
  const { w, h } = viewport(), m = margins(), size = avatarBtn.offsetWidth;
  // Подсказка браузеру, какой из размеров картинки брать: с учётом масштаба страницы.
  avatarImg.sizes = Math.round(size * zoom()) + "px";
  const free = { x: Math.max(0, w - size - 2 * m.side), y: Math.max(0, h - size - m.top - m.side) };
  avatarBtn.style.left = m.side + avatarPos.x * free.x + "px";
  avatarBtn.style.top = m.top + avatarPos.y * free.y + "px";
  if (!chatBox.hidden) placeChat();
}

// Чат рядом с аватаром: слева или справа, если хватает места, иначе над или под ним.
function placeChat() {
  const { w, h } = viewport(), m = margins(), gap = 10;
  const a = { x: avatarBtn.offsetLeft, y: avatarBtn.offsetTop, s: avatarBtn.offsetWidth };
  const cw = Math.min(340, w - 2 * m.side);
  let ch = Math.min(440, h - m.top - m.side), x, y;
  const clampX = (v) => Math.min(Math.max(v, m.side), w - cw - m.side);
  const clampY = (v) => Math.min(Math.max(v, m.top), h - ch - m.side);
  if (a.x - gap - cw >= m.side || a.x + a.s + gap + cw <= w - m.side) {
    x = a.x - gap - cw >= m.side ? a.x - gap - cw : a.x + a.s + gap;
    y = clampY(a.y + a.s - ch);
  } else {
    const above = a.y - gap - m.top, below = h - m.side - (a.y + a.s + gap);
    ch = Math.min(ch, Math.max(above, below, 200));
    x = clampX(a.x + a.s / 2 - cw / 2);
    y = above >= below ? clampY(a.y - gap - ch) : clampY(a.y + a.s + gap);
  }
  Object.assign(chatBox.style, { left: x + "px", top: y + "px", width: cw + "px", height: ch + "px" });
}

function setChatOpen(open) {
  chatBox.hidden = !open;
  avatarBtn.setAttribute("aria-expanded", String(open));
  if (!open) return;
  if (!messages.length) addMessage("bot", T.greeting);
  placeChat();
  chatInput.focus();
}

function showMessages() {
  chatLog.replaceChildren(...messages.map((m) => h("div", { class: "msg " + m.from }, m.text)));
  chatLog.scrollTop = chatLog.scrollHeight;
}

function addMessage(from, text) {
  messages = [...messages, { from, text }].slice(-200);
  store("yakumo.chat", messages);
  showMessages();
}

// Заготовка: собеседник ещё не подключён, отвечаем шаблонной фразой.
async function reply(text) {
  return T.stubReply;
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = "";
  chatInput.style.height = "";
  addMessage("me", text);
  addMessage("bot", await reply(text));
});
chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); chatForm.requestSubmit(); }
  if (e.key === "Escape") { setChatOpen(false); avatarBtn.focus(); }
});
chatInput.addEventListener("input", () => {
  chatInput.style.height = "";
  chatInput.style.height = chatInput.scrollHeight + 2 + "px";
});
document.getElementById("chat-close").addEventListener("click", () => { setChatOpen(false); avatarBtn.focus(); });

// Перетаскивание: короткое нажатие без сдвига открывает чат, сдвиг больше 5 точек двигает аватар.
let drag = null;
avatarBtn.addEventListener("pointerdown", (e) => {
  if (e.button !== 0) return;
  justDragged = false;
  drag = { x: e.clientX, y: e.clientY, left: avatarBtn.offsetLeft, top: avatarBtn.offsetTop, moved: false };
  avatarBtn.setPointerCapture(e.pointerId);
});
avatarBtn.addEventListener("pointermove", (e) => {
  if (!drag) return;
  const dx = (e.clientX - drag.x) / zoom(), dy = (e.clientY - drag.y) / zoom();
  if (!drag.moved && Math.hypot(dx, dy) < 5) return;
  drag.moved = true;
  avatarBtn.classList.add("dragging");
  const { w, h } = viewport(), m = margins(), size = avatarBtn.offsetWidth;
  const free = { x: Math.max(1, w - size - 2 * m.side), y: Math.max(1, h - size - m.top - m.side) };
  avatarPos = {
    x: Math.min(Math.max((drag.left + dx - m.side) / free.x, 0), 1),
    y: Math.min(Math.max((drag.top + dy - m.top) / free.y, 0), 1),
  };
  placeAvatar();
});
let justDragged = false;
function endDrag() {
  if (drag?.moved) { store("yakumo.avatar", avatarPos); justDragged = true; }
  drag = null;
  avatarBtn.classList.remove("dragging");
}
avatarBtn.addEventListener("pointerup", endDrag);
avatarBtn.addEventListener("pointercancel", endDrag);
avatarBtn.addEventListener("click", () => {
  // После перетаскивания браузер всё равно присылает click, его пропускаем.
  if (justDragged) { justDragged = false; return; }
  setChatOpen(chatBox.hidden);
});

window.addEventListener("resize", placeAvatar);
window.addEventListener("hashchange", render);
showMessages();
placeAvatar();
start();
