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
    networkAccess: "Доступ по сети", accessHint: "На этом компьютере вход свободный. Для других устройств нужен пароль.",
    accessOpen: "Пароль задан. Сетевой вход защищён.", accessClosed: "Сетевой вход закрыт: пароль ещё не задан.",
    accessPassword: "Пароль для других устройств", accessPlaceholder: "Новый пароль: от 8 до 128 символов",
    accessSave: "Сохранить пароль", accessClose: "Закрыть сетевой вход", accessLogout: "Выйти на этом устройстве",
    accessLocalOnly: "Менять пароль можно только на компьютере, где запущена Yakumo.",
    accessSaved: "Сохранено. Прежние сетевые сеансы завершены.",
    avatarSection: "Аватар", avatarShow: "Показывать аватар",
    avatarShowHint: "Кицунэ на всех страницах; по нажатию на неё открывается чат.",
    avatarSize: "Размер", px: "точек", avatarMotion: "Движение", avatarGlow: "Сияние", avatarSpeed: "Скорость анимации",
    avatarEffects: "Эффекты", avatarEffectsHint: "Можно выбрать несколько сразу.", fxPower: "Сила эффектов",
    effects: { sparkles: "Золотые искры", foxfire: "Кицунэ-би", petals: "Лепестки сакуры", dust: "Золотая пыльца",
               fireflies: "Светлячки", leaves: "Листья гинкго", aura: "Золотая аура", butterflies: "Бабочки",
               mist: "Золотой туман", meteors: "Падающие звёзды", runes: "Иероглифы" },
    powers: { low: "Слабо", normal: "Обычно", high: "Сильно" },
    avatarImage: "Образ", avatarImageHint: "Эффекты, сияние и движения работают с любым образом.",
    images: { classic: "Классика", welcome: "Объятия", tender: "Нежность", prayer: "Молитва", shy: "Смущение",
              invite: "Приглашение", bow: "Поклон", respect: "Почтение", sleep: "Сон" },
    look: "Оформление", accent: "Цвет", cardRadius: "Скругление", cardRadiusHint: "Углы карточек и кнопок.",
    cardAlpha: "Прозрачность карточек",
    scale: "Масштаб", scaleHint: "Размер текста и элементов всего приложения.",
    accents: { honey: "Мёд", gold: "Золото", amber: "Янтарь", bronze: "Бронза", peach: "Персик", coral: "Коралл",
               crimson: "Алый", rose: "Розовый", sakura: "Сакура", plum: "Слива", violet: "Фиалка",
               lavender: "Лаванда", indigo: "Индиго", azure: "Лазурь", sky: "Небо", teal: "Бирюза", jade: "Нефрит",
               mint: "Мята", lime: "Лайм", silver: "Серебро", pearl: "Жемчуг" },
    radii: { none: "Нет", small: "Малое", normal: "Обычное", large: "Большое", round: "Круглое" },
    alphas: { solid: "Нет", glass: "Стекло", clear: "Сильная" },
    powerSave: "Экономия", powerSaveHint: "Анимации и эффекты останавливаются, когда окно Yakumo не активно.",
    avatarLock: "Закрепить на месте", avatarLockHint: "Аватар нельзя перетащить; по нажатию чат открывается как обычно.",
    fxMode: "Когда показывать эффекты", fxModes: { always: "Всегда", hover: "При наведении" },
    motions: { none: "Нет", float: "Парение", glide: "Мягкое парение", alive: "Живая" },
    glows: { off: "Нет", soft: "Мягкое", bright: "Яркое", pulse: "Мерцание" },
    speeds: { slow: "Медленно", normal: "Обычно", fast: "Быстро" },
    openBrowser: "Открывать браузер при старте",
    openBrowserHint: "После запуска Yakumo сразу откроется эта страница.",
    tray: "Значок в трее", trayHint: "Меню у часов: открыть, папки, выход.",
    trayMissing: "Нужны библиотеки pystray и Pillow (есть в портативной сборке).",
    autostart: "Запускать вместе с Windows",
    autostartHint: "Yakumo стартует без окна консоли и без браузера.",
    autostartMissing: "Работает только в Windows.",
    language: "Язык", languageHint: "Язык веб-версии и меню в трее.",
    compact: "Компактный режим",
    compactHint: "Меньше отступов, больше помещается на экран.",
    restart: "Нужен перезапуск Yakumo, чтобы изменение вступило в силу.",
    saved: "Сохранено", saveError: "Не сохранилось",
    avatar: "Yakumo: открыть чат", chatClose: "Закрыть чат", chatPlaceholder: "Напишите Yakumo…",
    maximize: "Развернуть", restore: "Свернуть", copy: "Копировать", copied: "Скопировано", retry: "Повторить",
    chatKeys: "Enter — отправить · Shift+Enter — новая строка",
    hints: ["Расскажи о себе", "Что ты умеешь?", "Придумай имя для проекта", "Объясни простыми словами, что такое API"],
    send: "Отправить", stop: "Остановить", clearChat: "Очистить чат", noCloud: "Cloud.ru не подключён",
    greeting: "Привет! Я Yakumo. Меня можно перетащить куда угодно, а по нажатию открывается этот чат.",
    openSettings: "Открыть настройки", stopped: "(остановлено)",
    planTitle: "Предлагаю сделать:", planRun: "Выполнить", planCancel: "Отмена", planRunning: "Выполняю…",
    planDone: (ok, n) => `Готово: ${ok} из ${n}`, planCancelled: "Отменено",
    cloudHint: "Через Cloud.ru Foundation Models со мной можно говорить в чате. Ключ выдаётся в личном кабинете Cloud.ru.",
    apiKey: "API-ключ", keySaved: (hint) => `Ключ сохранён (${hint}).`, keyNone: "Ключ ещё не сохранён.",
    keyPlaceholder: "Вставьте ключ Cloud.ru", saveKey: "Сохранить", deleteKey: "Удалить",
    connection: "Проверка связи", testConn: "Проверить", testing: "Проверяю…",
    connOk: (n) => `Связь есть, доступно моделей: ${n}.`, connUnknown: "Ещё не проверялась.",
    model: "Модель", modelHint: "Список моделей появляется после проверки связи.",
    errors: {
      no_key: "Сначала сохраните API-ключ Cloud.ru в настройках.",
      bad_key: "Cloud.ru не принял ключ. Проверьте его в настройках.",
      network: "Нет связи с Cloud.ru. Проверьте интернет.",
      rate_limit: "Слишком много запросов. Подождите немного и повторите.",
      bad_model: "Эта модель недоступна. Выберите другую в настройках.",
      no_models: "Для этого ключа нет доступных моделей.",
    },
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
    networkAccess: "Network access", accessHint: "This computer opens directly. Other devices need a password.",
    accessOpen: "A password is set. Network sign-in is protected.", accessClosed: "Network sign-in is closed: set a password first.",
    accessPassword: "Password for other devices", accessPlaceholder: "New password: 8–128 characters",
    accessSave: "Save password", accessClose: "Close network sign-in", accessLogout: "Sign out on this device",
    accessLocalOnly: "Change the password on the computer running Yakumo.",
    accessSaved: "Saved. Previous network sessions have ended.",
    avatarSection: "Avatar", avatarShow: "Show avatar",
    avatarShowHint: "The kitsune on every page; click her to open the chat.",
    avatarSize: "Size", px: "px", avatarMotion: "Motion", avatarGlow: "Glow", avatarSpeed: "Animation speed",
    avatarEffects: "Effects", avatarEffectsHint: "Pick as many as you like.", fxPower: "Effect strength",
    effects: { sparkles: "Golden sparks", foxfire: "Kitsune-bi", petals: "Sakura petals", dust: "Golden dust",
               fireflies: "Fireflies", leaves: "Ginkgo leaves", aura: "Golden aura", butterflies: "Butterflies",
               mist: "Golden mist", meteors: "Shooting stars", runes: "Kanji" },
    powers: { low: "Low", normal: "Normal", high: "High" },
    avatarImage: "Look", avatarImageHint: "Effects, glow and motion work with every look.",
    images: { classic: "Classic", welcome: "Embrace", tender: "Tender", prayer: "Prayer", shy: "Shy",
              invite: "Invitation", bow: "Bow", respect: "Respect", sleep: "Sleep" },
    look: "Look and feel", accent: "Colour", cardRadius: "Corners", cardRadiusHint: "Corners of cards and buttons.",
    cardAlpha: "Card transparency",
    scale: "Scale", scaleHint: "Size of text and elements across the app.",
    accents: { honey: "Honey", gold: "Gold", amber: "Amber", bronze: "Bronze", peach: "Peach", coral: "Coral",
               crimson: "Crimson", rose: "Rose", sakura: "Sakura", plum: "Plum", violet: "Violet",
               lavender: "Lavender", indigo: "Indigo", azure: "Azure", sky: "Sky", teal: "Teal", jade: "Jade",
               mint: "Mint", lime: "Lime", silver: "Silver", pearl: "Pearl" },
    radii: { none: "None", small: "Small", normal: "Normal", large: "Large", round: "Round" },
    alphas: { solid: "None", glass: "Glass", clear: "Strong" },
    powerSave: "Power saving", powerSaveHint: "Animations and effects stop while the Yakumo window is inactive.",
    avatarLock: "Lock in place", avatarLockHint: "The avatar can't be dragged; clicking still opens the chat.",
    fxMode: "When to show effects", fxModes: { always: "Always", hover: "On hover" },
    motions: { none: "None", float: "Float", glide: "Gentle float", alive: "Alive" },
    glows: { off: "None", soft: "Soft", bright: "Bright", pulse: "Pulse" },
    speeds: { slow: "Slow", normal: "Normal", fast: "Fast" },
    openBrowser: "Open browser on start",
    openBrowserHint: "This page opens right after Yakumo starts.",
    tray: "Tray icon", trayHint: "Menu near the clock: open, folders, exit.",
    trayMissing: "Requires pystray and Pillow (included in the portable build).",
    autostart: "Start with Windows",
    autostartHint: "Yakumo starts without a console window or browser.",
    autostartMissing: "Windows only.",
    language: "Language", languageHint: "Language of the web version and tray menu.",
    compact: "Compact mode",
    compactHint: "Less spacing, more fits on screen.",
    restart: "Restart Yakumo for this change to take effect.",
    saved: "Saved", saveError: "Not saved",
    avatar: "Yakumo: open chat", chatClose: "Close chat", chatPlaceholder: "Message Yakumo…",
    maximize: "Maximize", restore: "Restore", copy: "Copy", copied: "Copied", retry: "Retry",
    chatKeys: "Enter to send · Shift+Enter for a new line",
    hints: ["Tell me about yourself", "What can you do?", "Name my project", "Explain what an API is in simple words"],
    send: "Send", stop: "Stop", clearChat: "Clear chat", noCloud: "Cloud.ru is not connected",
    greeting: "Hi! I'm Yakumo. Drag me anywhere; click me to open this chat.",
    openSettings: "Open settings", stopped: "(stopped)",
    planTitle: "Here's my plan:", planRun: "Run", planCancel: "Cancel", planRunning: "Running…",
    planDone: (ok, n) => `Done: ${ok} of ${n}`, planCancelled: "Cancelled",
    cloudHint: "Chat with me through Cloud.ru Foundation Models. Get a key in your Cloud.ru console.",
    apiKey: "API key", keySaved: (hint) => `Key saved (${hint}).`, keyNone: "No key saved yet.",
    keyPlaceholder: "Paste your Cloud.ru key", saveKey: "Save", deleteKey: "Delete",
    connection: "Connection check", testConn: "Check", testing: "Checking…",
    connOk: (n) => `Connected, ${n} models available.`, connUnknown: "Not checked yet.",
    model: "Model", modelHint: "The model list appears after a connection check.",
    errors: {
      no_key: "Save your Cloud.ru API key in Settings first.",
      bad_key: "Cloud.ru rejected the key. Check it in Settings.",
      network: "Can't reach Cloud.ru. Check your internet connection.",
      rate_limit: "Too many requests. Wait a moment and try again.",
      bad_model: "This model is unavailable. Pick another one in Settings.",
      no_models: "No models are available for this key.",
    },
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
// Кнопки модулей под ответами Yakumo (Yakumo.addMessageAction), например 👍/👎 «Мозга».
const messageActions = [];
const avatarImg = avatarBtn.querySelector(".av-img");
const avatarBlink = avatarBtn.querySelector(".av-blink");
// Картинки аватара лежат в avatars/: <образ>-<ширина>.webp. Моргание есть только у образов с открытыми глазами,
// для которых сделан кусок с закрытыми глазами (tools/avatar_blink.py).
const AVATAR_WIDTHS = [400, 600, 900, 1254, 1800, 2508];
const BLINKS = new Set(["classic"]);
const chatBox = document.getElementById("chat");
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const statusEl = document.getElementById("status");
let status = null;
let settings = null;
let cloud = null;      // состояние подключения Cloud.ru (без ключа)
let access = null;
let accessMsg = null;
let cloudMsg = null;   // итог последней проверки связи: { text, ok }
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
  document.getElementById("chat-clear").setAttribute("aria-label", T.clearChat);
  document.getElementById("chat-clear").title = T.clearChat;
  showChatSub();
  chatInput.placeholder = T.chatPlaceholder;
  document.getElementById("chat-keys").textContent = T.chatKeys;
  showMaxButton();
  showHints();
  setSending(sending);
}

