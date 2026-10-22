"use strict";

// «Память»: что Yakumo помнит о пользователе и о прошлых разговорах. Страница подключается через Yakumo.addPage.
(() => {
  const { h, getJSON, postJSON } = window.Yakumo;

  const TX = {
    ru: {
      title: "Память", facts: "Факты", talks: "Разговоры",
      lead: (f, t) => `Yakumo помнит ${f} ${plural(f, "факт", "факта", "фактов")} о вас и ${t} ${plural(t, "разговор", "разговора", "разговоров")}.`,
      enabled: "Помнить в чате", enabledHint: "Yakumo видит свою память в каждом новом разговоре.",
      auto: "Запоминать самой", autoHint: "После паузы в разговоре Yakumo выписывает новые факты и конспект беседы. Для этого текст разговора ещё раз отправляется в Cloud.ru.",
      noCloud: "Чтобы Yakumo запоминала сама, подключите Cloud.ru в настройках.",
      busy: "Думаю над последним разговором…", lastError: (e) => `Не получилось разобрать разговор: ${e}`,
      tip: "В чате можно сказать: «запомни, что я пью чай без сахара», «забудь про мой старый адрес», «помнишь, о чём мы говорили на прошлой неделе?»",
      addPlaceholder: "Например: меня зовут Аня, я учусь на дизайнера", add: "Запомнить",
      search: "Поиск по памяти", nothing: "Ничего не нашлось",
      kinds: { person: "О вас", likes: "Вкусы и привычки", work: "Дела и планы", other: "Разное" },
      sources: { auto: "запомнила сама", chat: "вы попросили", manual: "добавлено вручную" },
      emptyFacts: "Пока ничего не запомнено", emptyFactsHint: "Поговорите с Yakumo или добавьте факт сами.",
      emptyTalks: "Разговоров пока нет", emptyTalksHint: "Конспект появится через полминуты после разговора в чате.",
      pin: "Закрепить: всегда помнить", unpin: "Открепить", edit: "Изменить", del: "Забыть", save: "Сохранить",
      cancel: "Отмена", strength: (s) => `Сила памяти: ${s}`, faded: "тускнеет",
      messages: (n) => `${n} ${plural(n, "реплика", "реплики", "реплик")}`,
      exp: "Экспорт", imp: "Импорт", clear: "Забыть всё",
      clearAsk: "Забыть все факты и разговоры? Вернуть их можно будет только из файла экспорта.",
      imported: (f, t) => `Добавлено: фактов ${f}, разговоров ${t}`, error: "Ошибка",
    },
    en: {
      title: "Memory", facts: "Facts", talks: "Conversations",
      lead: (f, t) => `Yakumo remembers ${f} ${f === 1 ? "fact" : "facts"} about you and ${t} ${t === 1 ? "conversation" : "conversations"}.`,
      enabled: "Use memory in chat", enabledHint: "Yakumo sees her memory in every new conversation.",
      auto: "Learn by herself", autoHint: "After a pause in the chat Yakumo writes down new facts and a summary. The conversation text is sent to Cloud.ru once more for that.",
      noCloud: "Connect Cloud.ru in settings so Yakumo can learn by herself.",
      busy: "Thinking over the last conversation…", lastError: (e) => `Couldn't process the conversation: ${e}`,
      tip: "In chat you can say: “remember that I take tea without sugar”, “forget my old address”, “do you remember what we talked about last week?”",
      addPlaceholder: "For example: my name is Ann, I study design", add: "Remember",
      search: "Search memory", nothing: "Nothing found",
      kinds: { person: "About you", likes: "Tastes and habits", work: "Work and plans", other: "Other" },
      sources: { auto: "learned herself", chat: "you asked", manual: "added by hand" },
      emptyFacts: "Nothing remembered yet", emptyFactsHint: "Chat with Yakumo or add a fact yourself.",
      emptyTalks: "No conversations yet", emptyTalksHint: "A summary appears half a minute after a chat.",
      pin: "Pin: always remember", unpin: "Unpin", edit: "Edit", del: "Forget", save: "Save",
      cancel: "Cancel", strength: (s) => `Memory strength: ${s}`, faded: "fading",
      messages: (n) => `${n} ${n === 1 ? "message" : "messages"}`,
      exp: "Export", imp: "Import", clear: "Forget everything",
      clearAsk: "Forget all facts and conversations? They can only be restored from an export file.",
      imported: (f, t) => `Added: ${f} facts, ${t} conversations`, error: "Error",
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
  const state = { data: null, tab: "facts", query: "", editing: null, msg: null, error: null };
  const root = h("div", { class: "brain" });
  let timer = 0;

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

  // --- Части страницы ---

  const date = (t) => new Date(t * 1000).toLocaleDateString(lang(), { day: "numeric", month: "short", year: "numeric" });

  function switchRow(key, title, hint, disabled = false) {
    const input = h("input", { type: "checkbox", role: "switch", checked: !!state.data[key] && !disabled, disabled,
                               onchange: (e) => send("settings", { [key]: e.target.checked }) });
    return h("label", { class: "row" + (disabled ? " disabled" : "") },
      h("span", { class: "row-text" }, h("span", { class: "row-title" }, title), h("span", { class: "row-hint" }, hint)),
      h("span", { class: "switch" }, input, h("span", { class: "knob" })));
  }

  function settingsCard() {
    const d = state.data;
    const note = !d.cloud ? h("p", { class: "row-hint bad" }, L.noCloud)
      : d.busy ? h("p", { class: "row-hint br-busy" }, L.busy)
      : d.error ? h("p", { class: "row-hint bad" }, L.lastError(d.error)) : "";
    return h("section", { class: "card group" },
      switchRow("enabled", L.enabled, L.enabledHint),
      switchRow("auto", L.auto, L.autoHint, !d.enabled || !d.cloud),
      note,
      h("p", { class: "row-hint br-tip" }, L.tip));
  }

  function addForm() {
    const input = h("input", { class: "text-input", maxlength: 300, placeholder: L.addPlaceholder,
                               "aria-label": L.addPlaceholder });
    const kind = h("select", { class: "select", "aria-label": L.facts },
      state.data.kinds.map((k) => h("option", { value: k }, L.kinds[k])));
    kind.value = "person";
    return h("form", { class: "br-add", onsubmit: async (e) => {
      e.preventDefault();
      if (!input.value.trim()) return input.focus();
      await send("fact", { text: input.value, kind: kind.value });
    } }, input, kind, h("button", { class: "btn primary", type: "submit" }, L.add));
  }

  function matches(text) {
    const q = state.query.trim().toLowerCase();
    return !q || text.toLowerCase().includes(q);
  }

  function factEl(f) {
    if (state.editing === f.id) {
      const input = h("input", { class: "text-input", value: f.text, maxlength: 300 });
      const kind = h("select", { class: "select" },
        state.data.kinds.map((k) => h("option", { value: k }, L.kinds[k])));
      kind.value = f.kind;
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
    return h("li", { class: "br-fact" + (f.pinned ? " pinned" : "") + (f.score < 1 ? " faded" : "") },
      meter,
      h("div", { class: "br-fact-body" },
        h("div", { class: "br-fact-text" }, f.text),
        h("div", { class: "br-meta" }, `${L.sources[f.source] || ""} · ${date(f.created)}`,
          f.score < 1 ? ` · ${L.faded}` : "")),
      h("div", { class: "br-tools" },
        tool(f.pinned ? "★" : "☆", f.pinned ? L.unpin : L.pin, () => send("fact", { id: f.id, pinned: !f.pinned }),
          f.pinned ? "on" : ""),
        tool("✎", L.edit, () => { state.editing = f.id; draw(); }),
        tool("✕", L.del, () => send("forget", { ids: [f.id] }), "danger")));
  }

  function tool(text, label, onclick, cls = "") {
    return h("button", { type: "button", class: "br-tool " + cls, title: label, "aria-label": label, onclick }, text);
  }

  function factsView() {
    const facts = state.data.facts.filter((f) => matches(f.text));
    if (!state.data.facts.length) return empty(L.emptyFacts, L.emptyFactsHint);
    if (!facts.length) return empty(L.nothing, "");
    return state.data.kinds.map((k) => {
      const list = facts.filter((f) => f.kind === k);
      return list.length ? h("section", { class: "br-kind" },
        h("h2", {}, L.kinds[k], h("span", {}, String(list.length))),
        h("ul", { class: "br-list" }, list.map(factEl))) : "";
    });
  }

  function talksView() {
    const talks = state.data.talks.filter((t) => matches(`${t.title} ${t.summary}`));
    if (!state.data.talks.length) return empty(L.emptyTalks, L.emptyTalksHint);
    if (!talks.length) return empty(L.nothing, "");
    return h("ul", { class: "br-list" }, talks.map((t) => h("li", { class: "br-talk" },
      h("div", { class: "br-fact-body" },
        h("div", { class: "br-talk-head" }, h("strong", {}, t.title), h("span", { class: "br-meta" },
          `${date(t.updated)} · ${L.messages(t.messages || 0)}`)),
        h("div", { class: "br-fact-text" }, t.summary)),
      h("div", { class: "br-tools" }, tool("✕", L.del, () => send("talks/delete", { ids: [t.id] }), "danger")))));
  }

  function empty(title, hint) {
    return h("div", { class: "br-empty" }, h("strong", {}, title), hint ? h("span", {}, hint) : "");
  }

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
    const tab = (id, label, n) => h("button", { type: "button", role: "tab", "aria-selected": String(state.tab === id),
                                               class: state.tab === id ? "on" : "",
                                               onclick: () => { state.tab = id; draw(); } }, label, h("span", {}, String(n)));
    root.replaceChildren(
      h("div", { class: "br-head" },
        h("div", {}, h("h1", {}, L.title), h("p", { class: "br-lead" }, L.lead(d.facts.length, d.talks.length))),
        h("div", { class: "br-actions" },
          h("button", { class: "btn", type: "button", onclick: exportFile }, L.exp),
          h("button", { class: "btn", type: "button", onclick: importFile }, L.imp),
          h("button", { class: "btn br-danger", type: "button", disabled: !d.facts.length && !d.talks.length,
                        onclick: () => confirm(L.clearAsk) && send("clear", { all: true }) }, L.clear))),
      state.msg ? h("p", { class: "row-hint br-msg " + (state.msg.bad ? "bad" : "good") }, state.msg.text) : "",
      settingsCard(),
      addForm(),
      h("div", { class: "br-tabs" },
        h("div", { class: "br-tablist", role: "tablist" },
          tab("facts", L.facts, d.facts.length), tab("talks", L.talks, d.talks.length)),
        h("div", { class: "br-search" }, search)),
      h("div", { class: "br-view" }, state.tab === "facts" ? factsView() : talksView()));
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
