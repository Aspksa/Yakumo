"use strict";

// «Диск»: файлы и папки как в Яндекс Диске. Страница подключается к веб-версии через Yakumo.addPage.
(() => {
  const { h, icon } = window.Yakumo;

  const TX = {
    ru: {
      title: "Диск", files: "Файлы", shared: "Общий доступ", trash: "Корзина",
      upload: "Загрузить", uploadFiles: "Файлы", uploadFolder: "Папку", newFolder: "Новая папка",
      folderName: "Название папки", create: "Создать", cancel: "Отмена", save: "Сохранить", close: "Закрыть",
      rename: "Переименовать", newName: "Новое имя", move: "Переместить", copy: "Копировать",
      moveHere: "Переместить сюда", copyHere: "Копировать сюда", chooseFolder: "Выберите папку",
      download: "Скачать", share: "Поделиться", del: "Удалить", restore: "Восстановить",
      purge: "Удалить навсегда", emptyTrash: "Очистить корзину", open: "Открыть", clear: "Снять выделение",
      askYakumo: "Спросить Yakumo", askFile: (p) => `Расскажи, что в файле [${p.split("/").pop()}](disk:${p}): главное, сроки и суммы.`,
      askFolder: (p) => `Что важного в папке «${p}»?`, askCompare: (a, b) => `Чем отличаются ${a} и ${b}?`,
      selected: (n) => `Выбрано: ${n}`, search: "Поиск по Диску", searchFound: (n, more) =>
        `Найдено: ${n}${more ? "+" : ""}`, nothingFound: "Ничего не найдено",
      sortBy: "Сортировка", sorts: { name: "По имени", mtime: "По дате", size: "По размеру", kind: "По типу" },
      tiles: "Плитка", list: "Список", name: "Имя", modified: "Изменён", size: "Размер",
      emptyFolder: "Здесь пока пусто", emptyHint: "Перетащите сюда файлы или папки с компьютера или нажмите «Загрузить».",
      emptyTrashText: "Корзина пуста", emptySharedText: "Вы ещё не делились файлами",
      emptySharedHint: "Выберите файл или папку и нажмите «Поделиться», чтобы открыть его по ссылке с телефона или другого компьютера.",
      dropHere: (f) => `Отпустите, чтобы загрузить в «${f}»`,
      usage: (u) => `Занято ${u}`, freeOf: (f, t) => `свободно ${f} из ${t}`, inTrash: (s) => `в корзине ${s}`,
      storedIn: "Хранится в", items: (n) => `${n} ${plural(n, "объект", "объекта", "объектов")}`,
      uploading: (d, n) => `Загрузка: ${d} из ${n}`, uploaded: (n) => `Загружено: ${n}`,
      uploadErrors: (n) => `ошибок: ${n}`, cancelAll: "Отменить",
      deleted: (n) => `В корзину: ${n}`, restored: (n) => `Восстановлено: ${n}`,
      purgeAsk: (n) => `Удалить навсегда ${n} ${plural(n, "объект", "объекта", "объектов")}? Вернуть их будет нельзя.`,
      emptyAsk: "Очистить корзину? Файлы удалятся навсегда.", confirm: "Удалить",
      linkTitle: "Ссылка", linkCopied: "Ссылка скопирована", copyLink: "Копировать ссылку", unshare: "Закрыть доступ",
      linkLan: "Ссылка открывается с телефона и других устройств в этой сети.",
      linkLocal: "Сейчас ссылка работает только на этом компьютере. Чтобы открывать её с телефона, запустите Yakumo с доступом из сети: Yakumo.bat --lan",
      noPreview: "Предпросмотр недоступен", textCut: "Показано начало файла.",
      deletedAt: "Удалён", from: "Откуда", root: "Диск", created: "Создана",
      moved: (n) => `Перемещено: ${n}`, copied: (n) => `Скопировано: ${n}`,
      notFound: "Файл не найден: его переместили или удалили",
      smart: "Умный поиск", inText: "в тексте", onPhoto: "на фото",
      smartText: (n) => `Поиск ищет не только по именам, но и по тексту внутри документов: txt, Word, Excel, PowerPoint, PDF, RTF, книги. Прочитано документов: ${n}.`,
      smartBusy: (d, n) => `Обновляю: ${d} из ${n}`,
      photos: "Распознавать фото через Cloud.ru",
      photosHint: "Фото по очереди отправляются в Cloud.ru, и модель описывает, что на них. Описания хранятся у вас на Диске, по ним работает поиск: «чек», «кошка», «море». Можно выключить в любой момент.",
      photosDone: (n) => `Описано фото: ${n}`, visionModel: (m) => `Модель: ${m}`,
      noCloud: "Сначала подключите Cloud.ru в настройках (раздел Cloud.ru).",
      noVision: "В каталоге Cloud.ru не нашлась модель, которая видит картинки.",
      chatTip: "Ещё можно попросить Yakumo в чате: «найди договор аренды», «перескажи отчёт.pdf», «разложи файлы в папке Загрузки по папкам». Изменения она только предлагает, а выполняются они по кнопке «Выполнить».",
      ocr: "Распознавать текст на сканах и чеках",
      ocrHint: "PDF-сканы без текста и фото документов отправляются в Cloud.ru, текст хранится у вас на Диске. Суммы и даты из чеков и квитанций попадают в «Память» Yakumo.",
      ocrDone: (n) => `Распознано сканов: ${n}`, more: "Ещё",
      order: "Порядок", orderIntro: "Кицунэ смотрит, как вы раскладываете файлы, и предлагает правила. Включённые правила сами раскладывают новые файлы из корня Диска и из «Загрузок».",
      noticed: "Кицунэ заметила привычку",
      noticedText: (label, to, n) => `Вы ${n} ${plural(n, "раз", "раза", "раз")} положили ${label} в «${to}». Делать так всегда?`,
      accept: "Да, сделать правилом", decline: "Не надо", rules: "Правила",
      noRules: "Правил пока нет. Создайте своё или подождите: кицунэ сама предложит, когда заметит привычку.",
      newRule: "Новое правило", editRule: "Изменить правило", ruleWords: "Если в имени или тексте есть слово",
      ruleWordsHint: "через запятую: договор, чек", ruleKinds: "И это", anyKind: "Любой файл",
      ruleTo: "Положить в папку", ruleToHint: "{год} и {месяц} подставятся сами: Финансы/{год}",
      ruleTell: "Написать мне в чат", ruleTellHint: "например: напомни о сроке оплаты", ruleSaved: "Правило сохранено",
      ruleHits: (n) => `сработало ${n} ${plural(n, "раз", "раза", "раз")}`, learned: "выведено кицунэ", fromChat: "из чата",
      kindNames: { pdf: "PDF", doc: "Документ Word", image: "Фото", sheet: "Таблица", text: "Текст", video: "Видео",
                   audio: "Музыка", slides: "Презентация", archive: "Архив", book: "Книга" },
      sortNow: "Разложить по правилам", nothingToSort: "Во «Входящих» нечего раскладывать по правилам",
      sortPlan: (n) => `Разложить: ${n}`, sorted: (n) => `Разложено: ${n}`, lessons: "Чему научилась кицунэ",
      placed: (name, to) => `Кицунэ положила «${name}» в «${to}»`, placedMany: (n) => `Кицунэ разложила файлов: ${n}`,
      names: "Понятные имена", nameOne: "Понятное имя", namesLooking: "Кицунэ придумывает имена…",
      namesNone: "Здесь все имена понятные", namesApply: "Переименовать", renamed: (n) => `Переименовано: ${n}`,
      namesHint: "Отметьте, что переименовать. Имя можно поправить: кицунэ запомнит ваш стиль.",
      askFolderBtn: "Спросить о папке", askOwn: "Свой вопрос о папке", askSend: "Спросить",
      folderQ: ["Что в этой папке главное?", "Какие здесь сроки и суммы?", "Что здесь устарело или повторяется?",
                "Составь опись папки"],
      askAbout: (link, q) => `Папка ${link}: ${q}`,
      summary: "Конспект", summaryBusy: (n) => `Кицунэ читает «${n}» и пишет конспект…`, summaryDone: "Конспект готов",
      related: "Связанное", relatedNone: "Связанных файлов пока нет", relatedFacts: "Кицунэ помнит",
      whyWords: (w) => `общие слова: ${w}`, whyMemory: "через память", whyMeaning: "похоже по смыслу",
      cinema: "Кинорежим", zoomIn: "Увеличить", zoomOut: "Уменьшить", zoomReset: "Вписать",
      sniffing: "Кицунэ ищет…",
    },
    en: {
      title: "Drive", files: "Files", shared: "Shared", trash: "Trash",
      upload: "Upload", uploadFiles: "Files", uploadFolder: "Folder", newFolder: "New folder",
      folderName: "Folder name", create: "Create", cancel: "Cancel", save: "Save", close: "Close",
      rename: "Rename", newName: "New name", move: "Move", copy: "Copy",
      moveHere: "Move here", copyHere: "Copy here", chooseFolder: "Choose a folder",
      download: "Download", share: "Share", del: "Delete", restore: "Restore",
      purge: "Delete forever", emptyTrash: "Empty trash", open: "Open", clear: "Clear selection",
      askYakumo: "Ask Yakumo", askFile: (p) => `What's in [${p.split("/").pop()}](disk:${p})? Key points, deadlines and amounts.`,
      askFolder: (p) => `What's important in the folder “${p}”?`, askCompare: (a, b) => `How do ${a} and ${b} differ?`,
      selected: (n) => `${n} selected`, search: "Search Drive", searchFound: (n, more) =>
        `Found: ${n}${more ? "+" : ""}`, nothingFound: "Nothing found",
      sortBy: "Sort", sorts: { name: "Name", mtime: "Date", size: "Size", kind: "Type" },
      tiles: "Tiles", list: "List", name: "Name", modified: "Modified", size: "Size",
      emptyFolder: "Nothing here yet", emptyHint: "Drop files or folders here, or press Upload.",
      emptyTrashText: "Trash is empty", emptySharedText: "Nothing shared yet",
      emptySharedHint: "Select a file or folder and press Share to open it by link from a phone or another computer.",
      dropHere: (f) => `Drop to upload to “${f}”`,
      usage: (u) => `Used ${u}`, freeOf: (f, t) => `${f} free of ${t}`, inTrash: (s) => `${s} in trash`,
      storedIn: "Stored in", items: (n) => `${n} ${n === 1 ? "item" : "items"}`,
      uploading: (d, n) => `Uploading: ${d} of ${n}`, uploaded: (n) => `Uploaded: ${n}`,
      uploadErrors: (n) => `errors: ${n}`, cancelAll: "Cancel",
      deleted: (n) => `Moved to trash: ${n}`, restored: (n) => `Restored: ${n}`,
      purgeAsk: (n) => `Delete ${n} ${n === 1 ? "item" : "items"} forever? This can't be undone.`,
      emptyAsk: "Empty the trash? Files will be deleted forever.", confirm: "Delete",
      linkTitle: "Link", linkCopied: "Link copied", copyLink: "Copy link", unshare: "Stop sharing",
      linkLan: "The link opens from phones and other devices on this network.",
      linkLocal: "Right now the link only works on this computer. To open it from a phone, start Yakumo with network access: Yakumo.bat --lan",
      noPreview: "No preview available", textCut: "Showing the beginning of the file.",
      deletedAt: "Deleted", from: "From", root: "Drive", created: "Created",
      moved: (n) => `Moved: ${n}`, copied: (n) => `Copied: ${n}`,
      notFound: "File not found: it was moved or deleted",
      smart: "Smart search", inText: "in text", onPhoto: "in photo",
      smartText: (n) => `Search looks not only at names but also at the text inside documents: txt, Word, Excel, PowerPoint, PDF, RTF, books. Documents read: ${n}.`,
      smartBusy: (d, n) => `Updating: ${d} of ${n}`,
      photos: "Recognise photos with Cloud.ru",
      photosHint: "Photos are sent to Cloud.ru one by one and the model describes them. Descriptions are stored on your Drive and make search work: “receipt”, “cat”, “sea”. You can turn it off any time.",
      photosDone: (n) => `Photos described: ${n}`, visionModel: (m) => `Model: ${m}`,
      noCloud: "Connect Cloud.ru in Settings first.",
      noVision: "The Cloud.ru catalog has no model that can see images.",
      chatTip: "You can also ask Yakumo in the chat: “find the lease”, “summarise report.pdf”, “sort the Downloads folder”. She only proposes changes; they run when you press Run.",
      ocr: "Recognise text on scans and receipts",
      ocrHint: "PDF scans without text and photos of documents are sent to Cloud.ru; the text is stored on your Drive. Amounts and dates from receipts go to Yakumo's Memory.",
      ocrDone: (n) => `Scans recognised: ${n}`, more: "More",
      order: "Order", orderIntro: "The kitsune watches how you sort files and suggests rules. Enabled rules sort new files from the Drive root and Downloads by themselves.",
      noticed: "The kitsune noticed a habit",
      noticedText: (label, to, n) => `You put ${label} into “${to}” ${n} times. Always do that?`,
      accept: "Yes, make it a rule", decline: "No thanks", rules: "Rules",
      noRules: "No rules yet. Create one, or wait: the kitsune will suggest one when she notices a habit.",
      newRule: "New rule", editRule: "Edit rule", ruleWords: "If the name or text contains a word",
      ruleWordsHint: "comma-separated: contract, receipt", ruleKinds: "And it is", anyKind: "Any file",
      ruleTo: "Put into folder", ruleToHint: "{year} and {month} are filled in: Finance/{year}",
      ruleTell: "Tell me in the chat", ruleTellHint: "e.g. remind me of the due date", ruleSaved: "Rule saved",
      ruleHits: (n) => `used ${n} times`, learned: "worked out by the kitsune", fromChat: "from the chat",
      kindNames: { pdf: "PDF", doc: "Word document", image: "Photo", sheet: "Spreadsheet", text: "Text", video: "Video",
                   audio: "Music", slides: "Presentation", archive: "Archive", book: "Book" },
      sortNow: "Sort by rules", nothingToSort: "Nothing in the inbox matches a rule",
      sortPlan: (n) => `Sort: ${n}`, sorted: (n) => `Sorted: ${n}`, lessons: "What the kitsune learned",
      placed: (name, to) => `The kitsune put “${name}” into “${to}”`, placedMany: (n) => `The kitsune sorted ${n} files`,
      names: "Clear names", nameOne: "Clear name", namesLooking: "The kitsune is thinking of names…",
      namesNone: "All names here are clear", namesApply: "Rename", renamed: (n) => `Renamed: ${n}`,
      namesHint: "Tick what to rename. You can edit a name: the kitsune will learn your style.",
      askFolderBtn: "Ask about the folder", askOwn: "Your question about the folder", askSend: "Ask",
      folderQ: ["What's important in this folder?", "What deadlines and amounts are here?",
                "What is outdated or duplicated here?", "Make an inventory of the folder"],
      askAbout: (link, q) => `Folder ${link}: ${q}`,
      summary: "Summary", summaryBusy: (n) => `The kitsune is reading “${n}” and writing a summary…`,
      summaryDone: "Summary ready",
      related: "Related", relatedNone: "No related files yet", relatedFacts: "The kitsune remembers",
      whyWords: (w) => `shared words: ${w}`, whyMemory: "through memory", whyMeaning: "similar meaning",
      cinema: "Cinema mode", zoomIn: "Zoom in", zoomOut: "Zoom out", zoomReset: "Fit",
      sniffing: "The kitsune is searching…",
    },
  };
  let L = TX.ru;

  function plural(n, one, few, many) {
    const m10 = n % 10, m100 = n % 100;
    if (m10 === 1 && m100 !== 11) return one;
    if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
    return many;
  }

  // --- Значки ---
  const ICONS = {
    "dk-folder": '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2h8.5A1.5 1.5 0 0 1 21 8.5v10a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5z"/>',
    "dk-file": '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/>',
    "dk-ask": '<path d="M4 5h16v11H9l-5 4z"/><path d="M9 9.5h6M9 12.5h4"/>',
    "dk-image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="9.5" r="1.8"/><path d="m21 16-5-5-9 9"/>',
    "dk-video": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m10 9 5 3-5 3z"/>',
    "dk-audio": '<path d="M9 18V6l11-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
    "dk-pdf": '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 16.5h4"/>',
    "dk-text": '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5M9 12h6M9 15h6M9 18h4"/>',
    "dk-doc": '<path d="M6 3h8l5 5v13H6z"/><path d="m8.5 12 1.3 6 1.7-4.5 1.7 4.5 1.3-6"/>',
    "dk-sheet": '<path d="M6 3h8l5 5v13H6z"/><path d="M9 12h7v6H9zM9 15h7M12.5 12v6"/>',
    "dk-slides": '<path d="M6 3h8l5 5v13H6z"/><path d="M9.5 18v-6h2.5a2 2 0 0 1 0 4H9.5"/>',
    "dk-archive": '<path d="M6 3h12v18H6z"/><path d="M12 3v2m0 2v2m0 2v2"/><rect x="10.5" y="13" width="3" height="4" rx="1"/>',
    "dk-book": '<path d="M5 4h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H5zM19 4h-4a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h4z"/>',
    "dk-app": '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M4 9h16"/>',
    "dk-upload": '<path d="M12 16V4m-5 5 5-5 5 5"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
    "dk-download": '<path d="M12 4v12m-5-5 5 5 5-5"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
    "dk-newfolder": '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2h8.5A1.5 1.5 0 0 1 21 8.5v10a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5z"/><path d="M12 11v6m-3-3h6"/>',
    "dk-share": '<circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="m8.2 10.8 7.6-4.6m-7.6 7 7.6 4.6"/>',
    "dk-link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "dk-rename": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
    "dk-move": '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2h8.5A1.5 1.5 0 0 1 21 8.5v10a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5z"/><path d="M9 13.5h6m-2.5-2.5 2.5 2.5-2.5 2.5"/>',
    "dk-copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
    "dk-trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "dk-restore": '<path d="M4 11a8 8 0 1 1 2.3 5.7"/><path d="M4 4v7h7"/>',
    "dk-tiles": '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    "dk-list": '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
    "dk-search": '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4"/>',
    "dk-up": '<path d="m6 15 6-6 6 6"/>', "dk-down": '<path d="m6 9 6 6 6-6"/>',
    "dk-prev": '<path d="m15 5-7 7 7 7"/>', "dk-next": '<path d="m9 5 7 7-7 7"/>',
    "dk-x": '<path d="M6 6l12 12M18 6 6 18"/>', "dk-check": '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    "dk-spark": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
    "dk-more": '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
    "dk-fox": '<path d="M4 4.5 8.5 9h7L20 4.5l-1 8.5-7 7-7-7z"/><path d="M9.5 12.5h.01M14.5 12.5h.01M11 16.2l1 .8 1-.8"/>',
    "dk-wand": '<path d="m4 20 11-11"/><path d="m13 7 2-2 4 4-2 2"/><path d="M18 2.5v3M16.5 4h3M6 4v2M5 5h2M20 14v2M19 15h2"/>',
    "dk-related": '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="8" r="2.5"/><circle cx="9" cy="18" r="2.5"/><path d="M8.4 6.6 15.6 7.4M7 8.4l1.5 7.2M16.4 10l-5.6 6"/>',
    "dk-summary": '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5M9 12h4M9 15h6M9 18h3"/><path d="m16.5 14.5.6 1.4 1.4.6-1.4.6-.6 1.4-.6-1.4-1.4-.6 1.4-.6z"/>',
    "dk-cinema": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 9h18M3 15h18M7 5v4M12 5v4M17 5v4M7 15v4M12 15v4M17 15v4"/>',
    "dk-zoomin": '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4M11 8v6M8 11h6"/>',
    "dk-zoomout": '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4M8 11h6"/>',
    "dk-fit": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
  };
  const sprite = document.querySelector("svg symbol").parentNode;
  for (const [id, body] of Object.entries(ICONS)) {
    const sym = document.createElementNS("http://www.w3.org/2000/svg", "symbol");
    sym.id = "i-" + id;
    sym.setAttribute("viewBox", "0 0 24 24");
    sym.innerHTML = body;
    sprite.append(sym);
  }
  const kindIcon = (kind) => icon("i-dk-" + (kind === "folder" ? "folder" : ICONS["dk-" + kind] ? kind : "file"));

  // --- Кицунэ: векторная лисичка с файлом в зубах (анимации и вкладка «Порядок») ---
  const FOX = `<svg viewBox="0 0 100 64" aria-hidden="true">
    <defs>
      <linearGradient id="dkfox-fur" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f8bd5c"/><stop offset="1" stop-color="#d8692a"/></linearGradient>
      <linearGradient id="dkfox-tail" x1="1" y1="0" x2="0" y2="0"><stop offset="0" stop-color="#d8692a"/><stop offset=".72" stop-color="#f4a94c"/><stop offset=".8" stop-color="#fff3df"/></linearGradient>
    </defs>
    <g class="dk-fox-tails">
      <path d="M34 38C22 40 8 36 3 24c8 5 18 3 27 7 3 1 5 4 4 7z" fill="url(#dkfox-tail)" opacity=".45"/>
      <path d="M34 37C23 34 12 26 10 14c6 7 15 8 22 14 3 2 4 6 2 9z" fill="url(#dkfox-tail)" opacity=".7"/>
      <path d="M34 38C22 37 9 31 5 20c7 6 17 6 25 11 3 2 5 4 4 7z" fill="url(#dkfox-tail)"/>
    </g>
    <g class="dk-fox-legs" fill="#b4531f">
      <path class="dk-leg-a" d="M59 43l5 11h3.5l-4.5-12z"/><path class="dk-leg-b" d="M52 45l-2 11h3.5l3-11z"/>
      <path class="dk-leg-b" d="M39 44l-8 9 3 2.5 9-10z"/><path class="dk-leg-a" d="M45 46v11h3.5l1-11z"/>
    </g>
    <path d="M31 38c0-9 13-13 25-12 10 1 15 6 13 12-2 6-11 10-24 10-8 0-14-3-14-10z" fill="url(#dkfox-fur)"/>
    <path d="M46 47c6 0 13-1 18-4-3 5-11 7-18 4z" fill="#fff3df" opacity=".85"/>
    <path d="M62 30c1-8 9-13 18-11l9 6c2 2 1 4-2 4l-6 2c-4 4-12 5-17 3z" fill="url(#dkfox-fur)"/>
    <path d="M67 22l2-13 8 9zM74 18.5l5-12 2 13z" fill="#d8692a"/>
    <path d="M69 19l1.2-6 3.5 4.2zM75.6 16.5l2.4-5.6 1 6.4z" fill="#3b2415"/>
    <path d="M75 29c4 1 8 0 11 0-3 3-8 4-11 1z" fill="#fff3df"/>
    <path d="M76.5 23.2q1.8-1.6 3.4 0" fill="none" stroke="#2a1a0e" stroke-width="1.3" stroke-linecap="round"/>
    <circle cx="89" cy="25.6" r="1.4" fill="#2a1a0e"/>
    <g class="dk-fox-file">
      <path d="M85 25h9l3.5 3.5V40H85z" fill="#fffdf8" stroke="#cbb89a" stroke-width=".8"/>
      <path d="M94 25v3.5h3.5" fill="none" stroke="#cbb89a" stroke-width=".8"/>
      <path d="M87.5 31.5h7.5M87.5 34h7.5M87.5 36.5h5" stroke="rgb(var(--accent-rgb))" stroke-width="1.1"/>
    </g>
  </svg>`;
  function foxArt(cls = "") {
    const el = h("span", { class: "dk-fox-pic " + cls, "aria-hidden": "true" });
    el.innerHTML = FOX;
    return el;
  }
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

  // Кицунэ «приносит» файл: бежит дугой от кнопки или окна загрузки к папке, где он теперь лежит.
  function flyFox(fromEl, toEl) {
    if (!toEl) return;
    const flash = () => { toEl.classList.remove("dk-arrived"); void toEl.offsetWidth; toEl.classList.add("dk-arrived"); };
    const a = fromEl?.getBoundingClientRect(), b = toEl.getBoundingClientRect();
    if (reducedMotion.matches || !a || !a.width || !toEl.animate) return flash();
    const fox = foxArt("dk-fox-runner");
    document.body.append(fox);
    const x0 = a.left + a.width / 2 - 40, y0 = a.top + a.height / 2 - 26;
    const x1 = b.left + b.width / 2 - 40, y1 = b.top + b.height / 2 - 30;
    const flip = x1 < x0 ? -1 : 1;
    const frames = [];
    for (let i = 0; i <= 16; i++) {
      const t = i / 16;
      const hop = Math.abs(Math.sin(Math.PI * t * 5)) * 7;  // скачки на бегу
      frames.push({ transform: `translate(${x0 + (x1 - x0) * t}px, ${y0 + (y1 - y0) * t - Math.sin(Math.PI * t) * 90 - hop}px) scaleX(${flip})`,
                    opacity: i === 0 || i === 16 ? 0 : 1 });
    }
    fox.animate(frames, { duration: 1200, easing: "ease-in-out" }).onfinish = () => { fox.remove(); flash(); };
  }

  // Куда «бежать»: плитка папки в открытом списке (или её родителя), иначе вкладка «Порядок».
  function targetEl(folder) {
    const parts = folder.split("/");
    for (let i = parts.length; i > 0; i--) {
      const el = root.querySelector(`.dk-item[data-key="${CSS.escape(parts.slice(0, i).join("/"))}"]`);
      if (el) return el;
    }
    return root.querySelector('.dk-tablist [data-view="order"]');
  }

  function foxCarry(placed, fromEl) {
    if (!placed.length) return;
    toast(placed.length === 1 ? L.placed(placed[0].name, placed[0].to) : L.placedMany(placed.length));
    flyFox(fromEl, targetEl(placed[0].to));
  }

  // --- Состояние ---

  function stored(key, fallback) {
    try { return JSON.parse(localStorage.getItem("yakumo.disk." + key)) ?? fallback; } catch { return fallback; }
  }
  function store(key, value) {
    try { localStorage.setItem("yakumo.disk." + key, JSON.stringify(value)); } catch { /* приватный режим */ }
  }

  const state = {
    view: "files",              // files | shared | trash
    path: stored("path", ""),   // текущая папка, относительно корня Диска
    items: [], trash: [], shares: [],
    selected: new Set(), anchor: null,
    query: "", found: null,     // поиск: null — не ищем
    sort: stored("sort", { key: "name", dir: 1 }),
    layout: stored("layout", "tiles"),
    info: null, loading: false, error: null,
    order: null,                // правила, предложения и уроки кицунэ
    fresh: false,               // результаты поиска только что пришли: подсветить
  };
  const root = h("div", { class: "disk" });
  let started = false;

  // --- Запросы ---

  async function get(name, params = {}) {
    const r = await fetch(`/api/disk/${name}?${new URLSearchParams(params)}`, { cache: "no-store" });
    const res = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(res.error || `HTTP ${r.status}`), { status: r.status });
    return res;
  }
  const post = (name, data) => window.Yakumo.postJSON(`/api/disk/${name}`, data);
  const fileUrl = (path, download) =>
    `/api/disk/file?path=${encodeURIComponent(path)}${download ? "&download=1" : ""}`;

  async function refreshInfo() {
    try { state.info = await get("info"); } catch { /* покажем без места */ }
    const bar = root.querySelector(".dk-usage");
    if (bar) bar.replaceWith(usageEl());
    refreshOrder();
  }

  async function refreshOrder() {
    try { state.order = await get("order"); } catch { return; }
    if (state.view === "order") return draw();
    const tab = root.querySelector('.dk-tablist [data-view="order"]');
    if (tab) tab.replaceWith(orderTab());
  }

  async function load() {
    state.loading = true;
    try {
      if (state.view === "files") {
        try {
          const res = await get("list", { path: state.path });
          state.items = res.items;
        } catch (e) {
          if (e.status !== 404 || !state.path) throw e;
          state.path = "";  // папку удалили или переименовали снаружи
          state.items = (await get("list", { path: "" })).items;
        }
        if (state.query) await runSearch();
      } else if (state.view === "order") {
        state.order = await get("order");
      } else if (state.view === "trash") {
        state.trash = await get("trash");
      } else {
        state.shares = await get("shares");
      }
      state.error = null;
    } catch (e) {
      state.error = e.message;
    }
    state.loading = false;
    const keep = new Set(currentItems().map((i) => keyOf(i)));
    state.selected = new Set([...state.selected].filter((k) => keep.has(k)));
    draw();
  }

  async function runSearch() {
    if (!state.query.trim()) { state.found = null; return; }
    try { state.found = await get("search", { q: state.query }); state.fresh = true; } catch (e) { toast(e.message, true); }
  }

  // --- Форматы ---

  const lang = () => window.Yakumo.lang();
  function size(n) {
    if (n == null) return "";
    const units = lang() === "ru" ? ["Б", "КБ", "МБ", "ГБ", "ТБ"] : ["B", "KB", "MB", "GB", "TB"];
    let i = 0;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
    return `${new Intl.NumberFormat(lang(), { maximumFractionDigits: i ? 1 : 0 }).format(n)} ${units[i]}`;
  }
  const date = (t) => new Date(t * 1000).toLocaleString(lang(),
    { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  const parentOf = (path) => path.split("/").slice(0, -1).join("/");
  const baseName = (path) => path.split("/").pop() || L.root;

  function sorted(items) {
    const { key, dir } = state.sort;
    const coll = new Intl.Collator(lang(), { numeric: true, sensitivity: "base" });
    return [...items].sort((a, b) => {
      if (a.dir !== b.dir) return a.dir ? -1 : 1;  // папки всегда сверху
      let c = 0;
      if (key === "mtime") c = a.mtime - b.mtime;
      else if (key === "size") c = (a.size || 0) - (b.size || 0);
      else if (key === "kind") c = coll.compare(a.kind, b.kind);
      return (c || coll.compare(a.name, b.name)) * dir;
    });
  }

  const keyOf = (item) => item.id || item.token || item.path;
  function currentItems() {
    if (state.view === "order") return [];
    if (state.view === "trash") return state.trash;
    if (state.view === "shared") return state.shares;
    return sorted(state.found ? state.found.items : state.items);
  }
  const selectedItems = () => currentItems().filter((i) => state.selected.has(keyOf(i)));

  // --- Отрисовка ---

  function button(iconId, label, onclick, { primary = false, iconOnly = false, cls = "" } = {}) {
    const b = h("button", { type: "button", class: `btn dk-btn ${primary ? "primary" : ""} ${cls}`,
                            title: label, "aria-label": label, onclick });
    b.append(icon("i-" + iconId));
    if (!iconOnly) b.append(h("span", {}, label));
    return b;
  }

  function usageEl() {
    const i = state.info;
    if (!i) return h("div", { class: "dk-usage" });
    const usedAll = i.total - i.free;
    const pct = (v) => `${Math.max(0, Math.min(100, (v / i.total) * 100)).toFixed(2)}%`;
    return h("div", { class: "dk-usage" },
      h("div", { class: "dk-meter", role: "meter", "aria-valuemin": 0, "aria-valuemax": i.total,
                 "aria-valuenow": usedAll, "aria-label": L.usage(size(i.used + i.trash)) },
        h("span", { class: "dk-meter-disk", style: `width:${pct(i.used + i.trash)}` }),
        h("span", { class: "dk-meter-other", style: `width:${pct(usedAll - i.used - i.trash)}` })),
      h("div", { class: "dk-usage-text" },
        h("strong", {}, L.usage(size(i.used))), " · ", L.freeOf(size(i.free), size(i.total)),
        i.trash ? ` · ${L.inTrash(size(i.trash))}` : ""),
      h("div", { class: "dk-root", title: i.root }, `${L.storedIn}: ${i.root}`));
  }

  function tabs() {
    const tab = (id, iconId) => tabEl(id, iconId);
    const search = h("input", {
      type: "search", class: "text-input dk-search-input", placeholder: L.search, "aria-label": L.search,
      value: state.query,
      oninput: (e) => {
        state.query = e.target.value;
        clearTimeout(searchTimer);
        searchTimer = setTimeout(async () => {
          if (state.view !== "files") state.view = "files";
          await runSearch();
          draw(true);
        }, 300);
      },
      onkeydown: (e) => { if (e.key === "Escape") { state.query = ""; state.found = null; draw(); } },
    });
    const box = h("label", { class: "dk-search" }, search);
    box.prepend(icon("i-dk-search"));
    return h("div", { class: "dk-tabs" },
      h("div", { class: "dk-tablist", role: "tablist" },
        tab("files", "dk-folder"), orderTab(), tab("shared", "dk-link"), tab("trash", "dk-trash")),
      h("div", { class: "dk-searchrow" }, box, button("dk-spark", L.smart, smartDialog, { iconOnly: true })));
  }
  let searchTimer = 0;

  function tabEl(id, iconId, badge = 0) {
    const b = h("button", { type: "button", role: "tab", "aria-selected": String(state.view === id), "data-view": id,
                            class: state.view === id ? "on" : "", "aria-label": L[id], onclick: () => setView(id) });
    b.append(icon("i-" + iconId), h("span", {}, L[id]));
    if (badge) b.append(h("b", { class: "dk-badge" }, String(badge)));
    return b;
  }
  const orderTab = () => tabEl("order", "dk-fox", state.order?.proposals.length || 0);

  function crumbs() {
    const parts = state.path ? state.path.split("/") : [];
    const nav = h("nav", { class: "dk-crumbs", "aria-label": L.files });
    const add = (label, path, last) => {
      const el = last ? h("span", { class: "dk-crumb cur", "aria-current": "page" }, label)
        : h("button", { type: "button", class: "dk-crumb", onclick: () => go(path) }, label);
      if (!last) dropTarget(el, path);
      nav.append(el);
      if (!last) nav.append(h("span", { class: "dk-sep" }, "/"));
    };
    add(L.root, "", !parts.length);
    parts.forEach((p, i) => add(p, parts.slice(0, i + 1).join("/"), i === parts.length - 1));
    return nav;
  }

  function toolbar() {
    if (state.selected.size) return selectionBar();
    if (state.view === "trash") {
      return h("div", { class: "dk-bar" }, h("div", { class: "dk-bar-title" }, L.trash),
        state.trash.length ? button("dk-trash", L.emptyTrash, emptyTrash) : "");
    }
    if (state.view === "shared") return h("div", { class: "dk-bar" }, h("div", { class: "dk-bar-title" }, L.shared));
    if (state.view === "order") {
      return h("div", { class: "dk-bar" }, h("div", { class: "dk-bar-title" }, L.order),
        h("div", { class: "dk-actions" }, button("dk-fox", L.sortNow, sortNow),
          button("dk-spark", L.newRule, () => ruleDialog(), { primary: true })));
    }
    const sortSel = h("select", { class: "select dk-sort", "aria-label": L.sortBy,
                                   onchange: (e) => setSort({ key: e.target.value, dir: state.sort.dir }) },
      Object.entries(L.sorts).map(([k, v]) => h("option", { value: k, selected: k === state.sort.key }, v)));
    const head = state.found
      ? h("div", { class: "dk-bar-title dk-found-title" }, icon("i-dk-fox"),
          L.searchFound(state.found.items.length, state.found.more))
      : crumbs();
    const more = button("dk-more", L.more, (e) => {
      e.stopPropagation();
      openMenu(e.currentTarget, [
        { icon: "dk-wand", label: L.names, run: () => namesDialog(state.path) },
        { icon: "dk-fox", label: L.sortNow, run: sortNow },
      ]);
    }, { iconOnly: true });
    return h("div", { class: "dk-bar" }, head,
      h("div", { class: "dk-actions" },
        uploadButton(),
        button("dk-newfolder", L.newFolder, newFolder, { iconOnly: true }),
        window.Yakumo.ask ? button("dk-ask", L.askFolderBtn, () => askFolderDialog(state.path), { iconOnly: true }) : "",
        sortSel,
        button(state.sort.dir > 0 ? "dk-up" : "dk-down", L.sortBy,
               () => setSort({ key: state.sort.key, dir: -state.sort.dir }), { iconOnly: true }),
        button(state.layout === "tiles" ? "dk-list" : "dk-tiles", state.layout === "tiles" ? L.list : L.tiles,
               () => { state.layout = state.layout === "tiles" ? "list" : "tiles"; store("layout", state.layout); draw(); },
               { iconOnly: true }),
        more));
  }

  const fileInput = h("input", { type: "file", multiple: true, hidden: true,
                                 onchange: (e) => { pickFiles(e.target.files); e.target.value = ""; } });
  const folderInput = h("input", { type: "file", multiple: true, webkitdirectory: true, hidden: true,
                                   onchange: (e) => { pickFiles(e.target.files); e.target.value = ""; } });
  function pickFiles(list) {
    enqueue([...list].map((f) => ({ file: f, rel: f.webkitRelativePath || f.name })), state.path);
  }

  function uploadButton() {
    const wrap = h("div", { class: "dk-upload" });
    const main = button("dk-upload", L.upload, () => fileInput.click(), { primary: true });
    const more = h("button", { type: "button", class: "btn primary dk-upload-more", "aria-label": L.uploadFolder,
                               title: L.uploadFolder, onclick: (e) => {
                                 e.stopPropagation();
                                 openMenu(e.currentTarget, [
                                   { icon: "dk-file", label: L.uploadFiles, run: () => fileInput.click() },
                                   { icon: "dk-folder", label: L.uploadFolder, run: () => folderInput.click() },
                                 ]);
                               } });
    more.append(icon("i-dk-down"));
    wrap.append(main, more, fileInput, folderInput);
    return wrap;
  }

  // Выделение меняет только отметки и строку действий: список не перерисовывается,
  // иначе второй щелчок двойного нажатия попал бы в новый элемент.
  function showSelection() {
    for (const el of root.querySelectorAll(".dk-item")) {
      const on = state.selected.has(el.dataset.key);
      el.classList.toggle("on", on);
      el.setAttribute("aria-selected", String(on));
      el.querySelector(".dk-check").setAttribute("aria-checked", String(on));
    }
    root.querySelector(".dk-bar")?.replaceWith(toolbar());
  }

  function selectionBar() {
    const sel = selectedItems();
    const bar = h("div", { class: "dk-bar dk-selbar", role: "toolbar", "aria-label": L.selected(sel.length) },
      h("span", { class: "dk-selcount" }, L.selected(sel.length)));
    const actions = actionsFor(sel), extra = actions.filter((a) => a.extra);
    for (const a of actions) if (!a.extra) bar.append(button(a.icon, a.label, a.run, { cls: a.danger ? "danger" : "" }));
    if (extra.length) {
      bar.append(button("dk-more", L.more, (e) => { e.stopPropagation(); openMenu(e.currentTarget, extra); },
                        { iconOnly: true }));
    }
    bar.append(button("dk-x", L.clear, () => { state.selected.clear(); showSelection(); }, { iconOnly: true }));
    return bar;
  }

  function actionsFor(sel) {
    const one = sel.length === 1 ? sel[0] : null;
    if (state.view === "trash") {
      return [
        { icon: "dk-restore", label: L.restore, run: () => restore(sel) },
        { icon: "dk-trash", label: L.purge, run: () => purge(sel), danger: true },
      ];
    }
    if (state.view === "shared") {
      return [
        ...(one ? [{ icon: "dk-link", label: L.copyLink, run: () => copy(linkFor(one.token), L.linkCopied) },
                   { icon: "dk-download", label: L.download, run: () => download(sel) }] : []),
        { icon: "dk-x", label: L.unshare, run: () => unshare(sel), danger: true },
      ];
    }
    return [
      ...(one && !one.dir ? [{ icon: "dk-file", label: L.open, run: () => open(one) }] : []),
      ...(askable(sel) ? [{ icon: "dk-ask", label: L.askYakumo, run: () => askYakumo(sel) }] : []),
      ...(one && !one.dir ? [{ icon: "dk-related", label: L.related, run: () => { sideOn = true; open(one); }, extra: true }] : []),
      ...(one && DOCS.has(one.kind) ? [{ icon: "dk-summary", label: L.summary, run: () => summarize(one), extra: true }] : []),
      ...(one ? [{ icon: "dk-wand", label: one.dir ? L.names : L.nameOne, run: () => namesDialog(one.path), extra: true }] : []),
      { icon: "dk-download", label: L.download, run: () => download(sel) },
      ...(one ? [{ icon: "dk-share", label: L.share, run: () => share(one), extra: true },
                 { icon: "dk-rename", label: L.rename, run: () => rename(one) }] : []),
      { icon: "dk-move", label: L.move, run: () => moveDialog(sel, false) },
      { icon: "dk-copy", label: L.copy, run: () => moveDialog(sel, true), extra: true },
      { icon: "dk-trash", label: L.del, run: () => remove(sel), danger: true },
    ];
  }

  function itemEl(item, index, items) {
    const key = keyOf(item);
    const on = state.selected.has(key);
    const thumb = h("span", { class: "dk-thumb", "data-kind": item.kind });
    if (item.kind === "image" && state.view === "files" && state.layout === "tiles") {
      thumb.append(h("img", { src: fileUrl(item.path), alt: "", loading: "lazy", decoding: "async", draggable: "false",
                              onerror: (e) => e.target.replaceWith(kindIcon(item.kind)) }));
    } else {
      thumb.append(kindIcon(item.kind));
    }
    const check = h("span", { class: "dk-check", role: "checkbox", "aria-checked": String(on), "aria-label": item.name,
                              onclick: (e) => { e.stopPropagation(); toggleSelect(key, index, items, e.shiftKey); } });
    check.append(icon("i-dk-check"));
    let meta;
    const where = baseName(parentOf(item.path));  // «Откуда» — папка, где лежит (лежал) файл
    if (state.view === "trash") meta = [where, date(item.deleted)];
    else if (state.view === "shared") meta = [where, date(item.created)];
    else if (state.found) meta = [where, item.dir ? "" : size(item.size)];
    else meta = [date(item.mtime), item.dir ? "" : size(item.size)];
    const el = h("div", {
      class: "dk-item" + (on ? " on" : ""), tabindex: "0", role: "option", "aria-selected": String(on),
      "data-key": key, draggable: state.view === "files" ? "true" : "false", title: item.path || item.name,
      onclick: (e) => clickItem(e, item, index, items),
      ondblclick: () => state.view === "files" && open(item),
      onkeydown: (e) => { if (e.key === "Enter") { e.preventDefault(); openOrRun(item); } },
      oncontextmenu: (e) => {
        e.preventDefault();
        if (!state.selected.has(key)) { state.selected = new Set([key]); state.anchor = index; showSelection(); }
        openMenu({ x: e.clientX, y: e.clientY }, actionsFor(selectedItems()));
      },
      ondragstart: (e) => {
        const paths = state.selected.has(key) ? selectedItems().map((i) => i.path) : [item.path];
        e.dataTransfer.setData("application/x-yakumo-disk", JSON.stringify(paths));
        e.dataTransfer.effectAllowed = "move";
      },
    }, check, thumb,
      h("span", { class: "dk-name" }, item.name, item.snippet ? h("small", { class: "dk-snippet" },
        item.match !== "name" ? h("b", {}, item.match === "photo" ? L.onPhoto : L.inText) : "", item.snippet) : ""),
      h("span", { class: "dk-meta" }, meta[0]), h("span", { class: "dk-meta dk-size" }, meta[1]));
    if (item.dir && state.view === "files") dropTarget(el, item.path);
    return el;
  }

  function emptyEl() {
    let title = L.emptyFolder, hint = L.emptyHint, iconId = "dk-upload";
    if (state.found) { title = L.nothingFound; hint = ""; iconId = "dk-search"; }
    else if (state.view === "trash") { title = L.emptyTrashText; hint = ""; iconId = "dk-trash"; }
    else if (state.view === "shared") { title = L.emptySharedText; hint = L.emptySharedHint; iconId = "dk-link"; }
    const box = h("div", { class: "empty dk-empty" });
    box.append(icon("i-" + iconId), h("strong", {}, title), hint ? h("span", {}, hint) : "");
    return box;
  }

  function draw(keepFocus = false) {
    const lng = window.Yakumo.lang();
    L = TX[lng] || TX.ru;
    const focused = keepFocus && document.activeElement?.classList.contains("dk-search-input");
    const items = currentItems();
    const layout = state.view === "files" && !state.found ? state.layout : "list";  // у найденного — фрагменты текста
    const list = h("div", { class: `dk-list ${layout}`, role: "listbox",
                             "aria-multiselectable": "true", "aria-label": L.title,
                             onclick: (e) => { if (e.target === e.currentTarget && state.selected.size) {
                               state.selected.clear(); showSelection(); } } });
    if (layout === "list") {
      list.append(h("div", { class: "dk-listhead", "aria-hidden": "true" }, h("span"), h("span"),
        h("span", {}, L.name),
        h("span", {}, state.view === "trash" ? L.from : state.found || state.view === "shared" ? L.from : L.modified),
        h("span", {}, state.view === "trash" ? L.deletedAt : state.view === "shared" ? L.created : L.size)));
    }
    items.forEach((item, i) => list.append(itemEl(item, i, items)));
    if (state.found && state.fresh && !reducedMotion.matches) {  // кицунэ «вынюхала» найденное: волна подсветки
      list.classList.add("dk-sniff");
      [...list.querySelectorAll(".dk-item")].slice(0, 30).forEach((el, i) => el.style.setProperty("--i", i));
    }
    state.fresh = false;
    const footer = items.length && !state.found ? h("div", { class: "dk-foot" }, L.items(items.length)) : "";
    root.replaceChildren(
      h("div", { class: "dk-head" }, h("h1", {}, L.title), usageEl()),
      tabs(), toolbar(),
      state.error ? h("p", { class: "dk-error" }, state.error) : "",
      state.view === "order" ? orderEl() : items.length ? list : (state.loading ? "" : emptyEl()),
      footer,
      h("div", { class: "dk-drop", "aria-hidden": "true" }, h("span", {}, L.dropHere(baseName(state.path)))));
    if (focused) {
      const input = root.querySelector(".dk-search-input");
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    }
  }

  // --- Выделение и открытие ---

  const coarse = matchMedia("(pointer: coarse)");

  function toggleSelect(key, index, items, range) {
    if (range && state.anchor != null) {
      const [a, b] = [state.anchor, index].sort((x, y) => x - y);
      for (let i = a; i <= b; i++) state.selected.add(keyOf(items[i]));
    } else {
      if (state.selected.has(key)) state.selected.delete(key); else state.selected.add(key);
      state.anchor = index;
    }
    showSelection();
  }

  function clickItem(e, item, index, items) {
    const key = keyOf(item);
    if (e.ctrlKey || e.metaKey || e.shiftKey) return toggleSelect(key, index, items, e.shiftKey);
    // На телефоне одно касание открывает, как в мобильном Яндекс Диске; выделение — галочкой.
    if (coarse.matches && !state.selected.size) return openOrRun(item);
    if (coarse.matches) return toggleSelect(key, index, items, false);
    state.selected = new Set([key]);
    state.anchor = index;
    showSelection();
    root.querySelector(`[data-key="${CSS.escape(key)}"]`)?.focus();
  }

  function openOrRun(item) {
    if (state.view === "files") return open(item);
    if (state.view === "shared") return item.dir ? goTo(item.path) : preview(item, [item]);
    return null;
  }

  function goTo(path) { setView("files"); go(path); }

  function go(path, push = true) {
    state.path = path;
    state.query = "";
    state.found = null;
    state.selected.clear();
    state.anchor = null;
    store("path", path);
    if (push) history.pushState({ disk: path }, "", "#/disk");
    load();
  }

  function open(item) {
    if (item.dir) return go(item.path);
    const files = currentItems().filter((i) => !i.dir);
    return preview(item, files);
  }

  function setView(view) {
    if (state.view === view) return;
    state.view = view;
    state.selected.clear();
    state.anchor = null;
    if (view !== "files") { state.query = ""; state.found = null; }
    draw();
    load();
  }

  function setSort(sort) {
    state.sort = sort;
    store("sort", sort);
    draw();
  }

  // --- Действия ---

  function download(items) {
    items.forEach((item, i) => setTimeout(() => {
      const a = h("a", { href: fileUrl(item.path, true), download: "" });
      document.body.append(a);
      a.click();
      a.remove();
    }, i * 400));  // браузеры блокируют много скачиваний сразу
  }

  async function act(fn, done) {
    try {
      const res = await fn();
      if (done) toast(done(res));
    } catch (e) {
      toast(e.message, true);
    }
    await load();
    refreshInfo();
  }

  async function newFolder() {
    const name = await ask(L.newFolder, L.folderName, L.newFolder, L.create);
    if (name) act(() => post("mkdir", { path: state.path, name }));
  }

  // «Спросить Yakumo»: чат открывается с вопросом о файле, папке или о разнице двух файлов.
  function askable(sel) {
    return !!window.Yakumo.ask && (sel.length === 1 || (sel.length === 2 && !sel[0].dir && !sel[1].dir));
  }

  function askYakumo(sel) {
    if (sel.length === 2) return window.Yakumo.ask(L.askCompare(sel[0].path, sel[1].path));
    window.Yakumo.ask(sel[0].dir ? L.askFolder(sel[0].path) : L.askFile(sel[0].path));
  }

  // «Спросить о папке»: готовые вопросы и свой; отвечает Yakumo в чате (пересказ папки — folder_brief).
  async function askFolderDialog(path) {
    const link = `[${path ? baseName(path) : L.root}](disk:${path})`;
    const input = h("input", { class: "text-input", placeholder: L.askOwn, "aria-label": L.askOwn, maxlength: "500" });
    const chips = h("div", { class: "dk-chips" }, L.folderQ.map((q) => h("button", {
      type: "button", class: "dk-chip", onclick: () => { input.value = q; input.form.requestSubmit(); } }, q)));
    let question = "";
    setTimeout(() => input.focus());
    await modal(L.askFolderBtn + ": " + (path ? baseName(path) : L.root), [chips, input], [
      { label: L.cancel },
      { label: L.askSend, primary: true, run: () => { question = input.value.trim(); } },
    ]);
    if (question) window.Yakumo.ask(L.askAbout(link, question));
  }

  // --- Понятные имена ---

  async function namesDialog(path) {
    const body = h("div", { class: "dk-names" }, h("p", { class: "row-hint dk-busy" }, foxArt("dk-fox-mini"), L.namesLooking));
    let rows = [];
    const done = modal(L.names, [body], [
      { label: L.cancel },
      { label: L.namesApply, primary: true, run: () => {
        const items = rows.filter((r) => r.check.checked && r.input.value.trim())
          .map((r) => ({ path: r.item.path, name: r.input.value.trim(), suggested: r.item.suggestion }));
        if (items.length) act(() => post("names", { items }), (res) => L.renamed(res.length));
      } },
    ]);
    let res;
    try { res = await get("names", { path }); } catch (e) { body.replaceChildren(h("p", { class: "dk-error" }, e.message)); return done; }
    if (!res.items.length) { body.replaceChildren(h("p", { class: "row-hint" }, L.namesNone)); return done; }
    rows = res.items.map((item) => ({
      item, check: h("input", { type: "checkbox", checked: true, "aria-label": item.name }),
      input: h("input", { class: "text-input", value: item.suggestion, "aria-label": L.newName, spellcheck: "false" }),
    }));
    body.replaceChildren(h("p", { class: "row-hint" }, L.namesHint), h("div", { class: "dk-names-list" }, rows.map((r) =>
      h("label", { class: "dk-name-row" }, r.check, kindIcon(r.item.kind),
        h("span", { class: "dk-name-old", title: r.item.name }, r.item.name), r.input))));
    return done;
  }

  // --- Конспект ---

  const DOCS = new Set(["pdf", "doc", "text", "sheet", "slides", "book"]);

  async function summarize(item) {
    const busy = toast(h("span", { class: "dk-busy" }, foxArt("dk-fox-mini"), L.summaryBusy(item.name)), false, 0);
    try {
      const res = await post("summary", { path: item.path });
      busy.remove();
      toast(L.summaryDone);
      openPath(res.path);
    } catch (e) {
      busy.remove();
      toast(e.message, true);
    }
  }

  // --- Порядок: правила, предложения и уроки кицунэ ---

  function orderEl() {
    const o = state.order;
    if (!o) return h("div", { class: "dk-order" });
    const box = h("div", { class: "dk-order" },
      h("div", { class: "dk-order-intro" }, foxArt(), h("p", {}, L.orderIntro)));
    for (const p of o.proposals) box.append(proposalEl(p));
    box.append(h("h2", {}, L.rules));
    if (!o.rules.length) box.append(h("p", { class: "row-hint" }, L.noRules));
    for (const r of o.rules) box.append(ruleEl(r));
    if (o.lessons.length) {
      box.append(h("h2", {}, L.lessons), h("ul", { class: "dk-lessons" }, o.lessons.map((x) =>
        h("li", {}, h("span", {}, x.text), h("small", {}, date(x.at))))));
    }
    return box;
  }

  function proposalEl(p) {
    const answer = async (accept) => {
      try {
        await post("order/answer", { id: p.id, accept });
        if (accept) toast(L.ruleSaved);
      } catch (e) { toast(e.message, true); }
      refreshOrder();
    };
    return h("div", { class: "dk-proposal" }, foxArt(),
      h("div", { class: "dk-proposal-text" }, h("strong", {}, L.noticed),
        h("p", {}, L.noticedText(p.label, p.target, p.count)),
        p.examples.length ? h("small", {}, p.examples.join(" · ")) : "",
        h("div", { class: "dk-proposal-actions" },
          h("button", { type: "button", class: "btn primary", onclick: () => answer(true) }, L.accept),
          h("button", { type: "button", class: "btn", onclick: () => answer(false) }, L.decline))));
  }

  function ruleEl(r) {
    const toggle = h("input", { type: "checkbox", role: "switch", checked: r.on, "aria-label": r.label,
      onchange: async (e) => {
        try { await post("order/rule", { ...r, on: e.target.checked }); } catch (err) { toast(err.message, true); }
        refreshOrder();
      } });
    const meta = [r.source === "learned" ? L.learned : r.source === "chat" ? L.fromChat : "",
                  r.hits ? L.ruleHits(r.hits) : "", r.tell ? `💬 ${r.tell}` : ""].filter(Boolean).join(" · ");
    return h("div", { class: "dk-rule" + (r.on ? "" : " off") },
      h("span", { class: "switch" }, toggle, h("span", { class: "knob" })),
      h("div", { class: "dk-rule-text" }, h("strong", {}, r.label, h("span", { class: "dk-arrow" }, " → "), r.to),
        meta ? h("small", {}, meta) : ""),
      button("dk-rename", L.editRule, () => ruleDialog(r), { iconOnly: true }),
      button("dk-trash", L.del, async () => {
        try { await post("order/delete", { id: r.id }); } catch (e) { toast(e.message, true); }
        refreshOrder();
      }, { iconOnly: true, cls: "danger" }));
  }

  async function ruleDialog(rule = {}) {
    const field = (label, input, hint) => h("label", { class: "dk-field" }, h("span", {}, label), input,
                                             hint ? h("small", {}, hint) : "");
    const words = h("input", { class: "text-input", value: (rule.words || []).join(", "), placeholder: L.ruleWordsHint });
    const kind = h("select", { class: "select" }, ["", ...Object.keys(L.kindNames)].map((k) =>
      h("option", { value: k, selected: (rule.kinds || [""])[0] === k }, k ? L.kindNames[k] : L.anyKind)));
    const to = h("input", { class: "text-input", value: rule.to || "", placeholder: L.ruleToHint.split(": ").pop() });
    const tell = h("input", { class: "text-input", value: rule.tell || "", placeholder: L.ruleTellHint });
    let data = null;
    setTimeout(() => words.focus());
    await modal(rule.id ? L.editRule : L.newRule, [h("div", { class: "dk-form" },
      field(L.ruleWords, words), field(L.ruleKinds, kind), field(L.ruleTo, to, L.ruleToHint), field(L.ruleTell, tell))], [
      { label: L.cancel },
      { label: L.save, primary: true, run: () => {
        data = { ...rule, words: words.value, kinds: kind.value ? [kind.value] : [], to: to.value, tell: tell.value };
      } },
    ]);
    if (!data) return;
    try {
      await post("order/rule", data);
      toast(L.ruleSaved);
    } catch (e) {
      toast(e.message, true);
      return ruleDialog({ ...data, words: data.words.split(",").map((w) => w.trim()) });
    }
    refreshOrder();
  }

  async function sortNow() {
    let moves;
    try { moves = (await get("order/plan")).moves; } catch (e) { return toast(e.message, true); }
    if (!moves.length) return toast(L.nothingToSort);
    let ok = false;
    await modal(L.sortNow, [h("ul", { class: "dk-plan" }, moves.map((m) =>
      h("li", {}, kindIcon(m.kind), h("span", {}, m.name), h("small", {}, `→ ${m.to}`))))], [
      { label: L.cancel },
      { label: L.sortPlan(moves.length), primary: true, run: () => { ok = true; } },
    ]);
    if (!ok) return;
    let done = [];
    try { done = await post("order/apply", { moves }); } catch (e) { toast(e.message, true); }
    if (state.view !== "files") setView("files");
    await load();
    refreshInfo();
    foxCarry(done, root.querySelector(".dk-bar .dk-actions"));
  }

  async function rename(item) {
    const dot = item.dir ? -1 : item.name.lastIndexOf(".");
    const name = await ask(L.rename, L.newName, item.name, L.save, dot > 0 ? dot : item.name.length);
    if (name && name !== item.name) act(() => post("rename", { path: item.path, name }));
  }

  function remove(items) {
    state.selected.clear();
    act(() => post("delete", { paths: items.map((i) => i.path) }), (r) => L.deleted(r.count));
  }

  function restore(items) {
    state.selected.clear();
    act(() => post("restore", { ids: items.map((i) => i.id) }), (r) => L.restored(r.length));
  }

  async function purge(items) {
    if (!(await confirmBox(L.purgeAsk(items.length), L.purge))) return;
    state.selected.clear();
    act(() => post("purge", { ids: items.map((i) => i.id) }));
  }

  async function emptyTrash() {
    if (!(await confirmBox(L.emptyAsk, L.emptyTrash))) return;
    state.selected.clear();
    act(() => post("purge", { all: true }));
  }

  function unshare(items) {
    state.selected.clear();
    act(() => Promise.all(items.map((i) => post("unshare", { token: i.token }))));
  }

  function moveTo(paths, to, copyMode) {
    state.selected.clear();
    act(() => post(copyMode ? "copy" : "move", { paths, to }),
        (r) => (copyMode ? L.copied : L.moved)(r.length));
  }

  // Ссылка для других устройств: адрес компьютера в локальной сети, если Yakumo открыт для сети.
  function lanBase() {
    const s = window.Yakumo.status();
    let host = null;
    try { host = new URL(s?.url || "").hostname; } catch { /* нет статуса */ }
    const local = (x) => !x || x === "localhost" || x.startsWith("127.");
    if (!local(location.hostname)) return { base: location.origin, lan: true };
    if (!local(host)) return { base: `http://${host}:${location.port}`, lan: true };
    if (state.info?.lan && state.info.lan_address) {
      return { base: `http://${state.info.lan_address}:${location.port}`, lan: true };
    }
    return { base: location.origin, lan: false };
  }
  const linkFor = (token) => `${lanBase().base}/api/disk/s?t=${encodeURIComponent(token)}`;

  async function share(item) {
    let res;
    try { res = await post("share", { path: item.path }); } catch (e) { return toast(e.message, true); }
    const url = linkFor(res.token);
    const input = h("input", { class: "text-input", readonly: true, value: url, "aria-label": L.linkTitle,
                               onfocus: (e) => e.target.select() });
    const { lan } = lanBase();
    modal(L.share + ": " + item.name, [
      h("div", { class: "inline-form" }, input,
        h("button", { class: "btn primary", type: "button", onclick: () => copy(url, L.linkCopied) }, L.copyLink)),
      h("p", { class: "row-hint" + (lan ? "" : " dk-warn") }, lan ? L.linkLan : L.linkLocal),
    ], [
      { label: L.unshare, run: () => act(() => post("unshare", { token: res.token })) },
      { label: L.close, primary: true },
    ]);
  }

  async function copy(text, done) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {  // по адресу в сети (не localhost) буфер обмена браузер не даёт
      const t = h("textarea", {}, text);
      document.body.append(t);
      t.select();
      document.execCommand("copy");
      t.remove();
    }
    toast(done);
  }

  // --- Перемещение: выбор папки ---

  async function moveDialog(items, copyMode) {
    const moving = new Set(items.map((i) => i.path));
    let at = state.path;
    const list = h("div", { class: "dk-picker", role: "listbox", "aria-label": L.chooseFolder });
    const where = h("div", { class: "dk-picker-path" });
    async function show(path) {
      at = path;
      where.replaceChildren(...[L.root, ...(path ? path.split("/") : [])].map((p, i, arr) => {
        const target = arr.slice(1, i + 1).join("/");
        return i === arr.length - 1 ? h("strong", {}, p)
          : h("button", { type: "button", class: "dk-crumb", onclick: () => show(target) }, p);
      }).flatMap((el, i) => (i ? [h("span", { class: "dk-sep" }, "/"), el] : [el])));
      list.replaceChildren(h("span", { class: "row-hint" }, L.loading || "…"));
      let res;
      try { res = await get("list", { path }); } catch (e) { list.replaceChildren(e.message); return; }
      const dirs = sorted(res.items.filter((i) => i.dir && !moving.has(i.path)));
      list.replaceChildren(...dirs.map((d) => {
        const b = h("button", { type: "button", class: "dk-picker-item", onclick: () => show(d.path) }, d.name);
        b.prepend(icon("i-dk-folder"));
        return b;
      }));
      if (!dirs.length) list.append(h("span", { class: "row-hint" }, L.emptyFolder));
    }
    show(at);
    modal(copyMode ? L.copy : L.move, [where, list], [
      { label: L.cancel },
      { label: copyMode ? L.copyHere : L.moveHere, primary: true, run: () => moveTo([...moving], at, copyMode) },
    ]);
  }

  // --- Перетаскивание: файлы с компьютера и перенос внутри Диска ---

  function dropTarget(el, path) {
    el.addEventListener("dragover", (e) => {
      if (![...e.dataTransfer.types].some((t) => t === "Files" || t === "application/x-yakumo-disk")) return;
      e.preventDefault();
      e.stopPropagation();
      el.classList.add("dk-over");
      root.classList.remove("dropping");
    });
    el.addEventListener("dragleave", () => el.classList.remove("dk-over"));
    el.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
      el.classList.remove("dk-over");
      root.classList.remove("dropping");
      handleDrop(e.dataTransfer, path);
    });
  }

  async function handleDrop(dt, path) {
    const inner = dt.getData("application/x-yakumo-disk");
    if (inner) {
      const paths = JSON.parse(inner).filter((p) => p !== path && parentOf(p) !== path);
      if (paths.length) moveTo(paths, path, false);
      return;
    }
    enqueue(await droppedFiles(dt), path);
  }

  async function droppedFiles(dt) {
    const entries = [...dt.items].map((i) => i.webkitGetAsEntry?.()).filter(Boolean);
    if (!entries.length) return [...dt.files].map((f) => ({ file: f, rel: f.name }));
    const out = [];
    async function walk(entry, prefix) {
      if (entry.isFile) {
        const file = await new Promise((ok, fail) => entry.file(ok, fail)).catch(() => null);
        if (file) out.push({ file, rel: prefix + file.name });
      } else if (entry.isDirectory) {
        const reader = entry.createReader();
        for (;;) {  // readEntries отдаёт папку частями
          const batch = await new Promise((ok, fail) => reader.readEntries(ok, fail)).catch(() => []);
          if (!batch.length) break;
          for (const child of batch) await walk(child, prefix + entry.name + "/");
        }
      }
    }
    for (const e of entries) await walk(e, "");
    return out;
  }

  let dragDepth = 0;
  root.addEventListener("dragenter", (e) => {
    if (state.view !== "files" || state.found || ![...e.dataTransfer.types].includes("Files")) return;
    dragDepth++;
    root.classList.add("dropping");
  });
  root.addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; root.classList.remove("dropping"); } });
  root.addEventListener("dragover", (e) => {
    if (state.view === "files" && !state.found && [...e.dataTransfer.types].includes("Files")) e.preventDefault();
  });
  root.addEventListener("drop", (e) => {
    dragDepth = 0;
    root.classList.remove("dropping");
    if (state.view !== "files" || state.found || !e.dataTransfer.files.length) return;
    e.preventDefault();
    handleDrop(e.dataTransfer, state.path);
  });

  // --- Загрузка ---

  const queue = [];
  const placedNow = [];
  let uploading = null;
  const panel = h("div", { class: "dk-uploads", hidden: true, role: "status", "aria-live": "polite" });
  document.body.append(panel);

  function enqueue(files, dest) {
    if (!files.length) return;
    for (const f of files) queue.push({ ...f, dest, loaded: 0, status: "wait" });
    showPanel();
    if (!uploading) nextUpload();
  }

  function nextUpload() {
    const job = queue.find((j) => j.status === "wait");
    uploading = job || null;
    if (!job) {
      showPanel();
      load().then(() => foxCarry(placedNow.splice(0), panel.hidden ? root.querySelector(".dk-upload") : panel));
      refreshInfo();
      return;
    }
    job.status = "run";
    const xhr = new XMLHttpRequest();
    job.xhr = xhr;
    const rel = job.dest ? `${job.dest}/${job.rel}` : job.rel;
    xhr.open("POST", `/api/disk/upload?path=${encodeURIComponent(rel)}`);
    xhr.setRequestHeader("X-Yakumo", "1");
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (e) => { job.loaded = e.loaded; showPanel(); };
    xhr.onload = () => {
      let err = null, res = null;
      try { res = JSON.parse(xhr.responseText); } catch { /* ответ без JSON */ }
      if (xhr.status !== 200) err = res?.error || `HTTP ${xhr.status}`;
      else if (res?.placed) placedNow.push(res.placed);  // правило порядка сразу разложило файл
      finish(job, err);
    };
    xhr.onerror = () => finish(job, L.uploadErrors(1));
    xhr.onabort = () => finish(job, "—");
    xhr.send(job.file);
  }

  let listTimer = 0, hideTimer = 0;
  function finish(job, err) {
    job.status = err ? "error" : "done";
    job.error = err;
    job.loaded = job.file.size;
    // Пока идёт загрузка, обновляем открытую папку не чаще раза в секунду.
    if (!err && state.view === "files" && !listTimer) {
      listTimer = setTimeout(() => { listTimer = 0; load(); }, 1000);
    }
    nextUpload();
  }

  function showPanel() {
    if (!queue.length) { panel.hidden = true; return; }
    const done = queue.filter((j) => j.status === "done").length;
    const errors = queue.filter((j) => j.status === "error");
    const total = queue.reduce((s, j) => s + j.file.size, 0) || 1;
    const loaded = queue.reduce((s, j) => s + j.loaded, 0);
    const active = queue.some((j) => j.status === "wait" || j.status === "run");
    const head = active ? L.uploading(done + errors.length + 1, queue.length) : L.uploaded(done);
    clearTimeout(hideTimer);
    if (!active && !errors.length) hideTimer = setTimeout(() => { queue.length = 0; showPanel(); }, 6000);
    const closeBtn = active
      ? h("button", { type: "button", class: "btn", onclick: cancelUploads }, L.cancelAll)
      : h("button", { type: "button", class: "icon-btn", "aria-label": L.close,
                      onclick: () => { queue.length = 0; showPanel(); } }, icon("i-dk-x"));
    panel.hidden = false;
    panel.replaceChildren(
      h("div", { class: "dk-up-head" },
        h("strong", {}, head, errors.length ? ` · ${L.uploadErrors(errors.length)}` : ""), closeBtn),
      h("div", { class: "dk-meter" }, h("span", { class: "dk-meter-disk", style: `width:${(loaded / total) * 100}%` })),
      h("ul", { class: "dk-up-list" }, queue.filter((j) => j.status !== "done").slice(0, 6).map((j) =>
        h("li", { class: j.status }, h("span", {}, j.rel),
          h("small", {}, j.status === "error" ? j.error
            : `${Math.round((j.loaded / (j.file.size || 1)) * 100)}%`)))));
  }

  function cancelUploads() {
    for (const j of queue) if (j.status === "wait") { j.status = "error"; j.error = "—"; }
    uploading?.xhr?.abort();
  }

  window.addEventListener("beforeunload", (e) => { if (uploading) e.preventDefault(); });

  // --- Просмотр ---
  // Плавное листание с лентой миниатюр, увеличение колёсиком и перетаскиванием,
  // тёмный кинорежим для видео и панель «Связанное» сбоку.

  const viewer = h("div", { class: "dk-viewer", hidden: true, role: "dialog", "aria-modal": "true" });
  document.body.append(viewer);
  let viewing = null;  // { list, index }
  let zoom = { s: 1, x: 0, y: 0 };
  let sideOn = stored("side", false);
  let cinemaOn = stored("cinema", true);
  let idleTimer = 0;

  function preview(item, list) {
    const index = Math.max(0, list.findIndex((i) => i.path === item.path));
    viewing = { list, index };
    showViewer(0);
  }

  function showViewer(dir = 0) {
    const { list, index } = viewing;
    const item = list[index];
    const url = fileUrl(item.path);
    zoom = { s: 1, x: 0, y: 0 };
    let body;
    if (item.kind === "image") body = h("img", { src: url, alt: item.name, class: "dk-zoomable", draggable: "false" });
    else if (item.kind === "video") body = h("video", { src: url, controls: true, autoplay: true, playsinline: true });
    else if (item.kind === "audio") body = h("audio", { src: url, controls: true, autoplay: true });
    else if (item.kind === "pdf") body = h("iframe", { src: url, title: item.name });
    else if (item.kind === "text") body = h("pre", { class: "dk-text" }, "…");
    else {
      body = h("div", { class: "empty dk-nopreview" });
      body.append(kindIcon(item.kind), h("strong", {}, item.name), h("span", {}, `${size(item.size)} · ${L.noPreview}`),
        h("a", { class: "btn primary", href: fileUrl(item.path, true) }, L.download));
    }
    const nav = (d) => {
      const b = h("button", { type: "button", class: `icon-btn dk-nav dk-nav-${d < 0 ? "prev" : "next"}`,
                              "aria-label": d < 0 ? "←" : "→", onclick: () => step(d) });
      b.append(icon(d < 0 ? "i-dk-prev" : "i-dk-next"));
      return b;
    };
    const tool = (id, label, onclick, on) => {
      const b = h("button", { type: "button", class: "icon-btn" + (on ? " on" : ""), title: label, "aria-label": label,
                              "aria-pressed": on === undefined ? null : String(on), onclick });
      b.append(icon("i-" + id));
      return b;
    };
    const files = state.view === "files";
    const stage = h("div", { class: "dk-stage" + (dir ? ` dk-slide-${dir > 0 ? "next" : "prev"}` : "") }, body);
    viewer.replaceChildren(
      h("div", { class: "dk-viewer-top" },
        h("div", { class: "dk-viewer-title" }, h("strong", {}, item.name),
          h("small", {}, `${list.length > 1 ? `${index + 1} / ${list.length} · ` : ""}${size(item.size)}`)),
        ...(item.kind === "image" ? [tool("dk-zoomout", L.zoomOut, () => zoomBy(1 / 1.5)),
                                     tool("dk-zoomin", L.zoomIn, () => zoomBy(1.5)),
                                     tool("dk-fit", L.zoomReset, () => zoomBy(0))] : []),
        item.kind === "video" ? tool("dk-cinema", L.cinema, () => {
          cinemaOn = !cinemaOn;
          store("cinema", cinemaOn);
          showViewer();
        }, cinemaOn) : "",
        files ? tool("dk-related", L.related, () => { sideOn = !sideOn; store("side", sideOn); showViewer(); }, sideOn) : "",
        files && DOCS.has(item.kind) ? tool("dk-summary", L.summary, () => summarize(item)) : "",
        files && window.Yakumo.ask ? tool("dk-ask", L.askYakumo, () => { closeViewer(); askYakumo([item]); }) : "",
        tool("dk-download", L.download, () => download([item])),
        files ? tool("dk-share", L.share, () => share(item)) : "",
        files ? tool("dk-trash", L.del, () => { closeViewer(); remove([item]); }) : "",
        tool("dk-x", L.close, closeViewer)),
      h("div", { class: "dk-viewer-main" }, stage, files && sideOn ? sideEl(item) : ""),
      list.length > 1 ? stripEl(list, index) : "",
      ...(list.length > 1 ? [nav(-1), nav(1)] : []));
    viewer.hidden = false;
    viewer.dataset.kind = item.kind;
    viewer.classList.toggle("cinema", item.kind === "video" && cinemaOn);
    wake();
    viewer.querySelector(".dk-viewer-top .icon-btn:last-child").focus();
    if (item.kind === "text") showText(item, body);
    for (const d of [-1, 1]) {  // соседние фото — заранее, чтобы листались без задержки
      const next = list[(index + d + list.length) % list.length];
      if (next.kind === "image") new Image().src = fileUrl(next.path);
    }
  }

  function stripEl(list, index) {
    const strip = h("div", { class: "dk-strip", "aria-label": L.title });
    list.slice(0, 400).forEach((it, i) => {
      const b = h("button", { type: "button", class: "dk-strip-item" + (i === index ? " on" : ""), title: it.name,
                              "aria-label": it.name, "aria-current": i === index ? "true" : null, onclick: () => jump(i) });
      b.append(it.kind === "image" ? h("img", { src: fileUrl(it.path), alt: "", loading: "lazy", draggable: "false" })
        : kindIcon(it.kind));
      strip.append(b);
    });
    requestAnimationFrame(() => strip.children[index]?.scrollIntoView({ inline: "center", block: "nearest" }));
    return strip;
  }

  function why(text) {
    if (text.startsWith("words:")) return L.whyWords(text.slice(6));
    if (text.startsWith("memory:")) return `${L.whyMemory}: ${text.slice(7)}`;
    return L.whyMeaning;
  }

  // «Связанное»: похожие по тексту и смыслу файлы и что кицунэ помнит о файле.
  function sideEl(item) {
    const side = h("aside", { class: "dk-side", "aria-label": L.related }, h("h3", {}, L.related),
      h("p", { class: "row-hint dk-busy" }, foxArt("dk-fox-mini"), L.sniffing));
    get("related", { path: item.path }).then((res) => {
      if (viewing?.list[viewing.index]?.path !== item.path) return;
      const parts = [h("h3", {}, L.related)];
      if (res.facts.length) {
        parts.push(h("div", { class: "dk-side-facts" }, h("strong", {}, L.relatedFacts),
          ...res.facts.map((f) => h("p", {}, f))));
      }
      if (!res.files.length) parts.push(h("p", { class: "row-hint" }, L.relatedNone));
      for (const f of res.files) {
        parts.push(h("button", { type: "button", class: "dk-side-file", title: f.path, onclick: () => {
          const i = viewing.list.findIndex((x) => x.path === f.path);
          if (i >= 0) return jump(i);
          closeViewer();
          openPath(f.path);
        } }, kindIcon(f.kind), h("span", {}, h("b", {}, f.name), h("small", {}, why(f.why)))));
      }
      side.replaceChildren(...parts);
    }).catch((e) => side.replaceChildren(h("h3", {}, L.related), h("p", { class: "dk-error" }, e.message)));
    return side;
  }

  async function showText(item, pre) {
    const LIMIT = 512 * 1024;
    try {
      const r = await fetch(fileUrl(item.path), { headers: { Range: `bytes=0-${LIMIT - 1}` } });
      const buf = await r.arrayBuffer();
      let text;
      try { text = new TextDecoder("utf-8", { fatal: true }).decode(buf); } catch {
        // Старые русские файлы из Блокнота часто в windows-1251.
        text = new TextDecoder("windows-1251").decode(buf);
      }
      pre.textContent = text;
      if (item.size > LIMIT) pre.after(h("p", { class: "row-hint dk-cut" }, L.textCut));
    } catch (e) {
      pre.textContent = e.message;
    }
  }

  function step(d) {
    if (!viewing) return;
    viewing.index = (viewing.index + d + viewing.list.length) % viewing.list.length;
    showViewer(d);
  }

  function jump(i) {
    if (!viewing || i === viewing.index) return;
    const d = i > viewing.index ? 1 : -1;
    viewing.index = i;
    showViewer(d);
  }

  function closeViewer() {
    viewer.hidden = true;
    viewer.replaceChildren();  // остановить видео
    viewer.classList.remove("cinema", "idle");
    viewing = null;
  }

  // Кинорежим: панели прячутся, пока мышь не двигается.
  function wake() {
    viewer.classList.remove("idle");
    clearTimeout(idleTimer);
    if (viewer.classList.contains("cinema")) idleTimer = setTimeout(() => viewer.classList.add("idle"), 2500);
  }
  viewer.addEventListener("pointermove", wake);

  // Увеличение: колёсико — к точке под курсором, двойной щелчок — 2.5× и обратно, при увеличении — перетаскивание.
  const zoomImg = () => viewer.querySelector(".dk-zoomable");
  function applyZoom(img) {
    img.style.transform = `translate(${zoom.x}px, ${zoom.y}px) scale(${zoom.s})`;
    img.classList.toggle("zoomed", zoom.s > 1);
  }
  function zoomAt(img, factor, cx, cy) {
    const r = img.getBoundingClientRect();  // с учётом текущего увеличения
    const ox = cx - (r.left + r.width / 2) + zoom.x, oy = cy - (r.top + r.height / 2) + zoom.y;
    const s = Math.min(8, Math.max(1, zoom.s * factor));
    const k = s / zoom.s;
    zoom = s === 1 ? { s: 1, x: 0, y: 0 } : { s, x: ox - (ox - zoom.x) * k, y: oy - (oy - zoom.y) * k };
    applyZoom(img);
  }
  function zoomBy(factor) {
    const img = zoomImg();
    if (!img) return;
    if (!factor) { zoom = { s: 1, x: 0, y: 0 }; return applyZoom(img); }
    const r = img.getBoundingClientRect();
    zoomAt(img, factor, r.left + r.width / 2, r.top + r.height / 2);
  }
  viewer.addEventListener("wheel", (e) => {
    const img = zoomImg();
    if (!img || !e.target.closest(".dk-stage")) return;
    e.preventDefault();
    zoomAt(img, e.deltaY < 0 ? 1.2 : 1 / 1.2, e.clientX, e.clientY);
  }, { passive: false });
  viewer.addEventListener("dblclick", (e) => {
    const img = zoomImg();
    if (!img || e.target !== img) return;
    if (zoom.s > 1) zoomBy(0); else zoomAt(img, 2.5, e.clientX, e.clientY);
  });

  let drag = null;
  viewer.addEventListener("pointerdown", (e) => {
    drag = { x: e.clientX, y: e.clientY, zx: zoom.x, zy: zoom.y, pan: zoom.s > 1 && e.target === zoomImg() };
    if (drag.pan) { e.target.setPointerCapture(e.pointerId); e.preventDefault(); }
  });
  viewer.addEventListener("pointermove", (e) => {
    if (!drag?.pan) return;
    zoom.x = drag.zx + e.clientX - drag.x;
    zoom.y = drag.zy + e.clientY - drag.y;
    applyZoom(zoomImg());
  });
  viewer.addEventListener("pointerup", (e) => {
    // Листание жестом — только у фото без увеличения.
    if (drag && !drag.pan && zoom.s === 1 && viewing?.list[viewing.index].kind === "image"
        && Math.abs(e.clientX - drag.x) > 60 && Math.abs(e.clientX - drag.x) > Math.abs(e.clientY - drag.y)) {
      step(e.clientX < drag.x ? 1 : -1);
    }
    drag = null;
  });
  viewer.addEventListener("click", (e) => { if (e.target.classList.contains("dk-stage")) closeViewer(); });

  // --- Умный поиск ---

  async function smartDialog() {
    const body = h("div", { class: "dk-smart" });
    let info = null;
    async function show() {
      try { info = await get("smart"); } catch (e) { body.replaceChildren(e.message); return; }
      const toggle = (key) => h("input", { type: "checkbox", role: "switch", checked: info[key], disabled: !info.cloud,
        onchange: async (e) => {
          try { await post("smart", { [key]: e.target.checked }); } catch (err) { toast(err.message, true); }
          show();
        } });
      const row = (key, title, hint) => h("label", { class: "row" },
        h("span", { class: "row-text" }, h("span", { class: "row-title" }, title), h("span", { class: "row-hint" }, hint)),
        h("span", { class: "switch" }, toggle(key), h("span", { class: "knob" })));
      let note = "";
      if (!info.cloud) note = h("p", { class: "dk-warn" }, L.noCloud);
      else if (!info.vision_model) note = h("p", { class: "dk-warn" }, L.noVision);
      else note = h("p", { class: "row-hint" }, L.visionModel(info.vision_model),
        info.photos ? ` · ${L.photosDone(info.photos_done)}` : "", info.ocr ? ` · ${L.ocrDone(info.ocr_done)}` : "");
      body.replaceChildren(
        h("p", {}, L.smartText(info.texts)),
        info.running && info.queue ? h("p", { class: "row-hint" }, L.smartBusy(info.done, info.queue)) : "",
        row("photos", L.photos, L.photosHint),
        row("ocr", L.ocr, L.ocrHint),
        note,
        info.photo_error ? h("p", { class: "dk-error" }, info.photo_error) : "",
        info.ocr_error ? h("p", { class: "dk-error" }, info.ocr_error) : "",
        h("p", { class: "row-hint dk-tip" }, L.chatTip));
    }
    await show();
    const timer = setInterval(() => { if (info?.running || info?.photos || info?.ocr) show(); }, 3000);
    await modal(L.smart, [body], [{ label: L.close, primary: true }]);
    clearInterval(timer);
  }

  // Ссылки на файлы из ответов Yakumo в чате: [имя](disk:путь).
  async function openPath(raw) {
    let path = raw || "";
    try { path = decodeURIComponent(path); } catch { /* уже без %-кодов */ }
    path = path.replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
    state.view = "files";
    state.query = "";
    state.found = null;
    if (location.hash !== "#/disk") location.hash = "#/disk";
    if (!path) return go("");
    const parent = parentOf(path), name = path.split("/").pop();
    let res;
    try { res = await get("list", { path: parent }); } catch { return toast(L.notFound, true); }
    const item = res.items.find((i) => i.name === name);
    if (!item) return toast(L.notFound, true);
    if (item.dir) return go(item.path);
    go(parent);
    return preview(item, sorted(res.items).filter((i) => !i.dir));
  }

  document.addEventListener("click", (e) => {
    const link = e.target.closest?.("a.disk-link");
    if (!link) return;
    e.preventDefault();
    openPath(link.dataset.path);
  });

  // Yakumo выполнила план из чата: показать изменения.
  window.addEventListener("yakumo:files-changed", () => {
    if (!started) return;
    load();
    refreshInfo();
  });

  // --- Окна, меню, уведомления ---

  function modal(title, content, actions) {
    return new Promise((resolve) => {
      const dlg = h("dialog", { class: "dk-dialog card" });
      const close = (value) => { dlg.close(); dlg.remove(); resolve(value); };
      const form = h("form", { method: "dialog", onsubmit: (e) => {
        e.preventDefault();
        const primary = actions.find((a) => a.primary);
        primary?.run?.();
        close(true);
      } }, h("h2", {}, title), content,
        h("div", { class: "dk-dialog-actions" }, actions.map((a) => h("button", {
          type: a.primary ? "submit" : "button", class: "btn" + (a.primary ? " primary" : "") + (a.danger ? " danger" : ""),
          onclick: a.primary ? null : () => { a.run?.(); close(false); },
        }, a.label))));
      dlg.append(form);
      dlg.addEventListener("cancel", (e) => { e.preventDefault(); close(false); });
      document.body.append(dlg);
      dlg.showModal();
    });
  }

  function ask(title, label, value, ok, selectEnd) {
    const input = h("input", { class: "text-input", value, "aria-label": label, spellcheck: "false", required: true,
                               maxlength: "255" });
    let result = null;
    const p = modal(title, [input], [
      { label: L.cancel },
      { label: ok, primary: true, run: () => { result = input.value.trim(); } },
    ]).then(() => result);
    setTimeout(() => { input.focus(); input.setSelectionRange(0, selectEnd ?? value.length); });
    return p;
  }

  function confirmBox(text, ok) {
    let yes = false;
    return modal(ok, [h("p", {}, text)], [
      { label: L.cancel },
      { label: ok, primary: true, danger: true, run: () => { yes = true; } },
    ]).then(() => yes);
  }

  let menuEl = null;
  function openMenu(at, actions) {
    closeMenu();
    menuEl = h("div", { class: "dk-menu card", role: "menu" });
    for (const a of actions) {
      const b = h("button", { type: "button", role: "menuitem", class: a.danger ? "danger" : "",
                              onclick: () => { closeMenu(); a.run(); } }, a.label);
      b.prepend(icon("i-" + a.icon));
      menuEl.append(b);
    }
    document.body.append(menuEl);
    const r = at instanceof Element ? at.getBoundingClientRect() : { left: at.x, bottom: at.y, right: at.x };
    const w = menuEl.offsetWidth, hgt = menuEl.offsetHeight;
    menuEl.style.left = `${Math.min(r.left, innerWidth - w - 8)}px`;
    menuEl.style.top = `${Math.min(r.bottom + 4, innerHeight - hgt - 8)}px`;
    menuEl.querySelector("button")?.focus();
  }
  function closeMenu() { menuEl?.remove(); menuEl = null; }
  document.addEventListener("click", (e) => { if (menuEl && !menuEl.contains(e.target)) closeMenu(); });
  window.addEventListener("resize", closeMenu);

  const toasts = h("div", { class: "dk-toasts", role: "status", "aria-live": "polite" });
  document.body.append(toasts);
  function toast(text, bad = false, ms = bad ? 6000 : 3000) {
    const t = h("div", { class: "dk-toast" + (bad ? " bad" : "") }, text);
    toasts.append(t);
    if (ms) setTimeout(() => t.remove(), ms);
    return t;
  }

  // --- Клавиши ---

  document.addEventListener("keydown", (e) => {
    if (menuEl && e.key === "Escape") return closeMenu();
    if (viewing) {
      if (document.querySelector("dialog[open]")) return;
      if (e.key === "Escape") closeViewer();
      else if (e.key === "ArrowLeft") step(-1);
      else if (e.key === "ArrowRight") step(1);
      else if (e.key === "+" || e.key === "=") zoomBy(1.5);
      else if (e.key === "-") zoomBy(1 / 1.5);
      else if (e.key === "0") zoomBy(0);
      return;
    }
    if (document.body.dataset.page !== "disk" || document.querySelector("dialog[open]")) return;
    if (e.target.closest?.("input, textarea, select")) return;
    const sel = selectedItems();
    if (e.key === "Escape" && state.selected.size) { state.selected.clear(); showSelection(); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
      e.preventDefault();
      state.selected = new Set(currentItems().map(keyOf));
      showSelection();
    } else if (e.key === "Delete" && sel.length) {
      if (state.view === "files") remove(sel);
      else if (state.view === "trash") purge(sel);
    } else if (e.key === "F2" && sel.length === 1 && state.view === "files") {
      e.preventDefault();
      rename(sel[0]);
    } else if (e.key === "Backspace" && state.view === "files" && state.path && !state.found) {
      go(parentOf(state.path));
    }
  });

  // Кнопки «назад/вперёд» браузера и мыши ходят по папкам.
  window.addEventListener("popstate", (e) => {
    if (location.hash !== "#/disk") return;
    const path = e.state?.disk ?? "";
    if (state.view !== "files") state.view = "files";
    if (path !== state.path || state.found) go(path, false);
  });

  window.Yakumo.addPage({
    id: "disk",
    icon: '<path d="M7 18.5a4.5 4.5 0 0 1-.6-9A6 6 0 0 1 18 8.6a4.5 4.5 0 0 1-.5 9.9z"/><path d="M12 15v-5m-2.2 2.2L12 10l2.2 2.2"/>',
    title: { ru: TX.ru.title, en: TX.en.title },
    render() {
      draw();
      if (!started) {
        started = true;
        history.replaceState({ disk: state.path }, "", location.hash);
        load();
        refreshInfo();
      }
      return [root];
    },
  });
})();