// --- Внешний вид из настроек ---

function applyLook() {
  const v = settings?.values;
  if (!v) return;
  T = TEXTS[v.language] || TEXTS.ru;
  document.documentElement.lang = v.language;
  document.documentElement.style.setProperty("--scale", v.font_scale / 100);
  document.body.classList.toggle("compact", v.compact);
  Object.assign(document.documentElement.dataset,
    { accent: v.accent, radius: v.card_radius, cards: v.card_alpha });
  applyAvatarLook(v);
  buildMenu();
  placeAvatar();
  showOnline();
}

function applyAvatarLook(v) {
  showAvatarImage(v.avatar_image);
  document.documentElement.style.setProperty("--avatar-size", v.avatar_size + "px");
  Object.assign(avatarBtn.dataset, { motion: v.avatar_motion, glow: v.avatar_glow, speed: v.avatar_speed });
  avatarBtn.hidden = !v.avatar_show;
  avatarBtn.classList.toggle("locked", v.avatar_lock);
  showEffects();
  updatePaused();
  scheduleBlink();
  if (!v.avatar_show && !chatBox.hidden) setChatOpen(false);
}

// Эффекты «при наведении» включаются, пока курсор над аватаром или открыт чат.
let avatarHover = false;
function showEffects() {
  const v = settings.values;
  const on = v.avatar_fx_mode === "always" || avatarHover || !chatBox.hidden ? v.avatar_effects : [];
  avatarBtn.classList.toggle("fx-aura", on.includes("aura"));
  AvatarFx.set(on, v.avatar_fx_power);
}

