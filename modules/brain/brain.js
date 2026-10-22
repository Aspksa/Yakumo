"use strict";

// «Память»: что Yakumo помнит о пользователе — факты, карта людей и мест, разговоры, обещания, даты и навыки.
// Страница подключается через Yakumo.addPage. Ещё скрипт забирает сообщения, которые Yakumo пишет первой.
(() => {
  const { h, getJSON, postJSON } = window.Yakumo;
  const SVG = "http://www.w3.org/2000/svg";

  const TX = {
    ru: {
      title: "Память", facts: "Факты", map: "Карта", talks: "Разговоры", plans: "Обещания и даты", skills: "Навыки",
      lead: (f, t) => `Yakumo помнит ${f} ${plural(f, "факт", "факта", "фактов")} о вас и ${t} ${plural(t, "разговор", "разговора", "разговоров")}.`,
      enabled: "Помнить в чате", enabledHint: "Yakumo видит свою память в каждом новом разговоре.",
      auto: "Запоминать самой", autoHint: "После паузы в разговоре Yakumo выписывает факты, людей и места, обещания и даты. Для этого текст разговора ещё раз отправляется в Cloud.ru.",
      sleep: "Сон кицунэ", sleepHint: "Раз в сутки, когда в чате тихо, Yakumo наводит порядок в памяти, а утром пишет первой: что ей «приснилось», о чём не забыть, как успехи с целями.",
      mood: "Замечать настроение", moodHint: "Yakumo отмечает, как вы себя чувствуете в разговорах, и бережнее говорит, если несколько дней было тяжело. Хранится только у вас.",
      activity: "Видеть, что открыто на компьютере", activityHint: "Раз в минуту Yakumo смотрит, какая программа на экране, чтобы помогать к месту. Заголовки окон не сохраняются, только минуты по программам за день.",
      activityNo: "Работает только в Windows.",
      noCloud: "Чтобы Yakumo запоминала сама, спала и искала по смыслу, подключите Cloud.ru в настройках.",
      busy: "Думаю над последним разговором…", lastError: (e) => `Не получилось разобрать разговор: ${e}`,
      semantic: (m, n) => `Поиск по смыслу: ${m}, векторов ${n}.`, semanticOff: "Поиск по смыслу: в каталоге Cloud.ru нет модели эмбеддингов, ищу по словам.",
      sleepNow: "Уснуть сейчас", sleeping: "Сплю…", lastSleep: (d) => `Последний сон: ${d}.`, noMorning: "Утром рассказать нечего — память пока пуста.",
      tip: "В чате можно сказать: «запомни, что я пью чай без сахара», «откуда ты это знаешь?», «напомни в пятницу сдать отчёт», «запомни, как я делаю недельный отчёт», «помнишь, о чём мы говорили на прошлой неделе?»",
      addPlaceholder: "Например: мою сестру зовут Аня, она живёт в Казани", add: "Запомнить",
      search: "Поиск по памяти", nothing: "Ничего не нашлось",
      kinds: { person: "О вас", likes: "Вкусы и привычки", work: "Дела и планы", other: "Разное", self: "О Yakumo и вас" },
      types: { person: "Человек", pet: "Питомец", place: "Место", project: "Проект", org: "Организация", thing: "Прочее" },
      you: "Вы", sources: { auto: "запомнила сама", chat: "вы попросили", manual: "добавлено вручную", module: "из модуля" },
      from: "Откуда", quote: (q) => `«${q}»`,
      emptyFacts: "Пока ничего не запомнено", emptyFactsHint: "Поговорите с Yakumo или добавьте факт сами.",
      emptyMap: "Карта пуста", emptyMapHint: "Когда Yakumo узнает о ваших близких, питомцах, местах и проектах, они появятся здесь.",
      emptyTalks: "Разговоров пока нет", emptyTalksHint: "Конспект появится через полминуты после разговора в чате.",
      emptyPlans: "Обещаний и дат пока нет", emptyPlansHint: "Скажите в чате: «напомни в пятницу сдать отчёт» или «у мамы день рождения 12 марта».",
      emptySkills: "Навыков пока нет", emptySkillsHint: "Объясните Yakumo в чате, как вы что-то делаете, и попросите запомнить. Потом скажите «сделай недельный отчёт».",
      pin: "Закрепить: всегда помнить", unpin: "Открепить", edit: "Изменить", del: "Забыть", save: "Сохранить",
      cancel: "Отмена", strength: (s) => `Сила памяти: ${s}`, faded: "тускнеет",
      messages: (n) => `${n} ${plural(n, "реплика", "реплики", "реплик")}`,
      exp: "Экспорт", imp: "Импорт", clear: "Забыть всё",
      clearAsk: "Забыть всё: факты, разговоры, обещания, даты и навыки? Вернуть можно будет только из файла экспорта.",
      imported: (f, t) => `Добавлено: фактов ${f}, разговоров ${t}`, error: "Ошибка",
      promisesUser: "Вы обещали", promisesYakumo: "Yakumo обещала", dates: "Даты", done: "Выполнено", due: (d) => `до ${d}`,
      overdue: "просрочено", yearly: "каждый год", addPromise: "Новое обещание", addDate: "Новая дата",
      who: { user: "Обещаю я", yakumo: "Напомнить мне" }, upcoming: "Скоро",
      inDays: (n) => (n < 0 ? "просрочено" : n === 0 ? "сегодня" : n === 1 ? "завтра" : `через ${n} дн.`),
      steps: (n) => `${n} ${plural(n, "шаг", "шага", "шагов")}`, used: (n) => `использован ${n} ${plural(n, "раз", "раза", "раз")}`,
      moodTitle: "Настроение за месяц", factsAbout: (n) => `Фактов: ${n}`, relation: "Кем приходится", rename: "Имя",
      openFile: "Открыть на Диске",
    },
    en: {
      title: "Memory", facts: "Facts", map: "Map", talks: "Conversations", plans: "Promises & dates", skills: "Skills",
      lead: (f, t) => `Yakumo remembers ${f} ${f === 1 ? "fact" : "facts"} about you and ${t} ${t === 1 ? "conversation" : "conversations"}.`,
      enabled: "Use memory in chat", enabledHint: "Yakumo sees her memory in every new conversation.",
      auto: "Learn by herself", autoHint: "After a pause Yakumo writes down facts, people and places, promises and dates. The conversation text is sent to Cloud.ru once more for that.",
      sleep: "Kitsune sleep", sleepHint: "Once a day, when the chat is quiet, Yakumo tidies her memory and writes first in the morning: her “dream”, what not to forget, how your goals are going.",
      mood: "Notice mood", moodHint: "Yakumo notes how you feel in conversations and is gentler after a few hard days. Stays only with you.",
      activity: "See what's open on the computer", activityHint: "Once a minute Yakumo checks which program is on screen to help at the right moment. Window titles are not saved, only minutes per program per day.",
      activityNo: "Windows only.",
      noCloud: "Connect Cloud.ru in settings so Yakumo can learn, sleep and search by meaning.",
      busy: "Thinking over the last conversation…", lastError: (e) => `Couldn't process the conversation: ${e}`,
      semantic: (m, n) => `Search by meaning: ${m}, ${n} vectors.`, semanticOff: "Search by meaning: no embedding model in the Cloud.ru catalog, searching by words.",
      sleepNow: "Sleep now", sleeping: "Sleeping…", lastSleep: (d) => `Last sleep: ${d}.`, noMorning: "Nothing to tell in the morning yet — memory is empty.",
      tip: "In chat you can say: “remember that I take tea without sugar”, “how do you know that?”, “remind me to send the report on Friday”, “remember how I do the weekly report”, “do you remember what we talked about last week?”",
      addPlaceholder: "For example: my sister Ann lives in Kazan", add: "Remember",
      search: "Search memory", nothing: "Nothing found",
      kinds: { person: "About you", likes: "Tastes and habits", work: "Work and plans", other: "Other", self: "Yakumo and you" },
      types: { person: "Person", pet: "Pet", place: "Place", project: "Project", org: "Organization", thing: "Other" },
      you: "You", sources: { auto: "learned herself", chat: "you asked", manual: "added by hand", module: "from a module" },
      from: "Source", quote: (q) => `“${q}”`,
      emptyFacts: "Nothing remembered yet", emptyFactsHint: "Chat with Yakumo or add a fact yourself.",
      emptyMap: "The map is empty", emptyMapHint: "People, pets, places and projects Yakumo learns about will appear here.",
      emptyTalks: "No conversations yet", emptyTalksHint: "A summary appears half a minute after a chat.",
      emptyPlans: "No promises or dates yet", emptyPlansHint: "Say in chat: “remind me to send the report on Friday” or “mom's birthday is March 12”.",
      emptySkills: "No skills yet", emptySkillsHint: "Explain to Yakumo how you do something and ask her to remember. Then say “do the weekly report”.",
      pin: "Pin: always remember", unpin: "Unpin", edit: "Edit", del: "Forget", save: "Save",
      cancel: "Cancel", strength: (s) => `Memory strength: ${s}`, faded: "fading",
      messages: (n) => `${n} ${n === 1 ? "message" : "messages"}`,
      exp: "Export", imp: "Import", clear: "Forget everything",
      clearAsk: "Forget everything: facts, conversations, promises, dates and skills? Only an export file can bring them back.",
      imported: (f, t) => `Added: ${f} facts, ${t} conversations`, error: "Error",
      promisesUser: "You promised", promisesYakumo: "Yakumo promised", dates: "Dates", done: "Done", due: (d) => `by ${d}`,
      overdue: "overdue", yearly: "every year", addPromise: "New promise", addDate: "New date",
      who: { user: "I promise", yakumo: "Remind me" }, upcoming: "Soon",
      inDays: (n) => (n < 0 ? "overdue" : n === 0 ? "today" : n === 1 ? "tomorrow" : `in ${n} days`),
      steps: (n) => `${n} ${n === 1 ? "step" : "steps"}`, used: (n) => `used ${n} ${n === 1 ? "time" : "times"}`,
      moodTitle: "Mood this month", factsAbout: (n) => `Facts: ${n}`, relation: "Relation", rename: "Name",
      openFile: "Open on Drive",
    },
  };

  function plural(n, one, few, many) {
    const m10 = n % 10, m100 = n % 100;
    if (m10 === 1 && m100 !== 11) return one;
    if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
    return many;
  }

  const lang = () => window.Yakumo.lang();
  const L = new Proxy({}, { get: (_t, k) => (TX[lang()] || TX.ru)[k] });
  const state = { data: null, tab: "facts", query: "", editing: null, open: null, node: null, msg: null, error: null,
                  sleeping: false };
  const root = h("div", { class: "brain" });
  let timer = 0;

  // --- Сообщения, которые Yakumo пишет первой ---

  async function inbox() {
    try {
      const res = await getJSON("/api/brain/inbox");
      for (const m of res.messages || []) window.Yakumo.say(m.text);
    } catch { /* сервер перезапускается — заберём в следующий раз */ }
  }
  setTimeout(inbox, 1500);
  setInterval(inbox, 60000);

  // --- Запросы ---

  async function load() {
    try {
      state.data = await getJSON("/api/brain");
      state.error = null;
    } catch (e) {
      state.error = e.message;
    }
    draw();
    // Пока Yakumo разбирает разговор, обновляем страницу, чтобы новые факты появились сами.
    clearTimeout(timer);
    if (state.data?.busy && document.body.dataset.page === "brain") timer = setTimeout(load, 5000);
  }

  async function send(name, data) {
    try {
      const res = await postJSON(`/api/brain/${name}`, data);
      state.data = res.state || res;
      state.msg = null;
      return res;
    } catch (e) {
      state.msg = { text: `${L.error}: ${e.message}`, bad: true };
    } finally {
      draw();
    }
  }

  // --- Мелочи ---

  const date = (t) => new Date(t * 1000).toLocaleDateString(lang(), { day: "numeric", month: "short", year: "numeric" });
  const day = (s) => new Date(s + "T12:00").toLocaleDateString(lang(), { day: "numeric", month: "long" });
  const entityById = () => Object.fromEntries((state.data.entities || []).map((e) => [e.id, e]));

  function tool(text, label, onclick, cls = "") {
    return h("button", { type: "button", class: "br-tool " + cls, title: label, "aria-label": label, onclick }, text);
  }

  function empty(title, hint) {
    return h("div", { class: "br-empty" }, h("strong", {}, title), hint ? h("span", {}, hint) : "");
  }

  function matches(text) {
    const q = state.query.trim().toLowerCase();
    return !q || text.toLowerCase().includes(q);
  }

  function select(options, value, label) {
    const el = h("select", { class: "select", "aria-label": label }, options.map(([v, t]) => h("option", { value: v }, t)));
    el.value = value;
    return el;
  }

  // --- Настройки ---

  function switchRow(key, title, hint, disabled = false) {
    const input = h("input", { type: "checkbox", role: "switch", checked: !!state.data[key] && !disabled, disabled,
                               onchange: (e) => send("settings", { [key]: e.target.checked }) });
    return h("label", { class: "row" + (disabled ? " disabled" : "") },
      h("span", { class: "row-text" }, h("span", { class: "row-title" }, title), h("span", { class: "row-hint" }, hint)),
      h("span", { class: "switch" }, input, h("span", { class: "knob" })));
  }

  async function sleepNow() {
    state.sleeping = true;
    draw();
    const res = await send("sleep", {});
    state.sleeping = false;
    if (res) {
      state.msg = { text: res.morning ? "" : L.noMorning };
      if (res.morning) await inbox();
    }
    draw();
  }

  function settingsCard() {
    const d = state.data;
    const off = !d.enabled;
    const note = !d.cloud ? h("p", { class: "row-hint bad" }, L.noCloud)
      : d.busy ? h("p", { class: "row-hint br-busy" }, L.busy)
      : d.error ? h("p", { class: "row-hint bad" }, L.lastError(d.error)) : "";
    const sem = d.semantic || {};
    return h("section", { class: "card group" },
      switchRow("enabled", L.enabled, L.enabledHint),
      switchRow("auto", L.auto, L.autoHint, off || !d.cloud),
      switchRow("sleep", L.sleep, L.sleepHint, off),
      switchRow("mood", L.mood, L.moodHint, off),
      switchRow("activity", L.activity, d.activity_available ? L.activityHint : L.activityNo, off || !d.activity_available),
      note,
      h("div", { class: "br-status" },
        h("span", { class: "row-hint" },
          d.cloud ? (sem.model ? L.semantic(sem.model, sem.indexed) : sem.error === "no_model" ? L.semanticOff : "") : "",
          d.last_sleep ? " " + L.lastSleep(day(d.last_sleep)) : ""),
        h("button", { class: "btn", type: "button", disabled: off || state.sleeping, onclick: sleepNow },
          state.sleeping ? L.sleeping : L.sleepNow)),
      h("p", { class: "row-hint br-tip" }, L.tip));
  }

  function addForm() {
    const input = h("input", { class: "text-input", maxlength: 300, placeholder: L.addPlaceholder,
                               "aria-label": L.addPlaceholder });
    const kind = select(state.data.kinds.map((k) => [k, L.kinds[k]]), "person", L.facts);
    return h("form", { class: "br-add", onsubmit: async (e) => {
      e.preventDefault();
      if (!input.value.trim()) return input.focus();
      await send("fact", { text: input.value, kind: kind.value });
    } }, input, kind, h("button", { class: "btn primary", type: "submit" }, L.add));
  }

  // --- Факты ---

  function chips(f) {
    const ents = entityById();
    const about = (f.about || []).map((id) => ents[id]).filter(Boolean).map((e) =>
      h("button", { type: "button", class: "br-chip", onclick: () => { state.tab = "map"; state.node = e.id; draw(); } },
        e.name + (e.relation ? ` · ${e.relation}` : "")));
    const files = (f.files || []).map((p) =>
      h("a", { class: "br-chip file", href: `/api/disk/file?path=${encodeURIComponent(p)}`, target: "_blank",
               title: L.openFile }, "📄 " + p.split("/").pop()));
    return about.length || files.length ? h("div", { class: "br-chips" }, about, files) : "";
  }

  function factEl(f) {
    if (state.editing === f.id) {
      const input = h("input", { class: "text-input", value: f.text, maxlength: 300 });
      const kind = select(state.data.kinds.map((k) => [k, L.kinds[k]]), f.kind);
      setTimeout(() => input.focus());
      return h("li", { class: "br-fact editing" }, h("form", { class: "br-add", onsubmit: async (e) => {
        e.preventDefault();
        state.editing = null;
        await send("fact", { id: f.id, text: input.value, kind: kind.value });
      } }, input, kind,
        h("button", { class: "btn primary", type: "submit" }, L.save),
        h("button", { class: "btn", type: "button", onclick: () => { state.editing = null; draw(); } }, L.cancel)));
    }
    // Сила памяти: 0..5 делений; закреплённые — всегда полные.
    const level = Math.max(0, Math.min(5, Math.round(f.score)));
    const meter = h("span", { class: "br-meter", title: L.strength(f.score), "aria-label": L.strength(f.score) },
      [0, 1, 2, 3, 4].map((i) => h("i", { class: i < level ? "on" : "" })));
    const open = state.open === f.id;
    return h("li", { class: "br-fact" + (f.pinned ? " pinned" : "") + (f.score < 1 ? " faded" : "") },
      meter,
      h("div", { class: "br-fact-body" },
        h("div", { class: "br-fact-text" }, f.text),
        chips(f),
        h("div", { class: "br-meta" },
          h("button", { type: "button", class: "br-link", "aria-expanded": String(open),
                        onclick: () => { state.open = open ? null : f.id; draw(); } },
            `${L.sources[f.source] || f.source || ""} · ${date(f.created)}`),
          f.score < 1 ? ` · ${L.faded}` : ""),
        open ? h("div", { class: "br-quote" }, h("b", {}, L.from + ": "),
          f.quote ? L.quote(f.quote) : L.sources[f.source] || "",
          f.talk && talkTitle(f.talk) ? ` — «${talkTitle(f.talk)}»` : "") : ""),
      h("div", { class: "br-tools" },
        tool(f.pinned ? "★" : "☆", f.pinned ? L.unpin : L.pin, () => send("fact", { id: f.id, pinned: !f.pinned }),
          f.pinned ? "on" : ""),
        tool("✎", L.edit, () => { state.editing = f.id; draw(); }),
        tool("✕", L.del, () => send("forget", { ids: [f.id] }), "danger")));
  }

  const talkTitle = (id) => state.data.talks.find((t) => t.id === id)?.title;

  function factsView() {
    const ents = entityById();
    const text = (f) => `${f.text} ${(f.about || []).map((id) => ents[id]?.name || "").join(" ")}`;
    const facts = state.data.facts.filter((f) => matches(text(f)));
    if (!state.data.facts.length) return empty(L.emptyFacts, L.emptyFactsHint);
    if (!facts.length) return empty(L.nothing, "");
    return state.data.kinds.map((k) => {
      const list = facts.filter((f) => f.kind === k);
      return list.length ? h("section", { class: "br-kind" },
        h("h2", {}, L.kinds[k], h("span", {}, String(list.length))),
        h("ul", { class: "br-list" }, list.map(factEl))) : "";
    });
  }

  // --- Карта памяти: вы в центре, вокруг люди, места и проекты ---

  function layout(nodes, links, w, hgt) {
    // Небольшая силовая раскладка: узлы отталкиваются, связи тянут, центр закреплён.
    const cx = w / 2, cy = hgt / 2;
    nodes.forEach((n, i) => {
      const a = (i / Math.max(1, nodes.length - 1)) * Math.PI * 2;
      if (!n.fixed) { n.x = cx + Math.cos(a) * w * 0.3; n.y = cy + Math.sin(a) * hgt * 0.3; }
    });
    for (let step = 0; step < 300; step++) {
      const t = 1 - step / 300;
      for (const a of nodes) for (const b of nodes) {
        if (a === b) continue;
        const dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy || 1;
        const f = 2400 / d2;
        if (!a.fixed) { a.x += dx * f * 0.05 * t; a.y += dy * f * 0.05 * t; }
      }
      for (const l of links) {
        const dx = l.b.x - l.a.x, dy = l.b.y - l.a.y, d = Math.hypot(dx, dy) || 1;
        const f = (d - l.len) / d * 0.08 * t;
        if (!l.a.fixed) { l.a.x += dx * f; l.a.y += dy * f; }
        if (!l.b.fixed) { l.b.x -= dx * f; l.b.y -= dy * f; }
      }
      for (const n of nodes) {
        n.x = Math.max(40, Math.min(w - 40, n.x));
        n.y = Math.max(30, Math.min(hgt - 48, n.y));
      }
    }
  }

  function mapView() {
    const ents = (state.data.entities || []).filter((e) => e.facts > 0 && matches(`${e.name} ${e.relation || ""}`));
    if (!ents.length) return empty(state.data.entities?.length ? L.nothing : L.emptyMap, L.emptyMapHint);
    // Рисуем в размер страницы, чтобы на телефоне подписи не становились мелкими.
    const w = Math.max(320, Math.min(820, root.clientWidth || 820)), hgt = Math.max(380, Math.min(620, 220 + ents.length * 18));
    const me = { id: "me", name: L.you, fixed: true, x: w / 2, y: hgt / 2, r: 22 };
    const nodes = [me, ...ents.map((e) => ({ ...e, r: 7 + Math.min(14, Math.sqrt(e.facts) * 4) }))];
    const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
    const links = nodes.slice(1).map((n) => ({ a: me, b: n, len: (n.type === "person" || n.type === "pet" ? 150 : 220) * Math.min(1, w / 820) }));
    const pairs = new Set();
    for (const f of state.data.facts) {
      const ids = (f.about || []).filter((id) => byId[id]);
      for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
        const key = [ids[i], ids[j]].sort().join("|");
        if (!pairs.has(key)) { pairs.add(key); links.push({ a: byId[ids[i]], b: byId[ids[j]], len: 110, side: true }); }
      }
    }
    layout(nodes, links, w, hgt);
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", `0 0 ${w} ${hgt}`);
    svg.setAttribute("class", "br-map");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", L.map);
    const el = (tag, attrs, parent = svg) => {
      const x = document.createElementNS(SVG, tag);
      for (const [k, v] of Object.entries(attrs)) x.setAttribute(k, v);
      parent.append(x);
      return x;
    };
    for (const l of links) el("line", { x1: l.a.x, y1: l.a.y, x2: l.b.x, y2: l.b.y, class: l.side ? "side" : "" });
    for (const n of nodes) {
      const g = el("g", { class: `br-node t-${n.type || "me"}` + (state.node === n.id ? " on" : ""), tabindex: n.fixed ? -1 : 0,
                          transform: `translate(${n.x.toFixed(1)} ${n.y.toFixed(1)})` });
      el("circle", { r: n.r }, g);
      const label = el("text", { y: n.r + 15 }, g);
      label.textContent = n.name;
      if (n.relation) {
        const sub = el("text", { y: n.r + 28, class: "sub" }, g);
        sub.textContent = n.relation;
      }
      if (!n.fixed) {
        const pick = () => { state.node = state.node === n.id ? null : n.id; draw(); };
        g.addEventListener("click", pick);
        g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
      }
    }
    return [h("div", { class: "br-map-wrap" }, svg), nodePanel()];
  }

  function nodePanel() {
    const e = (state.data.entities || []).find((x) => x.id === state.node);
    if (!e) return "";
    const facts = state.data.facts.filter((f) => (f.about || []).includes(e.id));
    const name = h("input", { class: "text-input", value: e.name, maxlength: 60, "aria-label": L.rename });
    const rel = h("input", { class: "text-input", value: e.relation || "", maxlength: 40, placeholder: L.relation,
                             "aria-label": L.relation });
    const type = select(state.data.entity_types.map((t) => [t, L.types[t]]), e.type);
    return h("section", { class: "card br-node-panel" },
      h("form", { class: "br-add", onsubmit: (ev) => {
        ev.preventDefault();
        send("item", { type: "entity", id: e.id, name: name.value, relation: rel.value, entity_type: type.value });
      } }, name, rel, type, h("button", { class: "btn primary", type: "submit" }, L.save),
        h("button", { class: "btn br-danger", type: "button",
                      onclick: () => { state.node = null; send("item/delete", { type: "entity", ids: [e.id] }); } }, L.del)),
      h("div", { class: "row-hint" }, L.factsAbout(facts.length)),
      h("ul", { class: "br-list" }, facts.map(factEl)));
  }

  // --- Разговоры и настроение ---

  function moodStrip() {
    const days = state.data.mood_days || [];
    if (!days.length) return "";
    return h("section", { class: "br-mood" }, h("h2", {}, L.moodTitle),
      h("div", { class: "br-mood-bars" }, days.map((d) => h("i", {
        class: d.mood < -0.5 ? "low" : d.mood > 0.5 ? "high" : "",
        style: `height:${Math.round(20 + (d.mood + 2) * 10)}px`, title: `${day(d.date)}: ${d.mood}`,
      }))));
  }

  function talksView() {
    const talks = state.data.talks.filter((t) => matches(`${t.title} ${t.summary}`));
    if (!state.data.talks.length) return empty(L.emptyTalks, L.emptyTalksHint);
    return [moodStrip(), talks.length ? h("ul", { class: "br-list" }, talks.map((t) => h("li", { class: "br-talk" },
      h("div", { class: "br-fact-body" },
        h("div", { class: "br-talk-head" }, h("strong", {}, t.title), h("span", { class: "br-meta" },
          `${date(t.updated)} · ${L.messages(t.messages || 0)}`)),
        h("div", { class: "br-fact-text" }, t.summary)),
      h("div", { class: "br-tools" }, tool("✕", L.del, () => send("talks/delete", { ids: [t.id] }), "danger")))))
      : empty(L.nothing, "")];
  }

  // --- Обещания и даты ---

  function plansView() {
    const d = state.data;
    const promises = d.promises.filter((p) => matches(p.text));
    const events = d.events.filter((e) => matches(e.text));
    const text = h("input", { class: "text-input", maxlength: 300, placeholder: L.addPromise, "aria-label": L.addPromise });
    const who = select([["user", L.who.user], ["yakumo", L.who.yakumo]], "user", L.addPromise);
    const due = h("input", { class: "text-input br-date", type: "date", "aria-label": L.due("") });
    const evText = h("input", { class: "text-input", maxlength: 300, placeholder: L.addDate, "aria-label": L.addDate });
    const evDate = h("input", { class: "text-input br-date", type: "date", required: true, "aria-label": L.addDate });
    const yearly = h("input", { type: "checkbox" });
    const promiseRow = (p) => h("li", { class: "br-fact br-promise" + (p.done ? " done" : "") },
      h("input", { type: "checkbox", checked: !!p.done, "aria-label": L.done,
                   onchange: (e) => send("item", { type: "promise", id: p.id, done: e.target.checked }) }),
      h("div", { class: "br-fact-body" }, h("div", { class: "br-fact-text" }, p.text),
        h("div", { class: "br-meta" }, p.due ? L.due(day(p.due)) : "", p.due && !p.done && p.due < new Date().toISOString().slice(0, 10)
          ? h("span", { class: "br-overdue" }, ` · ${L.overdue}`) : "")),
      h("div", { class: "br-tools" }, tool("✕", L.del, () => send("item/delete", { type: "promises", ids: [p.id] }), "danger")));
    const group = (title, list) => list.length ? h("section", { class: "br-kind" },
      h("h2", {}, title, h("span", {}, String(list.filter((p) => !p.done).length))),
      h("ul", { class: "br-list" }, list.map(promiseRow))) : "";
    const soon = d.upcoming.filter((x) => x.in_days <= 7);
    return [
      soon.length ? h("section", { class: "card br-soon" }, h("h2", {}, L.upcoming),
        soon.map((x) => h("div", { class: "br-soon-row" + (x.in_days < 0 ? " bad" : "") },
          h("b", {}, L.inDays(x.in_days)), " ", x.text))) : "",
      h("form", { class: "br-add", onsubmit: (e) => {
        e.preventDefault();
        if (!text.value.trim()) return text.focus();
        send("item", { type: "promise", text: text.value, who: who.value, due: due.value || null });
      } }, text, who, due, h("button", { class: "btn primary", type: "submit" }, L.add)),
      h("form", { class: "br-add", onsubmit: (e) => {
        e.preventDefault();
        if (!evText.value.trim()) return evText.focus();
        send("item", { type: "event", text: evText.value, date: evDate.value, yearly: yearly.checked });
      } }, evText, evDate, h("label", { class: "br-check" }, yearly, L.yearly),
        h("button", { class: "btn primary", type: "submit" }, L.add)),
      !promises.length && !events.length ? empty(d.promises.length || d.events.length ? L.nothing : L.emptyPlans, L.emptyPlansHint) : "",
      group(L.promisesUser, promises.filter((p) => p.who === "user")),
      group(L.promisesYakumo, promises.filter((p) => p.who === "yakumo")),
      events.length ? h("section", { class: "br-kind" }, h("h2", {}, L.dates, h("span", {}, String(events.length))),
        h("ul", { class: "br-list" }, events.map((e) => h("li", { class: "br-fact" },
          h("div", { class: "br-fact-body" }, h("div", { class: "br-fact-text" }, e.text),
            h("div", { class: "br-meta" }, e.yearly ? `${day(e.date)} · ${L.yearly}` : date(new Date(e.date + "T12:00") / 1000))),
          h("div", { class: "br-tools" }, tool("✕", L.del, () => send("item/delete", { type: "events", ids: [e.id] }), "danger")))))) : "",
    ];
  }

  // --- Навыки ---

  function skillsView() {
    const skills = state.data.skills.filter((s) => matches(`${s.name} ${s.when || ""} ${s.steps.join(" ")}`));
    if (!state.data.skills.length) return empty(L.emptySkills, L.emptySkillsHint);
    if (!skills.length) return empty(L.nothing, "");
    return h("ul", { class: "br-list" }, skills.map((s) => {
      const open = state.open === s.id;
      return h("li", { class: "br-fact br-skill" },
        h("div", { class: "br-fact-body" },
          h("button", { type: "button", class: "br-link br-skill-name", "aria-expanded": String(open),
                        onclick: () => { state.open = open ? null : s.id; draw(); } }, s.name),
          s.when ? h("div", { class: "br-meta" }, s.when) : "",
          h("div", { class: "br-meta" }, `${L.steps(s.steps.length)} · ${L.used(s.used || 0)}`),
          open ? h("ol", { class: "br-steps" }, s.steps.map((x) => h("li", {}, x))) : ""),
        h("div", { class: "br-tools" }, tool("✕", L.del, () => send("item/delete", { type: "skills", ids: [s.id] }), "danger")));
    }));
  }

  // --- Экспорт и импорт ---

  function exportFile() {
    getJSON("/api/brain/export").then((data) => {
      const blob = new Blob([JSON.stringify(data, null, 1)], { type: "application/json" });
      const a = h("a", { href: URL.createObjectURL(blob),
                         download: `yakumo-memory-${new Date().toISOString().slice(0, 10)}.json` });
      document.body.append(a);
      a.click();
      setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    }).catch((e) => { state.msg = { text: `${L.error}: ${e.message}`, bad: true }; draw(); });
  }

  function importFile() {
    const input = h("input", { type: "file", accept: ".json,application/json", onchange: async () => {
      const file = input.files[0];
      if (!file) return;
      let data;
      try { data = JSON.parse(await file.text()); } catch { data = null; }
      const res = await send("import", data);
      if (res) { state.msg = { text: L.imported(res.facts, res.talks) }; draw(); }
    } });
    input.click();
  }

  // --- Страница ---

  function draw() {
    if (!state.data) {
      root.replaceChildren(h("h1", {}, L.title), state.error ? h("p", { class: "row-hint bad" }, state.error) : "");
      return;
    }
    const d = state.data;
    const search = h("input", { class: "text-input", type: "search", placeholder: L.search, "aria-label": L.search,
                                value: state.query, oninput: (e) => {
                                  state.query = e.target.value;
                                  const pos = e.target.selectionStart;
                                  draw();
                                  const again = root.querySelector(".br-search input");
                                  again.focus();
                                  again.setSelectionRange(pos, pos);
                                } });
    const openPromises = d.promises.filter((p) => !p.done).length;
    const tabs = [["facts", L.facts, d.facts.length], ["map", L.map, d.entities.filter((e) => e.facts > 0).length],
                  ["talks", L.talks, d.talks.length], ["plans", L.plans, openPromises + d.events.length],
                  ["skills", L.skills, d.skills.length]];
    const views = { facts: factsView, map: mapView, talks: talksView, plans: plansView, skills: skillsView };
    root.replaceChildren(
      h("div", { class: "br-head" },
        h("div", {}, h("h1", {}, L.title), h("p", { class: "br-lead" }, L.lead(d.facts.length, d.talks.length))),
        h("div", { class: "br-actions" },
          h("button", { class: "btn", type: "button", onclick: exportFile }, L.exp),
          h("button", { class: "btn", type: "button", onclick: importFile }, L.imp),
          h("button", { class: "btn br-danger", type: "button", disabled: !d.facts.length && !d.talks.length,
                        onclick: () => confirm(L.clearAsk) && send("clear", { all: true }) }, L.clear))),
      state.msg?.text ? h("p", { class: "row-hint br-msg " + (state.msg.bad ? "bad" : "good") }, state.msg.text) : "",
      settingsCard(),
      addForm(),
      h("div", { class: "br-tabs" },
        h("div", { class: "br-tablist", role: "tablist" }, tabs.map(([id, label, n]) => h("button", {
          type: "button", role: "tab", "aria-selected": String(state.tab === id), class: state.tab === id ? "on" : "",
          onclick: () => { state.tab = id; state.open = null; draw(); } }, label, h("span", {}, String(n))))),
        h("div", { class: "br-search" }, search)),
      h("div", { class: "br-view" }, views[state.tab]()));
  }

  window.Yakumo.addPage({
    id: "brain",
    icon: '<path d="M9 4.5a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 6 1V5.5a2.5 2.5 0 0 0-3-1z"/>'
      + '<path d="M15 4.5a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-6 1"/><path d="M12 9h2.5M12 14h3"/>',
    title: { ru: TX.ru.title, en: TX.en.title },
    render() {
      load();
      draw();
      return [root];
    },
  });
})();
