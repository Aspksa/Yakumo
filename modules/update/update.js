"use strict";

(() => {
  const { h, getJSON } = window.Yakumo;
  const words = {
    ru: {
      title: "Обновление проекта", hint: "Новые версии Yakumo из Aspksa/Yakumo на GitHub.",
      source: "Источник", main: "Основная ветка · main", release: "Опубликованный выпуск",
      schedule: "Автопроверка", off: "Выключена", hourly: "Раз в час", daily: "Раз в день",
      autoHint: "По расписанию проверяется наличие обновления. Установка запускается кнопкой.",
      installed: "Установленная версия", unknown: "Версия локальной копии пока не определена", latest: "Выбранная версия GitHub",
      unchecked: "Ещё не проверялась", checked: "Последняя проверка", check: "Проверить обновления",
      prepare: "Скачать и проверить", install: "Установить и перезапустить", rollback: "Вернуть предыдущую версию",
      rollbackHint: "Перед каждой установкой сохраняется копия заменяемых файлов.", backup: "Последняя резервная копия",
      safe: "Настройки, ключи, файлы «Диска», Python и пользовательские модули сохраняются.",
      changed: "Заменить", added: "Добавить", removed: "Убрать", preview: "Изменения в файлах",
      modifications: (n) => `Локально изменённых файлов: ${n}. Их версии попадут в резервную копию.`,
      localOnly: "Управление обновлением и просмотр локального кода доступны на компьютере с Yakumo.",
      tokenTitle: "Токен GitHub · необязательно", tokenHint: "Публичный репозиторий работает без токена. Для закрытого репозитория или увеличения лимита запросов достаточно Contents: read-only.",
      tokenPlaceholder: "Вставьте токен GitHub", save: "Сохранить", clear: "Удалить токен",
      tokenSaved: (hint) => `Токен сохранён (${hint}).`, tokenNone: "Токен не задан.",
      reconnect: "Yakumo перезапускается. Эта страница подключится автоматически…", loading: "Загрузка…",
      network: "Не удалось связаться с Yakumo. Проверьте, что приложение запущено; страница повторит подключение.",
      ready: "Состояние", view: "Посмотреть коммит", files: "файлов", published: "Дата версии", installedAt: "Учтена локально",
      unpacked: "Размер файлов после распаковки", archive: "Загруженный архив", notes: "Что изменится",
      noNotes: "Автор пока не добавил описание изменений.", commitNotes: "Описание коммита", releaseNotes: "Описание выпуска",
      since: "Коммиты после установленной версии", firstCommits: (n, total) => `Показано первых ${n} из ${total} коммитов.`,
      allChanges: "Открыть сравнение на GitHub", notesUnavailable: "Список коммитов получить не удалось. Проверка файлов выполнена.",
      rateTitle: "Лимит GitHub API", remaining: "Осталось запросов", used: "Использовано", reset: "Восстановление лимита",
      rateUnknown: "Лимит определится после первого ответа GitHub.", observed: "По последнему ответу", retryAt: "Повторить после",
      rateHint: "Просмотр этой страницы не расходует запросы GitHub. Лимит обновляется при проверке и загрузке файлов.",
      rateBlocked: "GitHub временно ограничил запросы. Дождитесь восстановления лимита.",
      whatToDo: "Что делать", errorCode: "Код ошибки", more: "Показать ещё", emptyFiles: "Изменений файлов нет.",
      diff: "Посмотреть правки", close: "Закрыть сравнение", before: "Локальный файл", after: "Выбранный файл",
      diffHint: "Сравнение с файлом на этом компьютере. Зелёные строки добавляются, красные удаляются.",
      diffLarge: "Для этого файла доступен размер без построчного сравнения: предел — 64 КБ и 4000 строк на пару файлов.",
      diffBinary: "Двоичный файл или текст в другой кодировке: показаны размеры.",
      diffFormat: "Текст строк совпадает. Различаются окончания строк, BOM или завершающий перевод строки.",
      diffEqual: "Содержимое файлов уже совпадает.", diffTruncated: "Показана часть изменений. Полный файл доступен в выбранном коммите GitHub.",
      history: "История обновлений", historyHint: "Установки и откаты сохраняются между запусками Yakumo.",
      historyEmpty: "Установок и откатов пока не было.", refresh: "Обновить список", installing: "Установка", restoring: "Ручной откат",
      from: "С версии", to: "На версию", started: "Начало", finished: "Завершение", localCopy: "Локальная копия",
      done: "Успешно", rolled_back: "Выполнен автоматический откат", failed: "Не выполнено", recovery_failed: "Нужно восстановление",
      interrupted: "Операция прервана", ongoing: "Выполняется", speed: "Скорость", seconds: "с", eta: "Осталось примерно",
      sizeUnknown: "Размер архива пока неизвестен", file: "Текущий файл",
    },
    en: {
      title: "Project updates", hint: "New Yakumo versions from Aspksa/Yakumo on GitHub.",
      source: "Source", main: "Main branch · main", release: "Published release",
      schedule: "Automatic checks", off: "Off", hourly: "Every hour", daily: "Every day",
      autoHint: "Scheduled checks only look for updates. Use the button to install.",
      installed: "Installed version", unknown: "Local version has not been identified yet", latest: "Selected GitHub version",
      unchecked: "Not checked yet", checked: "Last checked", check: "Check for updates",
      prepare: "Download and verify", install: "Install and restart", rollback: "Restore previous version",
      rollbackHint: "Files being replaced are backed up before every installation.", backup: "Last backup",
      safe: "Settings, keys, Drive files, Python and custom modules are preserved.",
      changed: "Replace", added: "Add", removed: "Remove", preview: "File changes",
      modifications: (n) => `${n} locally modified files. Their versions will be backed up.`,
      localOnly: "Manage updates and view local code on the computer running Yakumo.",
      tokenTitle: "GitHub token · optional", tokenHint: "No token is needed for a public repository. Contents: read-only is sufficient for a private repository or a higher rate limit.",
      tokenPlaceholder: "Paste a GitHub token", save: "Save", clear: "Delete token",
      tokenSaved: (hint) => `Token saved (${hint}).`, tokenNone: "No token set.",
      reconnect: "Yakumo is restarting. This page will reconnect automatically…", loading: "Loading…",
      network: "Cannot connect to Yakumo. Check that the app is running; this page will retry.",
      ready: "Status", view: "View commit", files: "files", published: "Version date", installedAt: "Recorded locally",
      unpacked: "Unpacked file size", archive: "Downloaded archive", notes: "What's changing",
      noNotes: "The author has not provided change notes yet.", commitNotes: "Commit description", releaseNotes: "Release notes",
      since: "Commits since the installed version", firstCommits: (n, total) => `Showing the first ${n} of ${total} commits.`,
      allChanges: "Compare on GitHub", notesUnavailable: "Could not fetch the commit list. File verification completed.",
      rateTitle: "GitHub API rate limit", remaining: "Requests remaining", used: "Used", reset: "Limit resets",
      rateUnknown: "The limit will appear after the first GitHub response.", observed: "From the latest response", retryAt: "Retry after",
      rateHint: "Viewing this page does not use GitHub requests. Checking and fetching files refreshes the limit.",
      rateBlocked: "GitHub has temporarily limited requests. Wait for the limit to reset.",
      whatToDo: "Next step", errorCode: "Error code", more: "Show more", emptyFiles: "No file changes.",
      diff: "View changes", close: "Close comparison", before: "Local file", after: "Selected file",
      diffHint: "Compared with the file on this computer. Green lines are added; red lines are removed.",
      diffLarge: "Only file sizes are shown: the preview limit is 64 KB and 4000 lines across both files.",
      diffBinary: "Binary file or non-UTF-8 text: file sizes are shown.", diffFormat: "Lines match; line endings, BOM or the final newline differ.",
      diffEqual: "The files already match.", diffTruncated: "Only part of the diff is shown. Find the complete file in the selected GitHub commit.",
      history: "Update history", historyHint: "Installations and rollbacks are saved across Yakumo restarts.",
      historyEmpty: "No installations or rollbacks yet.", refresh: "Refresh list", installing: "Installation", restoring: "Manual rollback",
      from: "From", to: "To", started: "Started", finished: "Finished", localCopy: "Local copy",
      done: "Completed", rolled_back: "Automatically rolled back", failed: "Failed", recovery_failed: "Recovery required",
      interrupted: "Interrupted", ongoing: "In progress", speed: "Speed", seconds: "s", eta: "Estimated remaining",
      sizeUnknown: "Archive size is not known yet", file: "Current file",
    },
  };
  let data = null, error = null, waiting = false, tokenDraft = "", timer = null;
  let fileList = null, fileLoading = false, fileError = null;
  let diff = null, diffPath = "", diffLoading = false, diffError = null;
  let history = null, historyLoading = false, historyError = null;
  const opened = { notes: true, files: false, history: false, token: false };
  const text = () => words[window.Yakumo.lang()] || words.ru;
  const active = () => location.hash.replace(/^#\/?/, "") === "update";
  const repaint = () => { if (active()) window.Yakumo.rerender(); };
  const short = (value) => value ? value.slice(0, 10) : "—";
  const version = (info) => info?.version || (info?.revision ? short(info.revision) : text().localCopy);
  const stamp = () => `${data?.latest?.revision || ""}:${data?.last_checked || ""}`;
  const date = (value) => {
    if (!value) return "—";
    const d = new Date(typeof value === "number" ? value * 1000 : value);
    return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString(window.Yakumo.lang());
  };
  const bytes = (value) => {
    const n = Math.max(0, Number(value) || 0), ru = window.Yakumo.lang() === "ru";
    if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} ${ru ? "МБ" : "MB"}`;
    if (n >= 1024) return `${(n / 1024).toFixed(1)} ${ru ? "КБ" : "KB"}`;
    return `${Math.round(n)} ${ru ? "Б" : "B"}`;
  };
  const normalizeError = (e) => e.detail || { message: e instanceof TypeError ? text().network : e.message };

  async function post(name, payload = {}) {
    const response = await fetch("/api/update/" + name, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (response.status === 401) location.assign("/login");
    const value = await response.json();
    if (!response.ok) throw Object.assign(new Error(value.error || `HTTP ${response.status}`), { detail: value.error_detail });
    return value;
  }

  async function refresh() {
    try {
      const next = await getJSON("/api/update");
      const previousStamp = stamp(), changed = JSON.stringify(next) !== JSON.stringify(data) || error;
      const jobChanged = `${data?.job_id}:${data?.phase}` !== `${next.job_id}:${next.phase}`;
      data = next;
      if (error?.connection) error = null;
      if (stamp() !== previousStamp) { fileList = null; fileError = null; diff = null; diffPath = ""; diffError = null; }
      if (waiting && ["done", "rolled_back"].includes(data.phase)) {
        const url = new URL(location.href);
        url.searchParams.set("updated", data.job_id || Date.now());
        location.replace(url.href); return;
      }
      if (["error", "failed", "recovery_failed"].includes(data.phase)) waiting = false;
      if (changed) repaint();
      if (data.local && opened.files && !fileList && !fileLoading) loadFiles();
      if (data.local && opened.history && (!history || jobChanged) && !historyLoading) loadHistory();
    } catch (e) { error = { ...(waiting ? { message: text().reconnect } : normalizeError(e)), connection: true }; repaint(); }
    clearTimeout(timer);
    if (active() || waiting) timer = setTimeout(refresh, data?.busy || waiting ? 1000 : 5000);
  }

  async function action(name, payload = {}) {
    if (name === "install" || name === "rollback") waiting = true;
    error = null;
    try { data = await post(name, payload); if (name === "token") tokenDraft = ""; }
    catch (e) { waiting = false; error = normalizeError(e); }
    repaint(); clearTimeout(timer); timer = setTimeout(refresh, 400);
  }

  async function loadFiles(more = false) {
    if (fileLoading || !data?.local || !data.latest?.revision) return;
    fileLoading = true; fileError = null;
    const key = stamp(), revision = data.latest.revision;
    repaint();
    try {
      const result = await post("changes", { revision, offset: more ? fileList?.items.length || 0 : 0 });
      if (key === stamp()) fileList = { ...result, items: [...(more ? fileList?.items || [] : []), ...result.items] };
    } catch (e) { fileError = normalizeError(e); }
    finally { fileLoading = false; repaint(); }
  }

  async function loadDiff(path) {
    if (diffLoading || data.busy || waiting) return;
    diffPath = path; diff = null; diffLoading = true; diffError = null;
    const key = stamp(); repaint();
    try {
      const result = await post("diff", { path, revision: data.latest.revision });
      if (key === stamp() && path === diffPath) diff = result;
    } catch (e) { diffError = normalizeError(e); }
    finally { diffLoading = false; repaint(); }
  }

  async function loadHistory(more = false) {
    if (historyLoading || !data?.local) return;
    historyLoading = true; historyError = null; repaint();
    try {
      const result = await post("history", { offset: more ? history?.next_offset || 0 : 0 });
      const items = [...(more ? history?.items || [] : []), ...result.items];
      history = { ...result, items: [...new Map(items.map((item) => [item.id, item])).values()] };
    } catch (e) { historyError = normalizeError(e); }
    finally { historyLoading = false; repaint(); }
  }

  function errorBox(detail) {
    if (!detail) return "";
    const T = text();
    return h("div", { class: "up-error", role: "alert" }, h("strong", {}, detail.message || ""),
      detail.action ? h("p", {}, `${T.whatToDo}: ${detail.action}`) : "",
      detail.retry_at ? h("p", {}, `${T.retryAt}: ${date(detail.retry_at)}`) : "",
      detail.code ? h("small", {}, `${T.errorCode}: ${detail.code}`) : "");
  }

  function detailsCard(key, label, ...children) {
    return h("details", { class: "card up-" + key, open: opened[key], ontoggle: (event) => {
      const isOpen = event.target.open;
      if (isOpen === opened[key]) return;
      opened[key] = isOpen;
      if (isOpen && key === "files" && !fileList) loadFiles();
      if (isOpen && key === "history" && !history) loadHistory();
    } }, h("summary", {}, label), ...children);
  }

  function option(label, key, choices) {
    return h("label", { class: "up-option" }, h("span", { class: "row-title" }, label),
      h("select", { class: "select", disabled: data.busy || waiting || diffLoading || !data.local,
        onchange: (e) => action("settings", { [key]: e.target.value }) },
      Object.entries(choices).map(([value, title]) => h("option", { value, selected: data.settings[key] === value }, title))));
  }

  function progressView() {
    if (!data.busy || data.done == null) return "";
    const T = text(), done = Math.max(0, data.done || 0), total = Math.max(0, data.total || 0);
    const percent = total ? Math.min(100, Math.floor(done / total * 100)) : null;
    const caption = data.unit === "bytes" ? `${bytes(done)}${total ? " / " + bytes(total) : " · " + T.sizeUnknown}` :
      total ? `${done} / ${total} ${data.unit === "files" ? T.files : ""}` : "";
    const rate = data.unit === "bytes" && data.speed > 0 ? `${T.speed}: ${bytes(data.speed)}/${T.seconds}` : "";
    const eta = rate && total > done ? `${T.eta}: ${Math.ceil((total - done) / data.speed)} ${T.seconds}` : "";
    return h("div", { class: "up-progress", "aria-label": data.message },
      h("div", { class: "up-progress-line" }, h("progress", { max: total || 1, value: total ? Math.min(done, total) : null }),
        h("strong", {}, percent == null ? "…" : `${percent}%`)),
      h("p", { class: "row-hint" }, [caption, rate, eta].filter(Boolean).join(" · ")),
      data.current_file ? h("p", { class: "up-path" }, `${T.file}: ${data.current_file}`) : "");
  }

  function notesView() {
    const T = text(), comparison = data.comparison || {};
    return detailsCard("notes", T.notes,
      h("p", { class: "row-hint" }, data.notes_kind === "release" ? T.releaseNotes : T.commitNotes),
      h("div", { class: "up-notes-text" }, data.notes || T.noNotes),
      comparison.commits?.length ? h("div", { class: "up-commits" }, h("h3", {}, T.since),
        h("ol", {}, comparison.commits.map((item) => h("li", {},
          h("a", { href: `https://github.com/${data.repository}/commit/${item.revision}`, target: "_blank", rel: "noopener noreferrer" }, short(item.revision)),
          h("span", { class: "up-commit-message" }, item.message), h("small", {}, date(item.date))))),
        comparison.total > comparison.commits.length ? h("p", { class: "row-hint" }, T.firstCommits(comparison.commits.length, comparison.total)) : "") : "",
      comparison.url ? h("p", {}, h("a", { href: comparison.url, target: "_blank", rel: "noopener noreferrer" }, T.allChanges)) : "",
      data.notes_warning ? h("div", {}, h("p", { class: "row-hint" }, T.notesUnavailable), errorBox(data.notes_warning)) : "");
  }

  function rateView() {
    const T = text(), limit = data.rate_limit || {};
    const until = Math.max(limit.retry_at || 0, limit.remaining === 0 ? limit.reset || 0 : 0);
    return h("section", { class: "card up-rate" }, h("h2", {}, T.rateTitle),
      limit.remaining == null ? h("p", { class: "row-hint" }, T.rateUnknown) : h("div", { class: "up-rate-values" },
        h("div", {}, h("small", {}, T.remaining), h("strong", {}, `${limit.remaining} / ${limit.limit ?? "—"}`)),
        h("div", {}, h("small", {}, T.used), h("strong", {}, String(limit.used ?? "—"))),
        h("div", {}, h("small", {}, T.reset), h("strong", {}, date(limit.reset)))),
      until * 1000 > Date.now() ? h("p", { class: "up-warning" }, `${T.rateBlocked} ${T.retryAt}: ${date(until)}`) : "",
      limit.observed_at ? h("p", { class: "row-hint" }, `${T.observed}: ${date(limit.observed_at)}`) : "", h("p", { class: "row-hint" }, T.rateHint));
  }

  function filesView() {
    const T = text(), changes = data.changes || {};
    const labels = { changed: T.changed, added: T.added, removed: T.removed };
    const block = detailsCard("files", `${T.preview} · ${(changes.changed || 0) + (changes.added || 0) + (changes.removed || 0)}`,
      h("p", { class: "row-hint" }, T.diffHint), errorBox(fileError),
      fileList ? h("ul", { class: "up-file-list" }, fileList.items.map((item) => h("li", {},
        h("span", { class: "up-file-status " + item.status }, labels[item.status] || item.status),
        h("button", { class: "up-file-button", type: "button", disabled: data.busy || waiting || diffLoading,
          title: T.diff, onclick: () => loadDiff(item.path) }, item.path)))) : "",
      fileList && !fileList.total ? h("p", { class: "row-hint" }, T.emptyFiles) : "",
      fileLoading ? h("p", { role: "status" }, T.loading) : "",
      fileList && fileList.items.length < fileList.total ? h("button", { class: "btn", disabled: fileLoading, onclick: () => loadFiles(true) }, T.more) : "");
    if (diffPath) block.append(h("div", { class: "up-diff" },
      h("div", { class: "up-diff-title" }, h("strong", { class: "up-path" }, diffPath),
        h("button", { class: "btn", type: "button", disabled: diffLoading, onclick: () => { diffPath = ""; diff = null; diffError = null; repaint(); } }, T.close)),
      diffLoading ? h("p", { role: "status" }, T.loading) : "", errorBox(diffError),
      diff ? h("p", { class: "row-hint" }, `${T.before}: ${bytes(diff.before_size)} → ${T.after}: ${bytes(diff.after_size)}`) : "",
      diff?.reason ? h("p", { class: "row-hint" }, ({ large: T.diffLarge, binary: T.diffBinary, format: T.diffFormat, equal: T.diffEqual })[diff.reason]) : "",
      diff?.lines.length ? h("pre", { class: "up-diff-code", tabindex: "0", "aria-label": `${T.diff}: ${diffPath}` },
        h("code", {}, diff.lines.map((line) => h("span", { class: "up-line " + line.kind }, line.text || " ")))) : "",
      diff?.truncated ? h("p", { class: "row-hint" }, T.diffTruncated) : "",
      data.latest.url ? h("a", { href: data.latest.url, target: "_blank", rel: "noopener noreferrer" }, T.view) : ""));
    return block;
  }

  function historyView() {
    const T = text();
    return detailsCard("history", T.history, h("p", { class: "row-hint" }, T.historyHint),
      h("button", { class: "btn", type: "button", disabled: historyLoading, onclick: () => loadHistory() }, T.refresh),
      errorBox(historyError), historyLoading ? h("p", { role: "status" }, T.loading) : "",
      history && !history.items.length ? h("p", { class: "row-hint" }, T.historyEmpty) : "",
      h("ol", { class: "up-history-list" }, (history?.items || []).map((item) => h("li", {},
        h("div", { class: "up-history-heading" }, h("strong", {}, item.kind === "rollback" ? T.restoring : T.installing),
          h("span", { class: "up-outcome " + item.phase }, T[item.phase] || T.ongoing)),
        h("p", { class: "up-history-versions" }, `${T.from}: ${version(item.from_version)} → ${T.to}: ${version(item.to_version)}`),
        h("p", { class: "row-hint" }, `${T.started}: ${date(item.started)}${item.finished ? " · " + T.finished + ": " + date(item.finished) : ""}`),
        h("p", {}, item.message || ""), errorBox(item.error_detail)))),
      history && history.next_offset < history.total ? h("button", { class: "btn", type: "button", disabled: historyLoading,
        onclick: () => loadHistory(true) }, T.more) : "");
  }

  function render() {
    const T = text();
    if (!timer) timer = setTimeout(refresh, 0);
    if (!data) return [h("h1", {}, T.title), h("p", { class: "subtitle" }, error?.message || T.loading)];
    const disabled = data.busy || waiting || diffLoading || !data.local;
    const button = (label, command, primary, blocked = false) => h("button", {
      class: "btn" + (primary ? " primary" : ""), type: "button", disabled: disabled || blocked, onclick: () => action(command),
    }, label);
    const changes = data.changes || {}, current = data.current_info || { revision: data.current }, latest = data.latest || {};
    const versionCard = (label, info, isCurrent) => h("div", {}, h("small", {}, label),
      h("strong", { title: info.revision || "" }, info.revision ? version(info) : isCurrent ? T.unknown : "—"),
      info.revision && info.version && info.version !== short(info.revision) ? h("code", {}, short(info.revision)) : "",
      info.date || info.published_at ? h("p", { class: "row-hint" }, `${T.published}: ${date(info.published_at || info.date)}`) : "",
      isCurrent && info.installed_at ? h("p", { class: "row-hint" }, `${T.installedAt}: ${date(info.installed_at)}`) : "",
      !isCurrent && info.size != null ? h("p", { class: "row-hint" }, `${T.unpacked}: ${bytes(info.size)}`) : "",
      !isCurrent && info.archive_size ? h("p", { class: "row-hint" }, `${T.archive}: ${bytes(info.archive_size)}`) : "");
    const card = h("section", { class: "card up-main" },
      h("div", { class: "up-status", role: "status", "aria-live": "polite" },
        h("span", { class: "up-indicator " + (data.error ? "bad" : data.busy ? "working" : "") }),
        h("div", {}, h("small", {}, T.ready), h("strong", {}, waiting ? T.reconnect : data.message))),
      h("div", { class: "up-versions" }, versionCard(T.installed, current, true), versionCard(T.latest, latest, false)),
      latest.url ? h("a", { href: latest.url, target: "_blank", rel: "noopener noreferrer" }, T.view) : "",
      h("p", { class: "row-hint" }, `${T.checked}: ${data.last_checked ? date(data.last_checked) : T.unchecked}`), progressView(),
      errorBox(error || data.error_detail || (data.error ? { message: data.error } : null)));
    if (data.available) {
      card.append(h("div", { class: "up-counts" }, ...[[T.changed, changes.changed], [T.added, changes.added], [T.removed, changes.removed]].map(([label, n]) =>
        h("div", {}, h("strong", {}, String(n || 0)), h("span", {}, label)))));
      if (changes.local_modified) card.append(h("p", { class: "row-hint" }, T.modifications(changes.local_modified)));
    }
    card.append(h("div", { class: "up-actions" }, button(T.check, "check"), button(T.prepare, "prepare", !data.prepared, !data.available),
      button(T.install, "install", true, !data.prepared || !data.can_install)), h("p", { class: "row-hint" }, data.local ? T.safe : T.localOnly));
    const options = h("section", { class: "card up-options" }, option(T.source, "channel", { main: T.main, release: T.release }),
      option(T.schedule, "schedule", { off: T.off, hourly: T.hourly, daily: T.daily }), h("p", { class: "row-hint" }, T.autoHint));
    const restore = h("section", { class: "card up-restore" }, h("h2", {}, T.rollback), h("p", { class: "row-hint" }, T.rollbackHint),
      data.backup_date ? h("p", { class: "row-hint" }, `${T.backup}: ${date(data.backup_date)}`) : "", button(T.rollback, "rollback", false, !data.can_rollback || !data.can_install));
    const tokenInput = h("input", { class: "text-input", type: "password", autocomplete: "off", placeholder: T.tokenPlaceholder, value: tokenDraft,
      maxlength: "4000", disabled, "aria-label": T.tokenTitle, oninput: (e) => { tokenDraft = e.target.value; } });
    const token = detailsCard("token", T.tokenTitle, h("p", { class: "row-hint" }, T.tokenHint),
      h("p", { class: "row-hint" }, data.has_token ? T.tokenSaved(data.token_hint) : T.tokenNone),
      h("form", { class: "inline-form", onsubmit: (e) => { e.preventDefault(); if (tokenDraft.trim()) action("token", { token: tokenDraft.trim() }); } },
        tokenInput, h("button", { class: "btn", type: "submit", disabled }, T.save),
        data.has_token ? h("button", { class: "btn", type: "button", disabled, onclick: () => action("token", { token: "" }) }, T.clear) : ""));
    const result = [h("h1", {}, T.title), h("p", { class: "subtitle" }, T.hint), card];
    if (latest.revision) result.push(notesView());
    if (data.local && data.last_checked) result.push(filesView());
    result.push(rateView(), options);
    if (data.local) result.push(historyView());
    result.push(restore, token);
    return result;
  }

  window.Yakumo.addPage({ id: "update", icon: '<path d="M20 7v5h-5M4 17v-5h5M6.2 7a7 7 0 0 1 11.6-1L20 9M4 15l2.2 3A7 7 0 0 0 17.8 17"/>',
    title: { ru: words.ru.title, en: words.en.title }, render });
  addEventListener("hashchange", () => { if (active()) { clearTimeout(timer); timer = setTimeout(refresh, 0); } });
  if (active()) refresh();
})();