// Экономия: окно свёрнуто, вкладка скрыта или окно не в фокусе — анимации и эффекты стоят.
function isPaused() {
  return Boolean(settings?.values.power_save) && (document.hidden || !document.hasFocus());
}
function updatePaused() {
  const paused = isPaused();
  avatarBtn.classList.toggle("paused", paused);
  AvatarFx.pause(paused);
}
for (const ev of ["focus", "blur"]) window.addEventListener(ev, () => settings && updatePaused());
document.addEventListener("visibilitychange", () => settings && updatePaused());

function avatarSrc(id, w) { return `avatars/${id}-${w}.webp`; }

function showAvatarImage(id) {
  if (avatarBtn.dataset.image === id) return;
  avatarBtn.dataset.image = id;
  avatarImg.srcset = AVATAR_WIDTHS.map((w) => `${avatarSrc(id, w)} ${w}w`).join(", ");
  avatarImg.src = avatarSrc(id, 600);
  avatarBlink.hidden = !BLINKS.has(id);
  if (BLINKS.has(id)) avatarBlink.src = `avatars/${id}-blink.webp`;
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

function sizeSlider() {
  const opts = settings.options.avatar_size;
  const value = settings.values.avatar_size;
  const out = h("output", {}, `${value} ${T.px}`);
  const input = h("input", {
    type: "range", min: opts[0], max: opts[opts.length - 1], step: opts[1] - opts[0], value,
    "aria-label": T.avatarSize,
    // Пока тянем ползунок, меняем аватар сразу; сохраняем, когда отпустили.
    oninput: (e) => {
      out.textContent = `${e.target.value} ${T.px}`;
      document.documentElement.style.setProperty("--avatar-size", e.target.value + "px");
      placeAvatar();
    },
    onchange: (e) => save({ avatar_size: Number(e.target.value) }),
  });
  return h("div", { class: "row" },
    h("span", { class: "row-text" }, h("span", { class: "row-title" }, T.avatarSize)),
    h("span", { class: "slider" }, input, out));
}

function avatarSection() {
  const on = settings.values.avatar_show;
  return h("section", { class: "card group" },
    h("h2", {}, T.avatarSection),
    toggle("avatar_show", T.avatarShow, T.avatarShowHint),
    on ? [
      imagePicker(),
      toggle("avatar_lock", T.avatarLock, T.avatarLockHint),
      sizeSlider(),
      choice("avatar_motion", T.avatarMotion, null, (v) => T.motions[v]),
      choice("avatar_glow", T.avatarGlow, null, (v) => T.glows[v]),
      choice("avatar_speed", T.avatarSpeed, null, (v) => T.speeds[v]),
      effectChips(),
      choice("avatar_fx_power", T.fxPower, null, (v) => T.powers[v]),
      choice("avatar_fx_mode", T.fxMode, null, (v) => T.fxModes[v]),
    ] : []);
}

function accentPicker() {
  const current = settings.values.accent;
  return h("div", { class: "row" },
    h("span", { class: "row-text" }, h("span", { class: "row-title" }, T.accent),
      h("span", { class: "row-hint" }, T.accents[current])),
    h("span", { class: "swatches", role: "radiogroup", "aria-label": T.accent },
      settings.options.accent.map((id) => h("button", {
        type: "button", role: "radio", "aria-checked": String(id === current), "data-accent": id,
        title: T.accents[id], "aria-label": T.accents[id], onclick: () => id !== current && save({ accent: id }),
      }))));
}

function imagePicker() {
  const current = settings.values.avatar_image;
  return h("div", { class: "row row-wide" },
    h("span", { class: "row-text" }, h("span", { class: "row-title" }, T.avatarImage),
      h("span", { class: "row-hint" }, T.avatarImageHint)),
    h("span", { class: "looks", role: "radiogroup", "aria-label": T.avatarImage },
      settings.options.avatar_image.map((id) => h("button", {
        type: "button", role: "radio", "aria-checked": String(id === current), class: id === current ? "on" : "",
        title: T.images[id], onclick: () => id !== current && save({ avatar_image: id }),
      }, h("img", { src: `avatars/${id}-thumb.webp`, alt: "", width: 96, height: 96, loading: "lazy", draggable: "false" }),
        h("span", {}, T.images[id])))));
}

function effectChips() {
  const on = settings.values.avatar_effects;
  const flip = (fx) => save({ avatar_effects: settings.options.avatar_effects
    .filter((k) => (k === fx ? !on.includes(k) : on.includes(k))) });
  return h("div", { class: "row" },
    h("span", { class: "row-text" }, h("span", { class: "row-title" }, T.avatarEffects),
      h("span", { class: "row-hint" }, T.avatarEffectsHint)),
    h("span", { class: "chips", role: "group", "aria-label": T.avatarEffects },
      settings.options.avatar_effects.map((fx) => h("button", {
        type: "button", "aria-pressed": String(on.includes(fx)), onclick: () => flip(fx) }, T.effects[fx]))));
}

function accessSection() {
  const box = h("section", { class: "card group", id: "network-access" }, h("h2", {}, T.networkAccess),
    h("p", { class: "row-hint group-hint" }, T.accessHint));
  if (!access) return box;
  box.append(h("p", { class: "row-hint" }, access.password_set ? T.accessOpen : T.accessClosed));
  if (access.local) {
    const input = h("input", { type: "password", class: "text-input", placeholder: T.accessPlaceholder,
      autocomplete: "new-password", minlength: "8", maxlength: "128", required: true, "aria-label": T.accessPassword });
    const form = h("form", { class: "inline-form", onsubmit: (e) => {
      e.preventDefault();
      if (form.reportValidity()) saveAccess(input.value, form);
    } }, input, h("button", { class: "btn primary", type: "submit" }, T.accessSave));
    box.append(form);
    if (access.password_set) box.append(h("button", { class: "btn", type: "button",
      onclick: (e) => saveAccess("", e.currentTarget) }, T.accessClose));
  } else {
    box.append(h("p", { class: "row-hint" }, T.accessLocalOnly),
      h("button", { class: "btn", type: "button", onclick: async () => {
        await postJSON("/api/auth/logout", {});
        location.assign("/login");
      } }, T.accessLogout));
  }
  if (accessMsg) box.append(h("p", { class: "row-hint " + (accessMsg.ok ? "good" : "bad"), role: "status" }, accessMsg.text));
  return box;
}

async function saveAccess(password, source) {
  const buttons = source.matches("button") ? [source] : [...source.querySelectorAll("button")];
  buttons.forEach((b) => { b.disabled = true; });
  try {
    access = await postJSON("/api/auth/password", { password });
    accessMsg = { ok: true, text: T.accessSaved };
  } catch (e) {
    accessMsg = { ok: false, text: e.message };
  } finally {
    buttons.forEach((b) => { b.disabled = false; });
  }
  if (currentPage() === "settings") render();
}

function cloudSection() {
  const box = h("section", { class: "card group", id: "cloud" }, h("h2", {}, "Cloud.ru"),
    h("p", { class: "row-hint group-hint" }, T.cloudHint));
  if (!cloud) return box;
  const input = h("input", { type: "password", class: "text-input", placeholder: T.keyPlaceholder,
                             autocomplete: "off", spellcheck: "false", "aria-label": T.apiKey });
  const keyForm = h("form", { class: "inline-form", onsubmit: (e) => {
    e.preventDefault();
    if (input.value.trim()) saveCloud({ api_key: input.value.trim() }, true);
  } }, input, h("button", { class: "btn primary", type: "submit" }, T.saveKey),
    cloud.has_key ? h("button", { class: "btn", type: "button",
                                 onclick: () => { cloudMsg = null; saveCloud({ api_key: "" }); } }, T.deleteKey) : "");
  const models = cloud.models.length ? cloud.models : (cloud.model ? [cloud.model] : []);
  const select = h("select", { class: "select", "aria-label": T.model, disabled: !models.length,
                               onchange: (e) => saveCloud({ model: e.target.value }) },
    models.map((m) => h("option", { value: m, selected: m === cloud.model }, m)));
  const msg = cloudMsg || { text: T.connUnknown };
  box.append(
    h("div", { class: "row" },
      h("span", { class: "row-text" }, h("span", { class: "row-title" }, T.apiKey),
        h("span", { class: "row-hint" }, cloud.has_key ? T.keySaved(cloud.key_hint) : T.keyNone)),
      keyForm),
    h("div", { class: "row" },
      h("span", { class: "row-text" }, h("span", { class: "row-title" }, T.connection),
        h("span", { class: "row-hint " + (msg.ok === true ? "good" : msg.ok === false ? "bad" : ""), id: "cloud-msg" },
          msg.text)),
      h("button", { class: "btn", type: "button", disabled: !cloud.has_key, onclick: () => testCloud() }, T.testConn)),
    h("div", { class: "row" },
      h("span", { class: "row-text" }, h("span", { class: "row-title" }, T.model),
        h("span", { class: "row-hint" }, T.modelHint)),
      select));
  return box;
}

async function postJSON(url, data) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
                               body: JSON.stringify(data) });
  if (r.status === 401) location.assign("/login");
  const res = await r.json();
  if (!r.ok) throw new Error(res.error || `HTTP ${r.status}`);
  return res;
}

