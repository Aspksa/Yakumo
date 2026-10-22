"use strict";

(() => {
  const { h, getJSON, postJSON } = window.Yakumo;
  const words = {
    ru: {
      title: "Обновление проекта", hint: "Новые версии Yakumo из Aspksa/Yakumo на GitHub.",
      source: "Источник", main: "Основная ветка · main", release: "Опубликованный выпуск",
      schedule: "Автопроверка", off: "Выключена", hourly: "Раз в час", daily: "Раз в день",
      autoHint: "По расписанию проверяется наличие обновления. Установка запускается кнопкой.",
      installed: "Установлено", unknown: "Локальная копия — определится при проверке", latest: "Доступная версия",
      unchecked: "Ещё не проверялась", checked: "Последняя проверка", check: "Проверить обновления",
      prepare: "Скачать и проверить", install: "Установить и перезапустить", rollback: "Вернуть предыдущую версию",
      rollbackHint: "Перед каждой установкой сохраняется копия заменяемых файлов.", backup: "Последняя резервная копия",
      safe: "Настройки, ключи, файлы «Диска», Python и пользовательские модули сохраняются.",
      changed: "Заменить", added: "Добавить", removed: "Убрать", preview: "Изменения в файлах",
      modifications: (n) => `Локально изменённых файлов: ${n}. Их версии попадут в резервную копию.`,
      localOnly: "Управление обновлением доступно на компьютере, где запущена Yakumo.",
      tokenTitle: "Токен GitHub · необязательно", tokenHint: "Публичный репозиторий работает без токена. Для закрытого репозитория или увеличения лимита запросов достаточно Contents: read-only.",
      tokenPlaceholder: "Вставьте токен GitHub", save: "Сохранить", clear: "Удалить токен",
      tokenSaved: (hint) => `Токен сохранён (${hint}).`, tokenNone: "Токен не задан.",
      reconnect: "Yakumo перезапускается. Эта страница подключится автоматически…", loading: "Загрузка…",
      error: "Операция не завершена", ready: "Состояние", view: "Посмотреть коммит", files: "файлов",
    },
    en: {
      title: "Project updates", hint: "New Yakumo versions from Aspksa/Yakumo on GitHub.",
      source: "Source", main: "Main branch · main", release: "Published release",
      schedule: "Automatic checks", off: "Off", hourly: "Every hour", daily: "Every day",
      autoHint: "Scheduled checks only look for updates. Use the button to install.",
      installed: "Installed", unknown: "Local copy — determined when checked", latest: "Available version",
      unchecked: "Not checked yet", checked: "Last checked", check: "Check for updates",
      prepare: "Download and verify", install: "Install and restart", rollback: "Restore previous version",
      rollbackHint: "Files being replaced are backed up before every installation.", backup: "Last backup",
      safe: "Settings, keys, Drive files, Python and custom modules are preserved.",
      changed: "Replace", added: "Add", removed: "Remove", preview: "File changes",
      modifications: (n) => `${n} locally modified files. Their versions will be backed up.`,
      localOnly: "Manage updates on the computer running Yakumo.",
      tokenTitle: "GitHub token · optional", tokenHint: "No token is needed for a public repository. Contents: read-only is sufficient for a private repository or a higher rate limit.",
      tokenPlaceholder: "Paste a GitHub token", save: "Save", clear: "Delete token",
      tokenSaved: (hint) => `Token saved (${hint}).`, tokenNone: "No token set.",
      reconnect: "Yakumo is restarting. This page will reconnect automatically…", loading: "Loading…",
      error: "Operation incomplete", ready: "Status", view: "View commit", files: "files",
    },
  };
  let data = null, error = "", waiting = false, tokenDraft = "", timer = null;
  const text = () => words[window.Yakumo.lang()] || words.ru;
  const active = () => location.hash.replace(/^#\/?/, "") === "update";
  const date = (value) => value ? new Date(value * 1000).toLocaleString(window.Yakumo.lang()) : "—";
  const short = (value) => value ? value.slice(0, 10) : "—";
  const bytes = (value) => value > 1024 ** 2 ? `${(value / 1024 ** 2).toFixed(1)} MB` : `${Math.ceil(value / 1024)} KB`;

  async function refresh() {
    try {
      const next = await getJSON("/api/update");
      const changed = JSON.stringify(next) !== JSON.stringify(data) || error;
      data = next;
      error = "";
      if (waiting && ["done", "rolled_back"].includes(data.phase)) {
        const url = new URL(location.href);
        url.searchParams.set("updated", data.job_id || Date.now());
        location.replace(url.href);
        return;
      }
      if (["error", "failed", "recovery_failed"].includes(data.phase)) waiting = false;
      if (active() && changed) window.Yakumo.rerender();
    } catch (e) {
      error = waiting ? text().reconnect : e.message;
      if (active()) window.Yakumo.rerender();
    }
    clearTimeout(timer);
    if (active() || waiting) timer = setTimeout(refresh, data?.busy || waiting ? 1000 : 5000);
  }

  async function action(name, payload = {}) {
    if (name === "install" || name === "rollback") waiting = true;
    error = "";
    try {
      data = await postJSON("/api/update/" + name, payload);
      if (name === "token") tokenDraft = "";
    } catch (e) {
      waiting = false;
      error = e.message;
    }
    window.Yakumo.rerender();
    clearTimeout(timer);
    timer = setTimeout(refresh, 400);
  }

  function option(label, key, choices) {
    return h("label", { class: "up-option" }, h("span", { class: "row-title" }, label),
      h("select", { class: "select", disabled: data.busy || !data.local,
        onchange: (e) => action("settings", { [key]: e.target.value }) },
      Object.entries(choices).map(([value, title]) => h("option", { value, selected: data.settings[key] === value }, title))));
  }

  function render() {
    const T = text();
    if (!timer) timer = setTimeout(refresh, 0);
    if (!data) return [h("h1", {}, T.title), h("p", { class: "subtitle" }, error || T.loading)];
    const disabled = data.busy || waiting || !data.local;
    const button = (label, command, primary, blocked = false) => h("button", {
      class: "btn" + (primary ? " primary" : ""), type: "button", disabled: disabled || blocked,
      onclick: () => action(command),
    }, label);
    const changes = data.changes || {};
    const card = h("section", { class: "card up-main" },
      h("div", { class: "up-status", role: "status", "aria-live": "polite" },
        h("span", { class: "up-indicator " + (data.error ? "bad" : data.busy ? "working" : "") }),
        h("div", {}, h("small", {}, T.ready), h("strong", {}, waiting ? T.reconnect : data.message))),
      h("div", { class: "up-versions" },
        h("div", {}, h("small", {}, T.installed), h("strong", { title: data.current || "" }, data.current ? short(data.current) : T.unknown)),
        h("div", {}, h("small", {}, T.latest), h("strong", {}, short(data.latest?.revision)),
          data.latest?.url ? h("a", { href: data.latest.url, target: "_blank", rel: "noopener noreferrer" }, T.view) : "")),
      data.latest?.message ? h("p", { class: "up-commit" }, data.latest.message) : "",
      h("p", { class: "row-hint" }, `${T.checked}: ${data.last_checked ? date(data.last_checked) : T.unchecked}`));
    if (data.busy && data.done != null) card.append(h("div", { class: "up-progress" },
      h("progress", { max: data.total || Math.max(data.done, 1), value: data.done }),
      h("span", {}, data.phase === "downloading" ? `${bytes(data.done)}${data.total ? " / " + bytes(data.total) : ""}` : `${data.done} / ${data.total} ${T.files}`)));
    if (error || data.error) card.append(h("p", { class: "up-error", role: "alert" }, error || data.error));
    if (data.available) {
      card.append(h("div", { class: "up-counts" },
        ...[[T.changed, changes.changed], [T.added, changes.added], [T.removed, changes.removed]].map(([label, n]) =>
          h("div", {}, h("strong", {}, String(n || 0)), h("span", {}, label)))));
      if (changes.local_modified) card.append(h("p", { class: "row-hint" }, T.modifications(changes.local_modified)));
    }
    card.append(h("div", { class: "up-actions" }, button(T.check, "check"),
      button(T.prepare, "prepare", !data.prepared, !data.available),
      button(T.install, "install", true, !data.prepared || !data.can_install)),
      h("p", { class: "row-hint" }, data.local ? T.safe : T.localOnly));
    const options = h("section", { class: "card up-options" },
      option(T.source, "channel", { main: T.main, release: T.release }),
      option(T.schedule, "schedule", { off: T.off, hourly: T.hourly, daily: T.daily }),
      h("p", { class: "row-hint" }, T.autoHint));
    const restore = h("section", { class: "card up-restore" }, h("h2", {}, T.rollback),
      h("p", { class: "row-hint" }, T.rollbackHint),
      data.backup_date ? h("p", { class: "row-hint" }, `${T.backup}: ${date(data.backup_date)}`) : "",
      button(T.rollback, "rollback", false, !data.can_rollback || !data.can_install));
    const tokenInput = h("input", { class: "text-input", type: "password", autocomplete: "off",
      placeholder: T.tokenPlaceholder, value: tokenDraft, maxlength: "4000", disabled,
      "aria-label": T.tokenTitle, oninput: (e) => { tokenDraft = e.target.value; } });
    const token = h("details", { class: "card up-token" }, h("summary", {}, T.tokenTitle),
      h("p", { class: "row-hint" }, T.tokenHint),
      h("p", { class: "row-hint" }, data.has_token ? T.tokenSaved(data.token_hint) : T.tokenNone),
      h("form", { class: "inline-form", onsubmit: (e) => {
        e.preventDefault(); if (tokenDraft.trim()) action("token", { token: tokenDraft.trim() });
      } }, tokenInput, h("button", { class: "btn", type: "submit", disabled }, T.save),
        data.has_token ? h("button", { class: "btn", type: "button", disabled,
          onclick: () => action("token", { token: "" }) }, T.clear) : ""));
    const result = [h("h1", {}, T.title), h("p", { class: "subtitle" }, T.hint), card, options];
    if (changes.preview?.length) result.push(h("details", { class: "card up-files" }, h("summary", {}, T.preview),
      h("ul", {}, changes.preview.map((p) => h("li", {}, p)))));
    result.push(restore, token);
    return result;
  }

  window.Yakumo.addPage({ id: "update", icon: '<path d="M20 7v5h-5M4 17v-5h5M6.2 7a7 7 0 0 1 11.6-1L20 9M4 15l2.2 3A7 7 0 0 0 17.8 17"/>',
    title: { ru: words.ru.title, en: words.en.title }, render });
  addEventListener("hashchange", () => { if (active()) { clearTimeout(timer); timer = setTimeout(refresh, 0); } });
  if (active()) refresh();
})();
