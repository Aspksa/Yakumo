"use strict";

// Разделы. Один список строит оба меню: верхнее и левое.
const SECTIONS = [
  { id: "home", label: "Главная", icon: "i-home" },
  { id: "files", label: "Файлы", icon: "i-files" },
  { id: "modules", label: "Модули", icon: "i-modules" },
  { id: "log", label: "Журнал", icon: "i-log" },
];
const SETTINGS = { id: "settings", label: "Настройки", icon: "i-settings" };

const PATH_LABELS = {
  app: "Программа", data: "Данные", config: "Настройки", logs: "Журналы", cache: "Кэш",
  temp: "Временные", workspace: "Рабочая папка", modules: "Модули", web: "Веб-страницы",
};

const content = document.getElementById("content");
const statusEl = document.getElementById("status");
let status = null;

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v);
  }
  for (const c of children.flat()) el.append(c instanceof Node ? c : String(c));
  return el;
}

function icon(id) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", "#" + id);
  svg.append(use);
  return svg;
}

function buildMenus() {
  for (const nav of document.querySelectorAll("[data-menu]")) {
    for (const s of SECTIONS) {
      const a = h("a", { class: "icon-btn", href: "#/" + s.id, "data-route": s.id,
                         "data-label": s.label, "aria-label": s.label });
      a.append(icon(s.icon));
      nav.append(a);
    }
  }
}

// --- Страницы ---

function card(title, value, hint) {
  return h("div", { class: "card" }, h("h2", {}, title), h("div", { class: "value" }, value),
           hint ? h("div", { class: "hint" }, hint) : "");
}

function placeholder(section, text) {
  const box = h("div", { class: "empty" });
  box.append(icon(section.icon), h("strong", {}, section.label), h("span", {}, text));
  return box;
}

const PAGES = {
  home() {
    if (!status) return [h("h1", {}, "Главная"), h("p", { class: "subtitle" }, "Загрузка…")];
    const okModules = status.modules.filter((m) => !m.error).length;
    return [
      h("h1", {}, "Главная"),
      h("p", { class: "subtitle" }, `${status.app} ${status.version} работает`),
      h("div", { class: "cards" },
        card("Адрес", status.url),
        card("Данные", status.storage.root, status.storage.reason),
        card("Рабочая папка", status.paths.workspace),
        card("Модули", `${okModules} из ${status.modules.length}`,
             status.modules.map((m) => m.title).join(", ") || "нет модулей")),
    ];
  },
  files: () => [h("h1", {}, "Файлы"), placeholder(SECTIONS[1], "Здесь будет файловый менеджер рабочей папки.")],
  modules: () => [h("h1", {}, "Модули"), placeholder(SECTIONS[2], "Здесь будет список модулей и их страницы.")],
  log: () => [h("h1", {}, "Журнал"), placeholder(SECTIONS[3], "Здесь будет журнал в реальном времени.")],
  settings() {
    const rows = status ? Object.entries(status.paths) : [];
    return [
      h("h1", {}, "Настройки"),
      h("p", { class: "subtitle" }, "Пока только просмотр. Редактирование появится следующим шагом."),
      h("div", { class: "card" },
        h("h2", {}, "Пути"),
        h("table", { class: "kv" }, rows.map(([k, v]) => h("tr", {}, h("td", {}, PATH_LABELS[k] || k), h("td", {}, v))))),
    ];
  },
};

function render() {
  const id = location.hash.replace(/^#\/?/, "") || "home";
  const page = PAGES[id] ? id : "home";
  for (const a of document.querySelectorAll("[data-route]")) {
    const active = a.dataset.route === page;
    a.classList.toggle("active", active);
    if (active) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  const label = [...SECTIONS, SETTINGS].find((s) => s.id === page).label;
  document.title = `${label} · Yakumo`;
  content.replaceChildren(...PAGES[page]());
}

async function refreshStatus() {
  try {
    const r = await fetch("/api/status", { cache: "no-store" });
    status = await r.json();
    statusEl.className = "status ok";
    statusEl.querySelector(".status-text").textContent = "работает";
  } catch {
    statusEl.className = "status bad";
    statusEl.querySelector(".status-text").textContent = "нет связи";
  }
}

buildMenus();
window.addEventListener("hashchange", render);
render();
refreshStatus().then(render);
setInterval(refreshStatus, 10000);