function errorText(code) { return T.errors[code] || code; }

async function saveCloud(changes, thenTest = false) {
  try {
    cloud = await postJSON("/api/cloud", changes);
    if (thenTest) return testCloud();
  } catch (e) {
    cloudMsg = { text: `${T.saveError}: ${e.message}`, ok: false };
  }
  showChatSub();
  if (currentPage() === "settings") render();
}

async function testCloud() {
  const el = document.getElementById("cloud-msg");
  if (el) { el.textContent = T.testing; el.className = "row-hint"; }
  try {
    const res = await postJSON("/api/cloud/test", {});
    cloud = res;
    cloudMsg = res.ok ? { text: T.connOk(res.models.length), ok: true } : { text: errorText(res.error), ok: false };
  } catch (e) {
    cloudMsg = { text: e.message, ok: false };
  }
  showChatSub();
  if (currentPage() === "settings") render();
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
        toggle("compact", T.compact, T.compactHint)),
      h("section", { class: "card group" },
        h("h2", {}, T.look),
        accentPicker(),
        choice("font_scale", T.scale, T.scaleHint, (v) => `${v}%`),
        choice("card_radius", T.cardRadius, T.cardRadiusHint, (v) => T.radii[v]),
        choice("card_alpha", T.cardAlpha, null, (v) => T.alphas[v]),
        toggle("power_save", T.powerSave, T.powerSaveHint)),
      avatarSection(),
      accessSection(),
      cloudSection(),
      h("section", { class: "card group" },
        h("h2", {}, T.paths),
        h("table", { class: "kv" }, paths.map(([k, v]) => h("tr", {}, h("td", {}, T.pathNames[k] || k), h("td", {}, v))))),
    ];
  },
};

// --- Страницы модулей ---
// Модуль подключает свой скрипт (ctx.web в Python), а скрипт добавляет раздел в верхнее меню:
//   Yakumo.addPage({ id, icon: "<path …/>", title: { ru, en }, render: () => [элементы] })

window.Yakumo = {
  h, icon, getJSON, postJSON,
  lang: () => settings?.values.language || "ru",
  status: () => status,
  rerender: () => render(),
  // Yakumo пишет первой (утреннее сообщение, напоминание): реплика в чат и золотая точка на аватаре.
  say(text) {
    addMessage("bot", text, { from_memory: true });
    if (chatBox.hidden) avatarBtn.classList.add("news");
  },
  // Открыть чат и сразу спросить Yakumo (например, «Спросить Yakumo» о файле на Диске).
  ask(text) {
    setChatOpen(true);
    if (sending || !text?.trim()) return;
    addMessage("me", text.trim());
    ask();
  },
  // fn(m, { question, chatId, save }) → элемент или null; m — реплика Yakumo, в ней можно хранить своё (m.rated).
  addMessageAction(fn) {
    messageActions.push(fn);
    showMessages();
  },
  addPage({ id, icon: svg, title, render: draw }) {
    if (PAGES[id]) return;
    const sym = document.createElementNS("http://www.w3.org/2000/svg", "symbol");
    sym.id = "i-" + id;
    sym.setAttribute("viewBox", "0 0 24 24");
    sym.innerHTML = svg;
    document.querySelector("svg symbol").parentNode.append(sym);
    for (const [lang, texts] of Object.entries(TEXTS)) texts[id] = title[lang] || title.ru;
    SECTIONS.push({ id, icon: sym.id });
    PAGES[id] = draw;
    buildMenu();
    render();
  },
};

async function loadModulePages() {
  let modules = [];
  try { modules = await getJSON("/api/modules"); } catch { return; }
  for (const url of modules.flatMap((m) => m.web || [])) {
    if (url.endsWith(".css")) document.head.append(h("link", { rel: "stylesheet", href: url }));
    else document.body.append(h("script", { src: url }));
  }
}

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
  document.body.dataset.page = page;
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
  if (r.status === 401) location.assign("/login");
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
  try {
    access = await getJSON("/api/auth");
  } catch { /* при следующем открытии настройки доступа загрузятся заново */ }
  avatarBtn.classList.add("ready");
  placeAvatar();
  loadModulePages();
  try {
    cloud = await getJSON("/api/cloud");
    showChatSub();
  } catch { /* чат покажет ошибку при отправке */ }
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
// Id беседы: по нему память Yakumo отличает один разговор от другого. Новый — после очистки чата.
const newChatId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
let chatId = stored("yakumo.chatId", null) || newChatId();
store("yakumo.chatId", chatId);

// Страница масштабируется через zoom, поэтому размеры окна переводим в CSS-пиксели страницы.
function zoom() { return (settings?.values.font_scale || 100) / 100; }
function viewport() { return { w: innerWidth / zoom(), h: innerHeight / zoom() }; }
function margins() { return { top: document.querySelector(".topbar").offsetHeight + 4, side: 8 }; }

function placeAvatar() {
  const { w, h } = viewport(), m = margins(), size = avatarBtn.offsetWidth;
  // Подсказка браузеру, какой из размеров картинки брать: с учётом масштаба страницы.
  avatarImg.sizes = Math.round(size * zoom()) + "px";
  AvatarFx.resize(zoom());
  const free = { x: Math.max(0, w - size - 2 * m.side), y: Math.max(0, h - size - m.top - m.side) };
  avatarBtn.style.left = m.side + avatarPos.x * free.x + "px";
  avatarBtn.style.top = m.top + avatarPos.y * free.y + "px";
  if (!chatBox.hidden) placeChat();
}

// Размер окна чата задаёт пользователь (растягивая за края); храним в браузере.
let chatSize = stored("yakumo.chatSize", { w: 420, h: 600 });
let chatMax = stored("yakumo.chatMax", false);
const CHAT_MIN = { w: 300, h: 320 };

// Чат рядом с аватаром: слева или справа, если хватает места, иначе над или под ним.
function placeChat() {
  const { w, h } = viewport(), m = margins(), gap = 10;
  chatBox.classList.toggle("max", chatMax);
  if (chatMax) {
    Object.assign(chatBox.style, { left: m.side + "px", top: m.top + "px",
                                   width: w - 2 * m.side + "px", height: h - m.top - m.side + "px" });
    return;
  }
  const a = { x: avatarBtn.offsetLeft, y: avatarBtn.offsetTop, s: avatarBtn.offsetWidth };
  const cw = Math.max(Math.min(chatSize.w, w - 2 * m.side), Math.min(CHAT_MIN.w, w - 2 * m.side));
  let ch = Math.max(Math.min(chatSize.h, h - m.top - m.side), Math.min(CHAT_MIN.h, h - m.top - m.side)), x, y;
  const clampX = (v) => Math.min(Math.max(v, m.side), w - cw - m.side);
  const clampY = (v) => Math.min(Math.max(v, m.top), h - ch - m.side);
  if (avatarBtn.hidden) {
    x = w - cw - m.side * 3; y = clampY(h - ch - m.side * 3);
  } else if (a.x - gap - cw >= m.side || a.x + a.s + gap + cw <= w - m.side) {
    x = a.x - gap - cw >= m.side ? a.x - gap - cw : a.x + a.s + gap;
    y = clampY(a.y + a.s - ch);
  } else {
    const above = a.y - gap - m.top, below = h - m.side - (a.y + a.s + gap);
    ch = Math.min(ch, Math.max(above, below, CHAT_MIN.h));
    x = clampX(a.x + a.s / 2 - cw / 2);
    y = above >= below ? clampY(a.y - gap - ch) : clampY(a.y + a.s + gap);
  }
  Object.assign(chatBox.style, { left: x + "px", top: y + "px", width: cw + "px", height: ch + "px" });
}

function showMaxButton() {
  const btn = document.getElementById("chat-max");
  btn.setAttribute("aria-label", chatMax ? T.restore : T.maximize);
  btn.title = chatMax ? T.restore : T.maximize;
  btn.querySelector("use").setAttribute("href", chatMax ? "#i-min" : "#i-max");
}

document.getElementById("chat-max").addEventListener("click", () => {
  chatMax = !chatMax;
  store("yakumo.chatMax", chatMax);
  showMaxButton();
  placeChat();
});

// Растягивание за края и углы. Противоположный край стоит на месте.
let resize = null;
for (const grip of chatBox.querySelectorAll(".grip")) {
  grip.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || chatMax) return;
    e.preventDefault();
    grip.setPointerCapture(e.pointerId);
    resize = { edge: grip.dataset.edge, x: e.clientX, y: e.clientY, left: chatBox.offsetLeft, top: chatBox.offsetTop,
               w: chatBox.offsetWidth, h: chatBox.offsetHeight };
    chatBox.classList.add("resizing");
  });
  grip.addEventListener("pointermove", (e) => {
    if (!resize) return;
    const { w, h } = viewport(), m = margins(), r = resize;
    const dx = (e.clientX - r.x) / zoom(), dy = (e.clientY - r.y) / zoom();
    let { left, top, w: cw, h: ch } = r;
    if (r.edge.includes("e")) cw = Math.min(Math.max(r.w + dx, CHAT_MIN.w), w - m.side - left);
    if (r.edge.includes("s")) ch = Math.min(Math.max(r.h + dy, CHAT_MIN.h), h - m.side - top);
    if (r.edge.includes("w")) {
      cw = Math.min(Math.max(r.w - dx, CHAT_MIN.w), r.left + r.w - m.side);
      left = r.left + r.w - cw;
    }
    if (r.edge.includes("n")) {
      ch = Math.min(Math.max(r.h - dy, CHAT_MIN.h), r.top + r.h - m.top);
      top = r.top + r.h - ch;
    }
    Object.assign(chatBox.style, { left: left + "px", top: top + "px", width: cw + "px", height: ch + "px" });
  });
  const end = () => {
    if (!resize) return;
    resize = null;
    chatBox.classList.remove("resizing");
    chatSize = { w: chatBox.offsetWidth, h: chatBox.offsetHeight };
    store("yakumo.chatSize", chatSize);
  };
  grip.addEventListener("pointerup", end);
  grip.addEventListener("pointercancel", end);
}

function setChatOpen(open) {
  chatBox.hidden = !open;
  avatarBtn.setAttribute("aria-expanded", String(open));
  if (settings) showEffects();
  if (!open) return;
  avatarBtn.classList.remove("news");
  if (!messages.length) addMessage("bot", T.greeting, { local: true });
  placeChat();
  chatInput.focus();
}

function showChatSub() {
  const model = cloud?.has_key && cloud.model ? cloud.model.split("/").pop() : null;
  document.getElementById("chat-sub").textContent = model || T.noCloud;
  document.getElementById("chat-dot").classList.toggle("on", !!model);
}

// Подсказки-вопросы, пока разговор не начат.
function showHints() {
  const box = document.getElementById("chat-hints");
  const started = messages.some((m) => m.from === "me");
  box.replaceChildren(...(started ? [] : T.hints.map((text) => h("button", { type: "button",
    onclick: () => { chatInput.value = text; chatForm.requestSubmit(chatForm.querySelector(".chat-send")); } }, text))));
}

// Рассуждения моделей в <think>…</think> пользователю не показываем и обратно не отправляем.
function visible(text) {
  return text.replace(/<think>[\s\S]*?(<\/think>|$)/g, "").replace(/^\s+/, "");
}

async function copyText(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {  // не через localhost: буфер обмена недоступен, копируем по-старому
    const area = h("textarea", { style: "position:fixed;opacity:0" }, text);
    document.body.append(area); area.select(); document.execCommand("copy"); area.remove();
  }
  btn.classList.add("done"); btn.title = T.copied;
  setTimeout(() => { btn.classList.remove("done"); btn.title = T.copy; }, 1500);
}

function timeLabel(at) {
  return at ? new Date(at).toLocaleTimeString(document.documentElement.lang, { hour: "2-digit", minute: "2-digit" }) : "";
}

// Короткий безопасный Markdown: сначала экранируем всё, потом размечаем.
function escapeHTML(text) {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function inlineMd(text) {
  return text
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>")
    .replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    // Ссылки на файлы «Диска» из ответов Yakumo: [имя](disk:путь) — открывает модуль Диск.
    .replace(/\[([^\]\n]+)\]\(disk:([^)\n]*)\)/g, '<a href="#/disk" class="disk-link" data-path="$2">$1</a>');
}

function markdown(text) {
  const out = [];
  const parts = escapeHTML(text).split(/```/);
  parts.forEach((part, i) => {
    if (i % 2) {  // блок кода; первая строка может быть названием языка
      out.push(`<pre><code>${part.replace(/^[\w+-]*\n/, "")}</code></pre>`);
      return;
    }
    let list = null;
    for (const raw of part.split("\n")) {
      const item = raw.match(/^\s*(?:[-*•]|(\d+)[.)])\s+(.*)$/);
      if (item) {
        const tag = item[1] ? "ol" : "ul";
        if (list !== tag) { if (list) out.push(`</${list}>`); out.push(`<${tag}>`); list = tag; }
        out.push(`<li>${inlineMd(item[2])}</li>`);
        continue;
      }
      if (list) { out.push(`</${list}>`); list = null; }
      const head = raw.match(/^#{1,6}\s+(.*)$/);
      if (head) out.push(`<p><strong>${inlineMd(head[1])}</strong></p>`);
      else if (raw.trim()) out.push(`<p>${inlineMd(raw)}</p>`);
    }
    if (list) out.push(`</${list}>`);
  });
  return out.join("");
}

function messageEl(m) {
  const bubble = h("div", { class: `msg ${m.from}${m.error ? " error" : ""}` });
  const text = m.from === "bot" ? visible(m.text) : m.text;
  if (m.from === "bot" && !m.error) bubble.innerHTML = markdown(text) || "<span class=\"typing\"><i></i><i></i><i></i></span>";
  else bubble.textContent = m.error ? errorText(m.error) : text;
  if (m.from === "bot" && !m.error && !text && !m.pending && m.cards) bubble.hidden = true;  // ответ — только план
  if (m.pending && m.status) bubble.append(h("div", { class: "msg-status" }, m.status));
  if (m.error === "no_key" || m.error === "bad_key" || m.error === "bad_model") {
    bubble.append(h("button", { class: "btn small", type: "button",
                                onclick: () => { location.hash = "#/settings"; } }, T.openSettings));
  }
  const meta = h("div", { class: "msg-meta" }, timeLabel(m.at));
  if (m.error && !sending && m === messages[messages.length - 1]) {
    meta.append(iconButton("i-retry", T.retry, () => retry(m)));
    meta.lastChild.style.opacity = 1;
  } else if (!m.pending && !m.error && text) {
    meta.append(iconButton("i-copy", T.copy, (e) => copyText(text, e.currentTarget)));
    if (m.from === "bot" && !m.local && !m.from_memory) {
      const i = messages.indexOf(m);
      const question = messages.slice(0, i).reverse().find((x) => x.from === "me")?.text || "";
      const save = () => { saveMessages(); showMessages(); };
      for (const action of messageActions) {
        try { const el = action(m, { question, chatId, save }); if (el) meta.append(el); } catch { /* модуль ошибся — без кнопки */ }
      }
    }
  }
  const col = h("div", { class: "msg-col" }, bubble, (m.cards || []).map((c) => cardEl(c, m)), meta);
  if (m.from === "me") return h("div", { class: "msg-row me" }, col);
  return h("div", { class: "msg-row bot" }, h("img", { class: "msg-face", src: "avatar-face.webp", alt: "" }), col);
}

// Карточки под ответом. План: Yakumo предлагает изменения, они выполняются только по кнопке.
function cardEl(card, m) {
  if (card.type !== "plan") return "";
  const box = h("div", { class: "plan-card" }, h("strong", {}, T.planTitle),
    h("ol", {}, card.actions.map((a, i) => {
      const r = card.results?.[i];
      return h("li", { class: r ? (r.ok ? "ok" : "bad") : "" }, a.title, r && !r.ok ? h("small", {}, r.error) : "");
    })));
  if (card.state === "done") {
    const ok = card.results.filter((r) => r.ok).length;
    box.append(h("div", { class: "plan-state" }, T.planDone(ok, card.results.length)));
  } else if (card.state === "cancelled") {
    box.append(h("div", { class: "plan-state" }, T.planCancelled));
  } else {
    const run = h("button", { class: "btn primary small", type: "button", disabled: card.state === "running",
      onclick: () => runPlan(card) }, card.state === "running" ? T.planRunning : T.planRun);
    const cancel = h("button", { class: "btn small", type: "button", disabled: card.state === "running",
      onclick: () => { card.state = "cancelled"; saveMessages(); showMessages(); } }, T.planCancel);
    box.append(h("div", { class: "plan-actions" }, run, cancel));
  }
  return box;
}

async function runPlan(card) {
  card.state = "running";
  showMessages();
  try {
    const res = await postJSON("/api/chat/apply", { actions: card.actions.map(({ tool, args }) => ({ tool, args })) });
    card.results = res.results;
    card.state = "done";
  } catch (e) {
    card.results = card.actions.map(() => ({ ok: false, error: e.message }));
    card.state = "done";
  }
  saveMessages();
  showMessages();
  window.dispatchEvent(new CustomEvent("yakumo:files-changed"));  // открытые страницы модулей обновятся
}

function iconButton(id, label, onclick) {
  const b = h("button", { type: "button", title: label, "aria-label": label, onclick });
  b.append(icon(id));
  return b;
}

function retry(errorMessage) {
  messages = messages.filter((m) => m !== errorMessage);
  saveMessages();
  showMessages();
  ask();
}

function showMessages() {
  chatLog.replaceChildren(...messages.map(messageEl));
  chatLog.scrollTop = chatLog.scrollHeight;
  showHints();
}

function saveMessages() {
  messages = messages.slice(-200);
  store("yakumo.chat", messages.filter((m) => !m.pending));
}

function addMessage(from, text, extra = {}) {
  const m = { from, text, at: Date.now(), ...extra };
  messages = [...messages, m];
  saveMessages();
  showMessages();
  return m;
}

// Что отправить модели: настоящие реплики, без приветствия и ошибок.
function chatHistory() {
  const list = messages.filter((m) => !m.error && !m.local && !m.pending && visible(m.text))
    .map((m) => ({ role: m.from === "me" ? "user" : "assistant", content: m.from === "me" ? m.text : visible(m.text) }));
  const first = list.findIndex((m) => m.role === "user");  // разговор начинается с пользователя
  return first < 0 ? [] : list.slice(first);
}

let sending = null;  // AbortController текущего ответа

function setSending(controller) {
  sending = controller;
  const btn = chatForm.querySelector(".chat-send");
  btn.classList.toggle("stop", !!controller);
  btn.setAttribute("aria-label", controller ? T.stop : T.send);
  btn.querySelector("use").setAttribute("href", controller ? "#i-stop" : "#i-send");
}

async function ask() {
  const controller = new AbortController();
  setSending(controller);
  const answer = addMessage("bot", "", { pending: true });
  // Перерисовываем ответ не чаще кадра; если чат очистили, старый ответ больше не показываем.
  let drawn = 0;
  const update = () => {
    if (drawn) return;
    drawn = requestAnimationFrame(() => {
      drawn = 0;
      if (!messages.includes(answer)) return;
      const nearBottom = chatLog.scrollHeight - chatLog.scrollTop - chatLog.clientHeight < 80;
      chatLog.lastElementChild?.replaceWith(messageEl(answer));
      if (nearBottom) chatLog.scrollTop = chatLog.scrollHeight;
    });
  };
  try {
    const r = await fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: chatHistory(), chat_id: chatId }), signal: controller.signal,
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `HTTP ${r.status}`);
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        const ev = JSON.parse(line);
        if (ev.delta) { answer.text += ev.delta; update(); }
        if (ev.status) { answer.status = ev.status; update(); }
        if (ev.card) { (answer.cards ||= []).push(ev.card); update(); }
        if (ev.error) { if (answer.text) answer.text += "\n\n"; answer.error = ev.error; }
      }
    }
    if (!answer.text && !answer.error && !answer.cards) answer.error = "network";
  } catch (e) {
    if (e.name === "AbortError") answer.text += (answer.text ? " " : "") + T.stopped;
    else answer.error = e instanceof TypeError ? "network" : e.message;
  }
  cancelAnimationFrame(drawn);
  setSending(null);
  if (!messages.includes(answer)) return;  // чат очистили во время ответа
  // Ошибку после части ответа показываем отдельной репликой, а начало ответа оставляем.
  delete answer.pending;
  delete answer.status;
  if (answer.error && answer.text.trim()) {
    const error = answer.error;
    delete answer.error;
    answer.text = answer.text.trim();
    messages.push({ from: "bot", text: "", error, at: Date.now() });
  }
  saveMessages();
  showMessages();
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  // Во время ответа Enter ничего не делает, а кнопка останавливает ответ.
  if (sending) { if (e.submitter) sending.abort(); return; }
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = "";
  chatInput.style.height = "";
  showCount();
  addMessage("me", text);
  ask();
});
document.getElementById("chat-clear").addEventListener("click", () => {
  if (sending) sending.abort();
  messages = [];
  chatId = newChatId();
  store("yakumo.chatId", chatId);
  addMessage("bot", T.greeting, { local: true });
  chatInput.focus();
});
chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); chatForm.requestSubmit(); }
});
chatBox.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { setChatOpen(false); avatarBtn.focus(); }
});
function showCount() {
  const n = chatInput.value.length, el = document.getElementById("chat-count");
  el.textContent = n > 3000 ? `${n} / 4000` : "";
  el.className = n >= 4000 ? "over" : "";
}
chatInput.addEventListener("input", () => {
  chatInput.style.height = "";
  chatInput.style.height = chatInput.scrollHeight + "px";
  showCount();
});
document.getElementById("chat-close").addEventListener("click", () => { setChatOpen(false); avatarBtn.focus(); });

// Перетаскивание: короткое нажатие без сдвига открывает чат, сдвиг больше 5 точек двигает аватар.
let drag = null;
avatarBtn.addEventListener("pointerdown", (e) => {
  if (e.button !== 0) return;
  if (settings?.values.avatar_lock) { justDragged = false; return; }
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
for (const [ev, on] of [["pointerenter", true], ["pointerleave", false]]) {
  avatarBtn.addEventListener(ev, () => {
    avatarHover = on;
    if (settings?.values.avatar_fx_mode === "hover") showEffects();
  });
}
avatarBtn.addEventListener("pointercancel", endDrag);
avatarBtn.addEventListener("click", () => {
  // После перетаскивания браузер всё равно присылает click, его пропускаем.
  if (justDragged) { justDragged = false; return; }
  react();
  setChatOpen(chatBox.hidden);
});

// «Живая»: аватар слегка поворачивается в сторону курсора.
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
let lookFrame = 0;
function lookAt(x, y) {
  if (avatarBtn.dataset.motion !== "alive" || drag || reducedMotion.matches) return;
  cancelAnimationFrame(lookFrame);
  lookFrame = requestAnimationFrame(() => {
    const r = avatarBtn.getBoundingClientRect();
    const reach = Math.max(innerWidth, innerHeight) / 2;
    const dx = Math.max(-1, Math.min(1, (x - (r.left + r.width / 2)) / reach));
    const dy = Math.max(-1, Math.min(1, (y - (r.top + r.height / 2)) / reach));
    avatarBtn.style.setProperty("--ry", (dx * 9).toFixed(2) + "deg");
    avatarBtn.style.setProperty("--rx", (-dy * 6).toFixed(2) + "deg");
    // Курсор совсем рядом: она оживляется и слегка тянется навстречу.
    const near = Math.hypot(x - (r.left + r.width / 2), y - (r.top + r.height / 2)) < r.width * 0.75;
    avatarBtn.classList.toggle("near", near);
  });
}
function lookAway() {
  avatarBtn.style.removeProperty("--rx");
  avatarBtn.style.removeProperty("--ry");
  avatarBtn.classList.remove("near");
}

// Моргание в случайные моменты, иногда дважды подряд, как у живых.
let blinkTimer = 0;
function scheduleBlink() {
  clearTimeout(blinkTimer);
  if (avatarBtn.dataset.motion !== "alive" || reducedMotion.matches) return;
  blinkTimer = setTimeout(() => {
    if (!document.hidden && !avatarBtn.hidden && !isPaused()) {
      blinkOnce();
      if (Math.random() < 0.2) setTimeout(blinkOnce, 260);
    }
    scheduleBlink();
  }, 2500 + Math.random() * 4500);
}
function blinkOnce() {
  if (avatarBlink.hidden) return;
  avatarBtn.classList.add("blink");
  setTimeout(() => avatarBtn.classList.remove("blink"), 130);
}

// Ответ на нажатие: подскок, моргание и россыпь искр, если включены эффекты.
function react() {
  if (reducedMotion.matches) return;
  avatarBtn.classList.remove("hop");
  void avatarBtn.offsetWidth;  // перезапуск анимации
  avatarBtn.classList.add("hop");
  setTimeout(() => avatarBtn.classList.remove("hop"), 800);
  if (avatarBtn.dataset.motion === "alive") blinkOnce();
  if (settings?.values.avatar_effects.length) AvatarFx.burst();
}
window.addEventListener("pointermove", (e) => { if (e.pointerType === "mouse") lookAt(e.clientX, e.clientY); });
document.documentElement.addEventListener("pointerleave", lookAway);
window.addEventListener("blur", lookAway);

AvatarFx.init(avatarBtn);
window.addEventListener("resize", placeAvatar);
window.addEventListener("hashchange", render);
showMessages();
placeAvatar();
start();
