"use strict";

// «Память»: что Yakumo помнит о пользователе — факты, карта людей и мест, разговоры, обещания, даты и навыки,
// а ещё фоновый «разум» (режим, бюджет, очередь мыслей) и «рост» (уроки, стиль, желания, свои инструменты).
// Страница подключается через Yakumo.addPage. Ещё скрипт забирает сообщения, которые Yakumo пишет первой,
// и показывает на аватаре, бодрствует она, дремлет или спит.
(() => {
  const { h, getJSON, postJSON } = window.Yakumo;
  const SVG = "http://www.w3.org/2000/svg";

  const TX = {
    ru: {
      title: "Мозг", facts: "Факты", map: "Карта", talks: "Разговоры", plans: "Обещания и даты", skills: "Навыки",
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
      you: "Вы", sources: { auto: "запомнила сама", chat: "вы попросили", manual: "добавлено вручную", module: "из модуля", doc: "из документа" },
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
      grow: "Саморазвитие в простое", growHint: "Когда вы не работаете с Yakumo, она учится по вашим документам на Диске, сдаёт себе экзамен по своим ответам и раз в неделю улучшает свой стиль. Тратит фоновые запросы из дневного бюджета.",
      mind: "Разум", growth: "Рост", archive: (n) => `Архив · ${n}`, restore: "Вернуть из архива",
      archiveHint: "Потускневшие и заменённые новыми факты остаются в архиве: в подсказку они не попадают, но историю можно найти поиском.",
      modes: { awake: "Бодрствует", drowsy: "Дремлет", asleep: "Спит" },
      modeHints: { awake: "Вы недавно писали — Yakumo с вами, фоновые дела только самые лёгкие.",
                   drowsy: "В чате тихо — Yakumo разбирает Диск и считает векторы.",
                   asleep: "Вы давно не заходили — Yakumo спит и растёт: сон кицунэ, учёба по документам, экзамен, улучшение стиля." },
      budget: "Фоновых запросов в день", budgetUsed: (u, l) => l ? `Сегодня: ${u} из ${l}` : `Сегодня: ${u}`,
      noLimit: "Без ограничения",
      budgetHint: "Работа «круглые сутки» тратит запросы к Cloud.ru. Когда лимит исчерпан, Yakumo отдыхает до завтра; разговоры в чате не ограничиваются.",
      knowledge: (k) => `База знаний: ${k.documents} док., ${k.chunks} фрагм., с векторами ${k.vectors}.`,
      noDisk: "База знаний: модуль «Диск» не подключён.",
      thoughts: "Очередь мыслей", noThoughts: "Пока тихо", noThoughtsHint: "Здесь видно всё, что Yakumo делает сама: сон, учёба, экзамены, фоновые задачи.",
      kindsT: { sleep: "Сон", study: "Учёба", exam: "Экзамен", style: "Стиль", task: "Задача" },
      statuses: { queued: "в очереди", running: "думаю…", done: "готово", failed: "не вышло", cancelled: "отменено" },
      stop: "Отменить",
      examNow: "Экзамен сейчас", styleNow: "Улучшить стиль", studyNow: "Учиться по Диску", working: "Думаю…",
      suggestions: "Yakumo предлагает навыки", accept: "Сохранить навык", dismiss: "Не надо",
      tools: "Инструменты, которые Yakumo написала себе", toolPending: "ждёт вашего решения", toolOn: "включён", toolOff: "выключен",
      enable: "Включить", disable: "Выключить", code: "Код", test: "Проверка",
      toolsHint: "Код выполняется в отдельном процессе: без файлов, сети и программ, не дольше 5 секунд.",
      lessonFrom: { chat: "из разговора", exam: "экзамен в простое", feedback: "после 👎", think: "глубокое размышление", edit: "по вашим правкам", sleep: "укреплён в простое" }, lessons: "Уроки", lessonsHint: "Правила, которые Yakumo вывела сама из ошибок и ваших поправок. Она видит их в каждом разговоре.",
      style: "Стиль ответов", styleHint: "Раз в неделю Yakumo переписывает свою инструкцию «как отвечать». Можно вернуть любую версию.",
      styleOff: "Стиль выключен", turnOff: "Выключить", use: "Вернуть", active: "сейчас",
      wishes: "Чему Yakumo хочет научиться", times: (n) => `×${n}`,
      notes: "Конспекты по вашим темам", links: "Ассоциации",
      linksHint: "Связи между фактами, которые Yakumo нашла, пока вы не работали. На карте — пунктиром.",
      good: "Хороший ответ", bad: "Плохой ответ", whyBad: "Что было не так? (можно пропустить)",
      kindsT2: { feedback: "Разбор 👎", curious: "Любопытство", consolidate: "Уроки", think: "Мысль", edit: "Правки", foresee: "Наперёд", doc: "Документ", ideas: "Идеи" },
      docs: "Читать новые документы", docsHint: "Положили файл на Диск — Yakumo сама прочитает его: суммы, стороны и номера запомнит со ссылкой на файл, сроки добавит в напоминания, о важном напишет в чат и предложит, в какую папку его положить. Тратит фоновые запросы.",
      brain: "Рост мозга", neurons: (n) => `${n} ${plural(n, "нейрон", "нейрона", "нейронов")}`,
      linksN: (n) => `${n} ${plural(n, "связь", "связи", "связей")}`,
      groupMe: "Обо мне", groupHer: "Сама Yakumo",
      dNeurons: "нейронов", dFacts: "фактов", dPeople: "людей и мест", dBudget: "запросов сегодня", dToday: (n) => `+${n} сегодня`,
      dNoLimit: "без лимита",
      uni: { title: "Вселенная Yakumo", zoomIn: "Приблизить", zoomOut: "Отдалить", reset: "Вернуть как было", d3: "Объёмный вид (3D)",
             tour: "Экскурсия: Yakumo облетит ваш мир", next: "Дальше", stopTour: "Остановить",
             hint: "Колесо или кнопки приближают: издали видны галактики, ближе звёзды, совсем близко — факты, документы и обещания. Звёзды можно перетаскивать, в 3D мир вращается мышью.",
             areas: { family: "Семья", friends: "Друзья", work: "Работа", home: "Дом и питомцы", places: "Места", health: "Здоровье",
                      hobby: "Увлечения", other: "Другое" } },
      area: "Галактика",
      zoomIn: "Приблизить", zoomOut: "Отдалить", zoomReset: "Вернуть как было", mapHint: "Звёзды можно перетаскивать, колесо мыши или кнопки приближают, фон двигается мышью.",
      improve: "Улучшения", improveLead: "Что стоит доработать в самой Yakumo. Пункты появляются сами: из её неудач, ошибок программы и её собственных идей. Каждый оформлен как задача; скопируйте и отдайте Claude.",
      impStatuses: { new: "Новые", given: "Отданы", done: "Сделаны", rejected: "Отклонены" },
      impStatus1: { new: "новая", given: "отдана", done: "сделана", rejected: "отклонена" },
      impSources: { wish: "не смогла", thumbs: "👎", error: "ошибка", idea: "идея Yakumo", manual: "вы" },
      impPrio: { high: "важно", normal: "обычно", low: "мелочь" },
      impFields: { problem: "Что не так", steps: "Как воспроизвести", want: "Что хочется", fix: "Где поправить", detail: "Подробности" },
      impCopy: "Скопировать для Claude", impCopyAll: (n) => `Скопировать новые для Claude (${n})`, impCopied: "Скопировано. Вставьте в проект с Claude.",
      impIdeas: "Придумать идеи", impAdd: "Своя задача: что улучшить", impAddBtn: "Добавить", impTimes: (n) => `${n} раз`,
      impReopened: "вернулась", impEmpty: "Пока нечего улучшать", impEmptyHint: "Сюда попадут ошибки программы, ответы с 👎, то, что Yakumo не смогла, и её идеи.",
      impStatusLabel: "Статус",
      selfMap: "Карта меня", selfMapHint: "Yakumo читает свой код (только читает, не меняет): ищет в нём, когда вы спрашиваете, как она что-то делает, и смотрит нужный файл, когда пишет задачу в «Улучшения».",
      selfStat: (c) => `файлов: ${c.files}, кусочков кода: ${c.chunks}` + (c.vectors ? `, по смыслу: ${c.vectors}` : ""),
      core: "Ядро и веб-версия", linesN: (n) => `${n} строк`,
      versions: "История меня", versionKinds: { install: "Обновление", rollback: "Возврат", seen: "Версия" },
      versionsHint: "Когда Yakumo обновили или вернули к прошлой версии и что в ней нового. Она помнит это и может рассказать в чате.",
      changesN: (n) => `изменений: ${n}`,
      brainHint: "Нейроны — всё, что Yakumo знает: факты, люди и места, уроки, конспекты, навыки, разговоры, фрагменты документов. Связи — ассоциации и ссылки между ними.",
      branchesTitle: "Ветки развития", branchesHint: "Один общий мозг растёт по направлениям. Уровень считается из реального опыта, а не задаётся вручную.",
      branchLevel: (n) => `уровень ${n}`, branchXp: (n) => `опыт ${n}`, branchItems: (n) => `узлов ${n}`, branchLinks: (n) => `связей ${n}`,
      neuralLinks: "Нейросвязи", linkStrength: (n) => `сила ${n}%`, linkUses: (n) => `совместных ростов: ${n}`,
      focusTitle: "Автофокус", focusText: (name, action) => `Слабее сейчас: ${name}. Следующая тренировка: ${action}.`,
      focusActions: { consolidate: "укрепление памяти", exam: "экзамен логики", study: "обучение по документам",
                      code_refine: "разбор собственного кода", foresee: "планирование наперёд", ideas: "генерация идей" },
      tiersTitle: "Memory Engine 2.1", tiersHint: "Память сама перемещает знания между слоями, старое не удаляется бесследно.",
      tiers: { operational: "Оперативная", episodic: "Эпизодическая", longterm: "Долговременная", archive: "Архивная" },
      edgeHistory: "История силы связи", noEdgeHistory: "Связь ещё не меняла силу.",
      diagnosticsTitle: "Диагностика памяти и индекса", diagnosticsOk: "Всё согласовано", diagnosticsWarn: "Нужна проверка",
      conflictsTitle: "Возможные противоречия", needsClarification: "требует уточнения",
      vectorCoverage: (n) => `векторы: ${n}%`, indexedDocs: (n) => `интеллект-индекс: ${n} док.`,
      orphanRefs: (n) => `битых ссылок: ${n}`, activityTitle: "Лента активности Yakumo",
      journalTitle: "Временная память и решения",
      traceKinds: { cause: "Причина", decision: "Решение", project_error: "Ошибка проекта", progress: "Ход работы",
                    event: "Событие", promise: "Обещание" },
      openProgress: "незавершено", reason: "Почему", result: "Результат / осталось",
      sourceDocs: "Исходные документы", aliases: "Другие написания", relatedEntities: "Связанные сущности",
      staleThought: "watchdog остановил зависшую мысль",
      best: (n) => `Ответов с 👍 (образцы для стиля): ${n}`,
      curiousNow: "Задать мне вопрос", consolidateNow: "Укрепить уроки", foreseeNow: "Подумать наперёд",
      emptyGrow: "Yakumo только начинает расти", emptyGrowHint: "Уроки, стиль, желания и конспекты появятся после разговоров и первого простоя.",
    },
    en: {
      title: "Brain", facts: "Facts", map: "Map", talks: "Conversations", plans: "Promises & dates", skills: "Skills",
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
      you: "You", sources: { auto: "learned herself", chat: "you asked", manual: "added by hand", module: "from a module", doc: "from a document" },
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
      grow: "Self-development when idle", growHint: "When you are not working with her, Yakumo studies your Drive documents, takes an exam on her own answers and improves her style once a week. Uses background requests from the daily budget.",
      mind: "Mind", growth: "Growth", archive: (n) => `Archive · ${n}`, restore: "Restore from archive",
      archiveHint: "Faded and superseded facts stay in the archive: they are excluded from the prompt but remain searchable as history.",
      modes: { awake: "Awake", drowsy: "Drowsy", asleep: "Asleep" },
      modeHints: { awake: "You wrote recently — Yakumo is with you, only the lightest background work.",
                   drowsy: "The chat is quiet — Yakumo indexes the Drive and computes vectors.",
                   asleep: "You have been away a while — Yakumo sleeps and grows: kitsune sleep, studying documents, exam, style improvement." },
      budget: "Background requests per day", budgetUsed: (u, l) => l ? `Today: ${u} of ${l}` : `Today: ${u}`,
      noLimit: "No limit",
      budgetHint: "Working around the clock uses Cloud.ru requests. When the limit is reached Yakumo rests until tomorrow; chat is never limited.",
      knowledge: (k) => `Knowledge base: ${k.documents} docs, ${k.chunks} chunks, ${k.vectors} with vectors.`,
      noDisk: "Knowledge base: the Drive module is not connected.",
      thoughts: "Thought queue", noThoughts: "All quiet", noThoughtsHint: "Everything Yakumo does on her own shows up here: sleep, study, exams, background tasks.",
      kindsT: { sleep: "Sleep", study: "Study", exam: "Exam", style: "Style", task: "Task" },
      statuses: { queued: "queued", running: "thinking…", done: "done", failed: "failed", cancelled: "cancelled" },
      stop: "Cancel",
      examNow: "Exam now", styleNow: "Improve style", studyNow: "Study the Drive", working: "Thinking…",
      suggestions: "Yakumo suggests skills", accept: "Save skill", dismiss: "No thanks",
      tools: "Tools Yakumo wrote for herself", toolPending: "awaiting your decision", toolOn: "on", toolOff: "off",
      enable: "Enable", disable: "Disable", code: "Code", test: "Test",
      toolsHint: "Code runs in a separate process: no files, network or programs, at most 5 seconds.",
      lessonFrom: { chat: "from a conversation", exam: "idle exam", feedback: "after a 👎", think: "deep thinking", edit: "from your edits", sleep: "strengthened when idle" }, lessons: "Lessons", lessonsHint: "Rules Yakumo derived herself from mistakes and your corrections. She sees them in every conversation.",
      style: "Answer style", styleHint: "Once a week Yakumo rewrites her “how to answer” instruction. Any version can be restored.",
      styleOff: "Style is off", turnOff: "Turn off", use: "Restore", active: "current",
      wishes: "What Yakumo wants to learn", times: (n) => `×${n}`,
      notes: "Notes on your topics", links: "Associations",
      linksHint: "Connections between facts Yakumo found while you were away. Dashed on the map.",
      good: "Good answer", bad: "Bad answer", whyBad: "What was wrong? (optional)",
      kindsT2: { feedback: "👎 review", curious: "Curiosity", consolidate: "Lessons", think: "Thought", edit: "Edits", foresee: "Ahead", doc: "Document", ideas: "Ideas" },
      docs: "Read new documents", docsHint: "Put a file on the Drive and Yakumo reads it herself: remembers amounts, parties and numbers with a link to the file, adds deadlines to reminders, writes to the chat about anything important and suggests a folder. Uses background requests.",
      brain: "Brain growth", neurons: (n) => `${n} ${n === 1 ? "neuron" : "neurons"}`,
      linksN: (n) => `${n} ${n === 1 ? "link" : "links"}`,
      groupMe: "About me", groupHer: "Yakumo herself",
      dNeurons: "neurons", dFacts: "facts", dPeople: "people & places", dBudget: "requests today", dToday: (n) => `+${n} today`,
      dNoLimit: "no limit",
      uni: { title: "Yakumo's universe", zoomIn: "Zoom in", zoomOut: "Zoom out", reset: "Reset view", d3: "3D view",
             tour: "Tour: Yakumo flies through your world", next: "Next", stopTour: "Stop",
             hint: "Zoom with the wheel or buttons: from afar you see galaxies, closer the stars, up close their facts, documents and promises. Drag the stars; in 3D drag to rotate.",
             areas: { family: "Family", friends: "Friends", work: "Work", home: "Home & pets", places: "Places", health: "Health",
                      hobby: "Hobbies", other: "Other" } },
      area: "Galaxy",
      zoomIn: "Zoom in", zoomOut: "Zoom out", zoomReset: "Reset view", mapHint: "Drag the stars, zoom with the mouse wheel or buttons, drag the background to move.",
      improve: "Improvements", improveLead: "What is worth improving in Yakumo herself. Items appear on their own: from her failures, program errors and her own ideas. Each is written as a task; copy it and give it to Claude.",
      impStatuses: { new: "New", given: "Given", done: "Done", rejected: "Rejected" },
      impStatus1: { new: "new", given: "given", done: "done", rejected: "rejected" },
      impSources: { wish: "couldn't", thumbs: "👎", error: "error", idea: "Yakumo's idea", manual: "you" },
      impPrio: { high: "important", normal: "normal", low: "minor" },
      impFields: { problem: "What is wrong", steps: "Steps to reproduce", want: "Desired result", fix: "Where to fix", detail: "Details" },
      impCopy: "Copy for Claude", impCopyAll: (n) => `Copy new for Claude (${n})`, impCopied: "Copied. Paste it into your Claude project.",
      impIdeas: "Come up with ideas", impAdd: "Your own task: what to improve", impAddBtn: "Add", impTimes: (n) => `${n} times`,
      impReopened: "came back", impEmpty: "Nothing to improve yet", impEmptyHint: "Program errors, 👎 answers, things Yakumo couldn't do and her ideas will appear here.",
      impStatusLabel: "Status",
      selfMap: "My map", selfMapHint: "Yakumo reads her own code (read only, never changes it): she searches it when you ask how she does something and looks at the right file when writing a task in Improvements.",
      selfStat: (c) => `files: ${c.files}, code chunks: ${c.chunks}` + (c.vectors ? `, by meaning: ${c.vectors}` : ""),
      core: "Core and web app", linesN: (n) => `${n} lines`,
      versions: "My history", versionKinds: { install: "Update", rollback: "Rollback", seen: "Version" },
      versionsHint: "When Yakumo was updated or rolled back and what was new. She remembers it and can tell you in chat.",
      changesN: (n) => `changes: ${n}`,
      brainHint: "Neurons are everything Yakumo knows: facts, people and places, lessons, notes, skills, conversations, document chunks. Links are associations and references between them.",
      branchesTitle: "Development branches", branchesHint: "One shared brain grows in several directions. Levels come from actual experience, not manual settings.",
      branchLevel: (n) => `level ${n}`, branchXp: (n) => `XP ${n}`, branchItems: (n) => `nodes ${n}`, branchLinks: (n) => `links ${n}`,
      neuralLinks: "Neural links", linkStrength: (n) => `strength ${n}%`, linkUses: (n) => `joint growths: ${n}`,
      focusTitle: "Auto focus", focusText: (name, action) => `Weakest now: ${name}. Next training: ${action}.`,
      focusActions: { consolidate: "memory consolidation", exam: "logic exam", study: "document study",
                      code_refine: "self-code review", foresee: "forward planning", ideas: "idea generation" },
      tiersTitle: "Memory Engine 2.1", tiersHint: "Memory moves knowledge between layers automatically; old knowledge is not silently destroyed.",
      tiers: { operational: "Operational", episodic: "Episodic", longterm: "Long-term", archive: "Archive" },
      edgeHistory: "Link strength history", noEdgeHistory: "This link has not changed strength yet.",
      diagnosticsTitle: "Memory & index diagnostics", diagnosticsOk: "Everything is consistent", diagnosticsWarn: "Review needed",
      conflictsTitle: "Possible conflicts", needsClarification: "needs clarification",
      vectorCoverage: (n) => `vectors: ${n}%`, indexedDocs: (n) => `intelligence index: ${n} docs`,
      orphanRefs: (n) => `broken refs: ${n}`, activityTitle: "Yakumo activity feed",
      journalTitle: "Timeline & decisions",
      traceKinds: { cause: "Cause", decision: "Decision", project_error: "Project error", progress: "Work progress",
                    event: "Event", promise: "Promise" },
      openProgress: "unfinished", reason: "Why", result: "Result / remaining",
      sourceDocs: "Source documents", aliases: "Other spellings", relatedEntities: "Related entities",
      staleThought: "watchdog stopped a stuck thought",
      best: (n) => `Answers with 👍 (style examples): ${n}`,
      curiousNow: "Ask me a question", consolidateNow: "Strengthen lessons", foreseeNow: "Think ahead",
      emptyGrow: "Yakumo is just starting to grow", emptyGrowHint: "Lessons, style, wishes and notes appear after conversations and the first idle time.",
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
                  sleeping: false, archive: false, growing: null, impFilter: "new",
                  mapPos: {}, mapView: { x: 0, y: 0, k: 1 } };
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

  // --- Режим разума на аватаре: бодрствует, дремлет («z») или спит («z z z») ---

  function showMode(mode) {
    const av = document.getElementById("avatar");
    if (!av || !mode) return;
    av.dataset.mind = mode;
    let z = av.querySelector(".br-z");
    if (!z) av.append(z = h("span", { class: "br-z", "aria-hidden": "true" }, h("i", {}, "z"), h("i", {}, "z"), h("i", {}, "z")));
    av.title = (TX[lang()] || TX.ru).modes[mode] || "";
  }

  async function mindPoll() {
    try {
      const m = await getJSON("/api/brain/mind");
      showMode(m.mode);
      if (state.data && state.tab === "mind" && document.body.dataset.page === "brain") {
        state.data.mind = m;
        draw();
      }
    } catch { /* сервер перезапускается */ }
  }
  setTimeout(mindPoll, 1000);
  setInterval(mindPoll, 30000);

  // --- 👍/👎 под ответами Yakumo: хорошие становятся образцами, по плохим она выводит урок ---

  const THUMB = "M7 10v11H3V10h4zm2 11h8.5a2 2 0 0 0 2-1.6l1.4-7A2 2 0 0 0 19 10h-5l.8-4.2a1.6 1.6 0 0 0-2.9-1.2L9 9.5V21z";

  function thumb(down) {
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    if (down) svg.style.transform = "scaleY(-1)";
    const path = document.createElementNS(SVG, "path");
    path.setAttribute("d", THUMB);
    path.setAttribute("fill", "currentColor");
    svg.append(path);
    return svg;
  }

  // universe.js грузится отдельно и может прийти позже — тогда карту перерисовываем.
  document.addEventListener("yakumo-universe", () => { if (state.data && state.tab === "map" && document.body.dataset.page === "brain") draw(); });

  // Живое небо: о ком говорят в чате — к той звезде летит искра (или полетит, когда откроют карту).
  const mentioned = new WeakSet();
  window.Yakumo.addMessageAction?.((m, { question }) => {
    if (!mentioned.has(m) && Date.now() - new Date(m.at || 0).getTime() < 300000) {  // только свежие ответы
      mentioned.add(m);
      window.YakumoUniverse?.mention(`${question || ""} ${m.text || ""}`);
    }
    return null;
  });

  window.Yakumo.addMessageAction?.((m, { question, chatId, save }) => {
    if (!question) return null;
    const rate = async (good) => {
      if (m.rated) return;
      let note = "";
      if (!good) {
        note = prompt(L.whyBad, "");
        if (note === null) return;
      }
      try {
        await postJSON("/api/brain/feedback", { question, answer: m.text, good, note, chat_id: chatId });
        m.rated = good ? "up" : "down";
        save();
      } catch { /* память выключена или сервер недоступен — без оценки */ }
    };
    const btn = (good) => {
      const b = h("button", { type: "button", class: "br-rate" + (m.rated === (good ? "up" : "down") ? " on" : ""),
                              title: good ? L.good : L.bad, "aria-label": good ? L.good : L.bad,
                              disabled: !!m.rated, onclick: () => rate(good) });
      b.append(thumb(!good));
      return b;
    };
    if (m.rated) return btn(m.rated === "up");
    return h("span", { class: "br-rates" }, btn(true), btn(false));
  });

  // --- Запросы ---

  async function load() {
    try {
      state.data = await getJSON("/api/brain");
      state.error = null;
    } catch (e) {
      state.error = e.message;
    }
    draw();
    showMode(state.data?.mind?.mode);
    // Пока Yakumo разбирает разговор или думает над задачей, обновляем страницу, чтобы новое появилось само.
    clearTimeout(timer);
    const thinking = (state.data?.mind?.thoughts || []).some((t) => t.status === "queued" || t.status === "running");
    if ((state.data?.busy || thinking) && document.body.dataset.page === "brain") timer = setTimeout(load, 5000);
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
      switchRow("grow", L.grow, L.growHint, off || !d.cloud),
      switchRow("docs", L.docs, L.docsHint, off || !d.cloud),
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

  // --- Значки групп фактов ---

  const KIND_ICONS = {
    person: '<circle cx="12" cy="8" r="3.6"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/>',
    likes: '<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.4a4.3 4.3 0 0 1 7.5 2.4C19.5 15.4 12 20 12 20z"/>',
    work: '<rect x="3.5" y="7.5" width="17" height="12" rx="2"/><path d="M9 7.5V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1.5M3.5 12.5h17"/>',
    other: '<path d="M12 3.5l2.1 5.4 5.4 2.1-5.4 2.1L12 18.5l-2.1-5.4L4.5 11l5.4-2.1z"/>',
    self: '<path d="M4 4l4.5 4.5h7L20 4l-1 8.5a7 7 0 0 1-14 0z"/><circle cx="9.5" cy="12.5" r=".9"/><circle cx="14.5" cy="12.5" r=".9"/><path d="M11 16h2"/>',
  };

  function kindIcon(k) {
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", "br-kind-icon");
    svg.setAttribute("aria-hidden", "true");
    svg.innerHTML = KIND_ICONS[k] || KIND_ICONS.other;
    return svg;
  }

  // --- Живой мозг: нейроны и связи, растёт вместе со знаниями ---

  function rng(seed) {  // одинаковые места для одних и тех же нейронов: новые просто добавляются
    return () => {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  function insideBrain(x, y) {
    // Два полушария, лобная выпуклость и мозжечок; координаты от -1 до 1.
    const e = (cx, cy, rx, ry) => ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1;
    return (e(-0.24, -0.06, 0.66, 0.78) || e(0.24, -0.06, 0.66, 0.78) || e(0.5, 0.55, 0.3, 0.24)) && Math.abs(x) > 0.03;
  }

  function brainSvg(neurons, links, fresh, w = 300, hgt = 200) {
    const n = Math.max(6, Math.min(170, neurons));
    const rand = rng(17);
    const pts = [];
    while (pts.length < n) {
      const x = rand() * 2 - 1, y = rand() * 2 - 1;
      if (insideBrain(x, y)) pts.push({ x: w / 2 + x * w * 0.42, y: hgt / 2 + y * hgt * 0.45 });
    }
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", `0 0 ${w} ${hgt}`);
    svg.setAttribute("class", "br-brainviz");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", `${L.neurons(neurons)}, ${L.linksN(links)}`);
    const el = (tag, attrs, parent = svg) => {
      const x = document.createElementNS(SVG, tag);
      for (const [k, v] of Object.entries(attrs)) x.setAttribute(k, v);
      parent.append(x);
      return x;
    };
    // Контур: два полушария и мозжечок — мозг узнаётся, даже пока нейронов мало.
    const shape = el("g", { class: "br-bv-shape" });
    for (const [cx, cy, rx, ry] of [[-0.24, -0.06, 0.66, 0.78], [0.24, -0.06, 0.66, 0.78], [0.5, 0.55, 0.3, 0.24]]) {
      el("ellipse", { cx: (w / 2 + cx * w * 0.42).toFixed(1), cy: (hgt / 2 + cy * hgt * 0.45).toFixed(1),
                      rx: (rx * w * 0.42).toFixed(1), ry: (ry * hgt * 0.45).toFixed(1) }, shape);
    }
    el("path", { d: `M${w / 2} ${(hgt * 0.16).toFixed(1)} q ${-w * 0.02} ${hgt * 0.17} 0 ${hgt * 0.34} t 0 ${hgt * 0.3}` }, shape);
    const lines = el("g", { class: "br-bv-links" });
    const limit = Math.min(pts.length * 2, Math.max(pts.length, links + pts.length / 2));
    let made = 0;
    for (let i = 1; i < pts.length && made < limit; i++) {
      const near = pts.slice(0, i).map((q, j) => [Math.hypot(q.x - pts[i].x, q.y - pts[i].y), j]).sort((a, b) => a[0] - b[0]);
      for (const [d, j] of near.slice(0, 2)) {
        if (d > w * 0.18 || made >= limit) continue;
        const line = el("line", { x1: pts[i].x.toFixed(1), y1: pts[i].y.toFixed(1), x2: pts[j].x.toFixed(1), y2: pts[j].y.toFixed(1) }, lines);
        if (made % 7 === 3) line.setAttribute("class", "pulse"), line.style.animationDelay = `${(made % 11) * 0.37}s`;
        made++;
      }
    }
    const dots = el("g", { class: "br-bv-dots" });
    pts.forEach((q, i) => {
      const c = el("circle", { cx: q.x.toFixed(1), cy: q.y.toFixed(1), r: (1.4 + (i % 5) * 0.35).toFixed(2),
                               class: i >= pts.length - Math.min(fresh, pts.length) ? "new" : "" }, dots);
      c.style.animationDelay = `${(i * 0.29) % 4}s`;
    });
    return svg;
  }

  function sparkline(values, w = 300, hgt = 40) {
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", `0 0 ${w} ${hgt}`);
    svg.setAttribute("class", "br-spark");
    svg.setAttribute("preserveAspectRatio", "none");
    svg.setAttribute("aria-hidden", "true");
    if (values.length < 2) return svg;
    const max = Math.max(...values), min = Math.min(...values), span = max - min || 1;
    const pts = values.map((v, i) => `${(i / (values.length - 1) * (w - 4) + 2).toFixed(1)},${(hgt - 3 - (v - min) / span * (hgt - 8)).toFixed(1)}`);
    for (const [tag, attrs] of [["polygon", { points: `2,${hgt} ${pts.join(" ")} ${w - 2},${hgt}`, class: "area" }],
                                ["polyline", { points: pts.join(" ") }]]) {
      const x = document.createElementNS(SVG, tag);
      for (const [k, v] of Object.entries(attrs)) x.setAttribute(k, v);
      svg.append(x);
    }
    return svg;
  }

  function growthNumbers() {
    const days = state.data.brain || [];
    const last = days[days.length - 1] || { neurons: 0, links: 0 };
    const prev = days.length > 1 ? days[days.length - 2].neurons : last.neurons;
    return { days, last, fresh: Math.max(0, last.neurons - prev) };
  }

  // --- Приборная панель: главное одной строкой ---

  function dashboard() {
    const d = state.data;
    const m = d.mind || {};
    const { last, fresh } = growthNumbers();
    const tile = (num, label, extra = "") => h("div", { class: "br-dash-tile" },
      h("strong", {}, String(num)), h("span", {}, label), extra);
    return h("section", { class: "card br-dash" },
      h("div", { class: "br-dash-brain" }, brainSvg(last.neurons, last.links, fresh, 240, 150)),
      h("div", { class: "br-dash-tiles" },
        tile(last.neurons, L.dNeurons, fresh ? h("em", {}, L.dToday(fresh)) : ""),
        tile(d.facts.filter((f) => !f.archived).length, L.dFacts),
        tile(d.entities.filter((e) => e.facts > 0).length, L.dPeople),
        tile(m.budget ? `${m.used} / ${m.budget}` : String(m.used ?? 0), L.dBudget,
          m.budget ? h("i", { class: "br-dash-bar" }, h("b", { style: `width:${Math.min(100, Math.round((m.used || 0) / m.budget * 100))}%` }))
            : h("em", {}, L.dNoLimit)),
        h("div", { class: "br-dash-mode", "data-mode": m.mode },
          h("span", { class: "br-mind-dot" }), h("strong", {}, L.modes[m.mode] || m.mode || ""),
          h("span", { class: "row-hint" }, L.modeHints[m.mode] || ""))));
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
    // Сила памяти — полоска слева: чем важнее и свежее факт, тем ярче; закреплённые — всегда полные.
    const level = f.pinned ? 5 : Math.max(0, Math.min(5, Math.round(f.score)));
    const meter = h("span", { class: `br-stripe l-${level}`, title: L.strength(f.score), "aria-label": L.strength(f.score) });
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
          f.score < 1 && !f.archived ? ` · ${L.faded}` : ""),
        open ? h("div", { class: "br-quote" }, h("b", {}, L.from + ": "),
          f.quote ? L.quote(f.quote) : L.sources[f.source] || "",
          f.talk && talkTitle(f.talk) ? ` — «${talkTitle(f.talk)}»` : "") : ""),
      h("div", { class: "br-tools" },
        f.archived ? tool("↺", L.restore, () => send("fact/restore", { id: f.id })) : "",
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
    if (!state.data.facts.length) return [addForm(), empty(L.emptyFacts, L.emptyFactsHint)];
    if (!facts.length) return [addForm(), empty(L.nothing, "")];
    const archived = facts.filter((f) => f.archived);
    return [addForm(), state.data.kinds.map((k) => {
      const list = facts.filter((f) => f.kind === k && !f.archived);
      return list.length ? h("section", { class: `br-kind k-${k}` },
        h("h2", {}, kindIcon(k), L.kinds[k], h("span", {}, String(list.length))),
        h("ul", { class: "br-list" }, list.map(factEl))) : "";
    }), archived.length ? h("section", { class: "br-kind br-archive" },
      h("h2", {}, h("button", { type: "button", class: "br-link", "aria-expanded": String(state.archive),
                               onclick: () => { state.archive = !state.archive; draw(); } },
        (state.archive ? "▾ " : "▸ ") + L.archive(archived.length))),
      state.archive ? [h("p", { class: "row-hint" }, L.archiveHint), h("ul", { class: "br-list" }, archived.map(factEl))] : "")
      : ""];
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

  // Вселенная: мозг в центре, звёзды по галактикам жизни (universe.js). Пока скрипт не загрузился — старое созвездие.
  function mapView() {
    const ents = (state.data.entities || []).filter((e) => e.facts > 0 && matches(`${e.name} ${e.relation || ""}`));
    if (!ents.length) return empty(state.data.entities?.length ? L.nothing : L.emptyMap, L.emptyMapHint);
    if (!window.YakumoUniverse) return constellationView(ents);
    const host = h("div", { class: "un-host" });
    const panel = h("div", {}, nodePanel());
    const d = state.data;
    window.YakumoUniverse.mount(host, {
      facts: d.facts, entities: ents, areas: d.areas || [], promises: d.promises || [], docs: d.entity_docs || {},
      brain: growthNumbers().last, texts: L.uni,
    }, {
      selected: state.node,
      onPick: (id) => { state.node = id; panel.replaceChildren(nodePanel()); },
      openDoc: (p) => window.open(`/api/disk/file?path=${encodeURIComponent(p)}`, "_blank"),
    });
    return [host, panel];
  }

  function constellationView(ents) {
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
    // Документы: файлы из фактов о людях и проектах — маленькие узлы рядом с ними.
    const docs = {};
    for (const f of state.data.facts) {
      for (const p of f.files || []) {
        for (const id of (f.about || []).filter((x) => byId[x])) {
          if (!docs[p] && Object.keys(docs).length >= 25) continue;
          (docs[p] ||= new Set()).add(id);
        }
      }
    }
    for (const [p, owners] of Object.entries(docs)) {
      const n = { id: "d:" + p, name: p.split("/").pop(), type: "doc", path: p, r: 5 };
      nodes.push(n);
      byId[n.id] = n;
      for (const id of owners) links.push({ a: byId[id], b: n, len: 70, doc: true });
    }
    // Ассоциации из сна: факты связаны — пунктир между людьми и местами, о которых они.
    const factById = Object.fromEntries(state.data.facts.map((f) => [f.id, f]));
    for (const a of state.data.links || []) {
      const left = (factById[a.a]?.about || []).filter((id) => byId[id]);
      const right = (factById[a.b]?.about || []).filter((id) => byId[id]);
      for (const x of left) for (const y of right) {
        const key = [x, y].sort().join("|");
        if (x !== y && !pairs.has(key)) { pairs.add(key); links.push({ a: byId[x], b: byId[y], len: 130, assoc: a.why }); }
      }
    }
    layout(nodes, links, w, hgt);
    for (const n of nodes) {  // звёзды, которые вы передвинули, остаются на своих местах
      const saved = state.mapPos[n.id];
      if (saved && !n.fixed) { n.x = saved[0]; n.y = saved[1]; }
    }
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
    // Фон — россыпь мелких звёзд; он же ловит перетаскивание всей карты.
    const sky = el("g", { class: "br-sky" });
    const rand = rng(5);
    for (let i = 0; i < 90; i++) {
      const c = el("circle", { cx: (rand() * w).toFixed(1), cy: (rand() * hgt).toFixed(1), r: (0.4 + rand() * 0.9).toFixed(2) }, sky);
      c.style.animationDelay = `${(rand() * 6).toFixed(2)}s`;
    }
    const world = el("g", { class: "br-world" });
    const view = state.mapView;
    const apply = () => world.setAttribute("transform", `translate(${view.x.toFixed(1)} ${view.y.toFixed(1)}) scale(${view.k.toFixed(3)})`);
    apply();
    const lineEls = [];
    for (const l of links) {
      const line = el("line", { x1: l.a.x, y1: l.a.y, x2: l.b.x, y2: l.b.y, class: l.assoc ? "assoc" : l.doc ? "doc" : l.side ? "side" : "" }, world);
      if (l.assoc) el("title", {}, line).textContent = l.assoc;
      lineEls.push([l, line]);
    }
    const toWorld = (e) => {
      const pt = svg.createSVGPoint();
      pt.x = e.clientX; pt.y = e.clientY;
      const q = pt.matrixTransform(svg.getScreenCTM().inverse());
      return [(q.x - view.x) / view.k, (q.y - view.y) / view.k, q.x, q.y];
    };
    nodes.forEach((n, i) => {
      const g = el("g", { class: `br-node t-${n.type || "me"}` + (state.node === n.id ? " on" : ""), tabindex: n.fixed ? -1 : 0,
                          transform: `translate(${n.x.toFixed(1)} ${n.y.toFixed(1)})` }, world);
      el("circle", { r: n.r * 1.9, class: "halo" }, g).style.animationDelay = `${(i * 0.53) % 5}s`;
      el("circle", { r: n.r + 8, class: "hit" }, g);  // попасть пальцем легче, чем в маленькую звезду
      el("circle", { r: n.r, class: "core" }, g);
      const label = el("text", { y: n.r + 15 }, g);
      label.textContent = n.name;
      if (n.relation) {
        const sub = el("text", { y: n.r + 28, class: "sub" }, g);
        sub.textContent = n.relation;
      }
      let act = null;
      if (n.path) {
        const openDoc = () => window.open(`/api/disk/file?path=${encodeURIComponent(n.path)}`, "_blank");
        el("title", {}, g).textContent = n.path;
        act = openDoc;
      } else if (!n.fixed) {
        act = () => { state.node = state.node === n.id ? null : n.id; draw(); };
      }
      if (act) g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); act(); } });
      // Перетаскивание звезды; короткое нажатие без сдвига — обычный выбор.
      g.addEventListener("pointerdown", (e) => {
        if (n.fixed) return;
        e.stopPropagation();
        g.setPointerCapture(e.pointerId);
        const [sx, sy] = toWorld(e);
        const ox = n.x, oy = n.y;
        let moved = false;
        const move = (ev) => {
          const [x, y] = toWorld(ev);
          if (!moved && Math.hypot(x - sx, y - sy) * view.k < 4) return;
          moved = true;
          g.classList.add("dragging");
          n.x = ox + x - sx; n.y = oy + y - sy;
          g.setAttribute("transform", `translate(${n.x.toFixed(1)} ${n.y.toFixed(1)})`);
          for (const [l, line] of lineEls) {
            if (l.a === n) { line.setAttribute("x1", n.x); line.setAttribute("y1", n.y); }
            if (l.b === n) { line.setAttribute("x2", n.x); line.setAttribute("y2", n.y); }
          }
        };
        const up = () => {
          g.removeEventListener("pointermove", move);
          g.classList.remove("dragging");
          if (moved) state.mapPos[n.id] = [n.x, n.y];
          else act?.();
        };
        g.addEventListener("pointermove", move);
        g.addEventListener("pointerup", up, { once: true });
        g.addEventListener("pointercancel", () => g.removeEventListener("pointermove", move), { once: true });
      });
    });
    // Приближение колесом (к курсору) и кнопками, сдвиг карты — перетаскиванием фона.
    const zoom = (factor, cx = w / 2, cy = hgt / 2) => {
      const k = Math.max(0.5, Math.min(3, view.k * factor));
      view.x = cx - (cx - view.x) * k / view.k;
      view.y = cy - (cy - view.y) * k / view.k;
      view.k = k;
      apply();
    };
    svg.addEventListener("wheel", (e) => {
      e.preventDefault();
      const [, , x, y] = toWorld(e);
      zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15, x, y);
    }, { passive: false });
    svg.addEventListener("pointerdown", (e) => {
      svg.setPointerCapture(e.pointerId);
      const [, , sx, sy] = toWorld(e);
      const ox = view.x, oy = view.y;
      svg.classList.add("panning");
      const move = (ev) => {
        const [, , x, y] = toWorld(ev);
        view.x = ox + x - sx; view.y = oy + y - sy;
        apply();
      };
      svg.addEventListener("pointermove", move);
      svg.addEventListener("pointerup", () => { svg.removeEventListener("pointermove", move); svg.classList.remove("panning"); }, { once: true });
    });
    const ctl = (text, label, fn) => h("button", { type: "button", class: "br-map-btn", title: label, "aria-label": label, onclick: fn }, text);
    return [h("div", { class: "br-map-wrap" }, svg,
      h("div", { class: "br-map-ctl" },
        ctl("+", L.zoomIn, () => zoom(1.25)), ctl("−", L.zoomOut, () => zoom(0.8)),
        ctl("⟲", L.zoomReset, () => { state.mapPos = {}; state.mapView = { x: 0, y: 0, k: 1 }; draw(); }))),
      h("p", { class: "row-hint br-map-hint" }, L.mapHint), nodePanel()];
  }

  function nodePanel() {
    const e = (state.data.entities || []).find((x) => x.id === state.node);
    if (!e) return "";
    const facts = state.data.facts.filter((f) => (f.about || []).includes(e.id));
    const docs = e.files || [];
    const related = (e.related || []).map((r) => ({ ...r, entity: state.data.entities.find((x) => x.id === r.id) }))
      .filter((r) => r.entity);
    const traces = (state.data.traces || []).filter((x) => (x.about || []).includes(e.id)).slice(0, 12);
    const name = h("input", { class: "text-input", value: e.name, maxlength: 60, "aria-label": L.rename });
    const rel = h("input", { class: "text-input", value: e.relation || "", maxlength: 40, placeholder: L.relation,
                             "aria-label": L.relation });
    const type = select(state.data.entity_types.map((t) => [t, L.types[t]]), e.type);
    const area = select((state.data.areas || []).map((a) => [a, L.uni.areas[a]]), e.area || "other", L.area);
    return h("section", { class: "card br-node-panel" },
      h("form", { class: "br-add", onsubmit: (ev) => {
        ev.preventDefault();
        send("item", { type: "entity", id: e.id, name: name.value, relation: rel.value, entity_type: type.value,
                       ...(area.value !== (e.area || "other") ? { area: area.value } : {}) });
      } }, name, rel, type, area, h("button", { class: "btn primary", type: "submit" }, L.save),
        h("button", { class: "btn br-danger", type: "button",
                      onclick: () => { state.node = null; send("item/delete", { type: "entity", ids: [e.id] }); } }, L.del)),
      e.aliases?.length ? h("div", { class: "br-entity-block" }, h("strong", {}, L.aliases),
        h("div", { class: "br-chips" }, e.aliases.map((x) => h("span", { class: "br-chip" }, x)))) : "",
      docs.length ? h("div", { class: "br-entity-block" }, h("strong", {}, L.sourceDocs),
        h("div", { class: "br-chips" }, docs.slice(0, 30).map((p) =>
          h("a", { class: "br-chip file", target: "_blank", href: `/api/disk/file?path=${encodeURIComponent(p)}` },
            "📄 " + p.split("/").pop())))) : "",
      related.length ? h("div", { class: "br-entity-block" }, h("strong", {}, L.relatedEntities),
        h("div", { class: "br-chips" }, related.map((r) => h("button", { type: "button", class: "br-chip",
          onclick: () => { state.node = r.entity.id; draw(); } }, `${r.entity.name} · ${r.weight}`)))) : "",
      traces.length ? h("div", { class: "br-entity-block" }, h("strong", {}, L.journalTitle),
        h("ul", { class: "br-mini-list" }, traces.map((x) => h("li", {},
          h("b", {}, L.traceKinds[x.kind] || x.kind), " · ", x.text)))) : "",
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

  // --- Разум: режим, бюджет, очередь мыслей ---

  const time = (t) => new Date(t * 1000).toLocaleString(lang(), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

  function diagnosticsCard() {
    const d = state.data.diagnostics || {};
    const m = d.memory || {}, k = d.knowledge || {}, intel = d.intelligence || {};
    const facts = Object.fromEntries((state.data.facts || []).map((f) => [f.id, f.text]));
    const conflicts = state.data.conflicts || [];
    return h("section", { class: "card br-diagnostics " + (d.ok ? "ok" : "warn") },
      h("div", { class: "br-diag-head" }, h("strong", {}, L.diagnosticsTitle),
        h("span", { class: "br-status-chip" }, d.ok ? L.diagnosticsOk : L.diagnosticsWarn)),
      h("div", { class: "br-diag-grid" },
        h("span", {}, `${m.facts || 0} · ${L.dFacts}`),
        h("span", {}, L.vectorCoverage(k.vector_coverage ?? 100)),
        h("span", {}, L.indexedDocs(intel.indexed || 0)),
        h("span", {}, L.orphanRefs(m.orphan_entity_refs || 0))),
      state.data.full_audit ? h("div", { class: "br-conflicts" },
        h("strong", {}, "Аудит девяти разделов"),
        h("div", { class: "br-diag-grid" },
          ...Object.entries(state.data.full_audit.areas || {}).map(([name, stats]) =>
            h("span", {}, name + ": " + (stats.count ?? stats.thoughts ?? stats.versions ?? stats.branches ?? "—")))),
        (state.data.full_audit.issues || []).length ?
          h("ul", { class: "br-mini-list" },
            ...state.data.full_audit.issues.map((issue) => h("li", {},
              h("b", {}, issue.area + ": "), issue.description))) :
          h("p", { class: "row-hint" }, "Автоматических предупреждений пока нет.")) : "",
      conflicts.length ? h("div", { class: "br-conflicts" }, h("strong", {}, `${L.conflictsTitle} · ${conflicts.length}`),
        h("ul", { class: "br-mini-list" }, conflicts.slice(0, 6).map((c) => h("li", {},
          h("span", { class: "br-status-chip warn" }, L.needsClarification), " ",
          `${facts[c.a] || c.a} ↔ ${facts[c.b] || c.b}`)))) : "");
  }

  function activityCard() {
    const items = state.data.activity_feed || [];
    if (!items.length) return "";
    return h("section", { class: "br-kind br-activity" }, h("h2", {}, L.activityTitle, h("span", {}, String(items.length))),
      h("ul", { class: "br-mini-list" }, items.slice(0, 24).map((x) =>
        h("li", {}, h("b", {}, L.traceKinds[x.kind] || L.kindsT[x.detail] || L.kindsT2[x.detail] || x.kind),
          h("span", { class: "br-meta" }, ` · ${time(x.at)}`), h("div", {}, x.title),
          x.detail && x.kind !== "thought" && x.detail !== x.title ? h("small", {}, x.detail) : ""))));
  }

  function journalCard() {
    const items = state.data.timeline || [];
    if (!items.length) return "";
    return h("section", { class: "br-kind br-journal" }, h("h2", {}, L.journalTitle, h("span", {}, String(items.length))),
      h("ul", { class: "br-mini-list" }, items.slice(0, 30).map((x) =>
        h("li", { class: x.status === "open" ? "open" : "" },
          h("div", {}, h("b", {}, L.traceKinds[x.kind] || x.kind),
            x.status === "open" ? h("span", { class: "br-status-chip warn" }, L.openProgress) : ""),
          h("div", {}, x.text || ""),
          x.reason ? h("small", {}, `${L.reason}: ${x.reason}`) : "",
          x.result ? h("small", {}, `${L.result}: ${x.result}`) : "",
          x.files?.length ? h("div", { class: "br-chips" }, x.files.map((p) =>
            h("a", { class: "br-chip file", target: "_blank", href: `/api/disk/file?path=${encodeURIComponent(p)}` },
              "📄 " + p.split("/").pop()))) : ""))));
  }

  function mindView() {
    const m = state.data.mind || {};
    const k = state.data.knowledge || {};
    const budget = select(m.budgets.map((b) => [String(b), b ? String(b) : L.noLimit]), String(m.budget), L.budget);
    budget.onchange = () => send("mind", { budget: Number(budget.value) }).then((res) => {
      if (res) { state.data = { ...state.data, mind: res }; load(); }
    });
    const thoughts = (m.thoughts || []).filter((t) => matches(`${t.title} ${t.result || ""}`));
    return [
      h("section", { class: "card br-mind" },
        h("div", { class: "br-mind-mode", "data-mode": m.mode },
          h("span", { class: "br-mind-dot" }), h("strong", {}, L.modes[m.mode] || m.mode),
          h("span", { class: "row-hint" }, L.modeHints[m.mode] || "")),
        h("label", { class: "row" },
          h("span", { class: "row-text" }, h("span", { class: "row-title" }, L.budget),
            h("span", { class: "row-hint" }, `${L.budgetUsed(m.used, m.budget)}. ${L.budgetHint}`)),
          budget),
        h("p", { class: "row-hint" }, k.available ? L.knowledge(k) : L.noDisk)),
      brainCard(),
      diagnosticsCard(),
      journalCard(),
      activityCard(),
      versionsCard(),
      selfMapCard(),
      h("section", { class: "br-kind" }, h("h2", {}, L.thoughts, h("span", {}, String(thoughts.length))),
        thoughts.length ? h("ul", { class: "br-list" }, thoughts.map((t) => {
          const open = state.open === t.id;
          const live = t.status === "queued" || t.status === "running";
          return h("li", { class: `br-fact br-thought s-${t.status}` },
            h("span", { class: "br-thought-kind" }, L.kindsT[t.kind] || L.kindsT2[t.kind] || t.kind),
            h("div", { class: "br-fact-body" },
              t.result ? h("button", { type: "button", class: "br-link br-fact-text", "aria-expanded": String(open),
                                       onclick: () => { state.open = open ? null : t.id; draw(); } }, t.title)
                : h("div", { class: "br-fact-text" }, t.title),
              h("div", { class: "br-meta" }, h("span", { class: "br-status-chip" }, L.statuses[t.status] || t.status),
                ` · ${time(t.started || t.created)}`, t.steps?.length ? ` · ${t.steps.join(" → ")}` : "",
                t.stale ? ` · ${L.staleThought}` : ""),
              open && t.result ? h("div", { class: "br-quote br-result" }, t.result) : ""),
            h("div", { class: "br-tools" }, live ? tool("■", L.stop, () => send("thought/cancel", { id: t.id }).then(load), "danger") : ""));
        })) : empty(L.noThoughts, L.noThoughtsHint)),
    ];
  }

  function selfMapCard() {
    const c = state.data.code;
    if (!c?.map?.modules?.length) return "";
    const files = (list) => h("ul", { class: "br-quote br-changes" }, list.map((f) =>
      h("li", {}, h("code", {}, f.path), f.lines ? ` · ${L.linesN(f.lines)}` : "", f.about ? ` — ${f.about}` : "")));
    const groups = [...c.map.modules.map((m) => ({ id: "map:" + m.id, name: m.name + (m.version ? ` ${m.version}` : ""),
                                                  about: m.about, files: m.files })),
                    { id: "map:core", name: L.core, about: "", files: c.map.core || [] }];
    return h("section", { class: "br-kind br-versions" }, h("h2", {}, L.selfMap, h("span", {}, String(c.map.modules.length))),
      h("p", { class: "row-hint" }, `${L.selfMapHint} ${L.selfStat(c)}.`),
      h("ul", { class: "br-list" }, groups.map((g) => {
        const open = state.open === g.id;
        return h("li", { class: "br-fact" }, h("div", { class: "br-fact-body" },
          h("button", { type: "button", class: "br-link br-fact-text", "aria-expanded": String(open),
                        onclick: () => { state.open = open ? null : g.id; draw(); } }, g.name),
          g.about ? h("div", { class: "br-meta" }, g.about) : "",
          open ? files(g.files) : ""));
      })));
  }

  function versionsCard() {
    const items = (state.data.versions || []).filter((v) => matches(`${v.title} ${v.revision} ${(v.changes || []).join(" ")}`));
    if (!items.length) return "";
    return h("section", { class: "br-kind br-versions" }, h("h2", {}, L.versions, h("span", {}, String(items.length))),
      h("p", { class: "row-hint" }, L.versionsHint),
      h("ul", { class: "br-list" }, items.map((v) => {
        const open = state.open === v.id;
        const name = v.title || v.revision.slice(0, 7);
        const changes = v.changes || [];
        return h("li", { class: "br-fact" },
          h("span", { class: "br-thought-kind" }, L.versionKinds[v.kind] || v.kind),
          h("div", { class: "br-fact-body" },
            changes.length ? h("button", { type: "button", class: "br-link br-fact-text", "aria-expanded": String(open),
                                           onclick: () => { state.open = open ? null : v.id; draw(); } }, name)
              : h("div", { class: "br-fact-text" }, name),
            h("div", { class: "br-meta" }, `${date(v.at)} · ${v.revision.slice(0, 7)}`,
              changes.length ? ` · ${L.changesN(Math.max(v.total || 0, changes.length))}` : ""),
            open ? h("ul", { class: "br-quote br-changes" }, changes.map((c) => h("li", {}, c))) : ""));
      })));
  }

  function brainCard() {
    const { days, last, fresh } = growthNumbers();
    if (!days.length) return "";
    const grew = days.length > 1 ? last.neurons - days[0].neurons : 0;
    return h("section", { class: "card br-brain" },
      h("div", { class: "br-brain-head" }, h("strong", {}, L.brain),
        h("span", { class: "br-brain-num" }, L.neurons(last.neurons)), h("span", { class: "row-hint" }, L.linksN(last.links)),
        grew > 0 ? h("span", { class: "br-brain-up" }, `+${grew}`) : ""),
      brainSvg(last.neurons, last.links, fresh, 600, 300),
      days.length > 1 ? h("div", { class: "br-spark-wrap", title: days.map((d) => `${day(d.date)}: ${d.neurons}`).join("\n") },
        sparkline(days.map((d) => d.neurons), 600, 44)) : "",
      h("p", { class: "row-hint" }, L.brainHint));
  }

  // --- Рост: предложения, свои инструменты, уроки, стиль, желания, конспекты, ассоциации ---

  async function growNow(what) {
    state.growing = what;
    draw();
    const res = await send("grow", { what });
    state.growing = null;
    if (what === "curious" || what === "foresee") await inbox();
    if (what === "ideas") state.impFilter = "new";
    draw();
  }

  async function copyFor(ids) {
    const res = await send("improvements/copy", ids ? { ids } : {});
    if (!res?.text) return;
    try {
      await navigator.clipboard.writeText(res.text);
    } catch {  // не через localhost: буфер обмена недоступен, копируем по-старому
      const area = h("textarea", { style: "position:fixed;opacity:0" }, res.text);
      document.body.append(area); area.select(); document.execCommand("copy"); area.remove();
    }
    state.msg = { text: L.impCopied };
    draw();
  }

  function improveView() {
    const d = state.data;
    const all = d.improvements || [];
    const items = all.filter((x) => x.status === state.impFilter
      && matches(`${x.title} ${x.problem || ""} ${x.module || ""}`));
    const fresh = all.filter((x) => x.status === "new").length;
    const title = h("input", { class: "text-input", maxlength: 200, placeholder: L.impAdd, "aria-label": L.impAdd });
    const add = () => title.value.trim() && send("improvement", { title: title.value.trim() });
    return [
      h("p", { class: "row-hint br-section-hint" }, L.improveLead),
      h("div", { class: "br-grow-actions" },
        h("button", { class: "btn primary", type: "button", disabled: !fresh, onclick: () => copyFor(null) }, L.impCopyAll(fresh)),
        h("button", { class: "btn", type: "button", disabled: !(d.cloud && d.enabled) || !!state.growing,
                      onclick: () => growNow("ideas") }, state.growing === "ideas" ? L.working : L.impIdeas),
        h("button", { class: "btn", type: "button", disabled: !(d.cloud && d.enabled) || !!state.growing,
                      onclick: () => growNow("audit") }, state.growing === "audit" ? L.working : "ИИ-аудит пробелов")),
      h("div", { class: "br-add" }, title, h("button", { class: "btn", type: "button", onclick: add }, L.impAddBtn)),
      h("div", { class: "br-imp-filter", role: "tablist" }, Object.entries(L.impStatuses).map(([id, label]) => h("button", {
        type: "button", role: "tab", class: "br-chip" + (state.impFilter === id ? " on" : ""), "aria-selected": String(state.impFilter === id),
        onclick: () => { state.impFilter = id; draw(); } }, `${label} · ${all.filter((x) => x.status === id).length}`))),
      items.length ? h("ul", { class: "br-list" }, items.map((x) => {
        const open = state.open === x.id;
        const status = select(Object.entries(L.impStatus1), x.status, L.impStatusLabel);
        status.onchange = () => send("improvement", { id: x.id, status: status.value });
        return h("li", { class: `br-fact br-imp p-${x.priority || "normal"}` },
          h("span", { class: "br-thought-kind" }, L.impSources[x.source] || x.source),
          h("div", { class: "br-fact-body" },
            h("button", { type: "button", class: "br-link br-fact-text", "aria-expanded": String(open),
                          onclick: () => { state.open = open ? null : x.id; draw(); } }, x.title),
            h("div", { class: "br-meta" }, [x.module, x.priority ? L.impPrio[x.priority] : "", date(x.last || x.created),
              (x.count || 1) > 1 ? L.impTimes(x.count) : "", x.reopened && x.status === "new" ? L.impReopened : ""].filter(Boolean).join(" · ")),
            open ? h("div", { class: "br-quote br-imp-body" }, ["problem", "steps", "want", "fix"].filter((k) => x[k]).map((k) =>
              h("p", {}, h("b", {}, `${L.impFields[k]}: `), x[k])),
              x.detail ? [h("b", {}, L.impFields.detail), h("pre", { class: "br-code" }, x.detail)] : "") : "",
            open ? h("div", { class: "br-add br-imp-actions" }, status,
              h("button", { class: "btn", type: "button", onclick: () => copyFor([x.id]) }, L.impCopy)) : ""),
          h("div", { class: "br-tools" }, tool("✕", L.del, () => send("item/delete", { type: "improvements", ids: [x.id] }), "danger")));
      })) : empty(L.impEmpty, L.impEmptyHint),
    ];
  }

  function section(title, count, hint, body) {
    return h("section", { class: "br-kind" }, h("h2", {}, title, count != null ? h("span", {}, String(count)) : ""),
      hint ? h("p", { class: "row-hint br-section-hint" }, hint) : "", body);
  }

  function developmentMap(data, names, focus) {
    const items = data?.branches || [];
    if (!items.length) return "";
    const pos = {
      memory: [105, 170], documents: [240, 70], logic: [370, 160], code: [540, 70],
      work: [235, 285], planning: [420, 285], creativity: [625, 185],
    };
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", "0 0 730 360");
    svg.setAttribute("class", "br-devmap");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", L.branchesTitle);
    const make = (tag, attrs, parent = svg) => {
      const x = document.createElementNS(SVG, tag);
      Object.entries(attrs).forEach(([k, v]) => x.setAttribute(k, v));
      parent.append(x); return x;
    };
    const edges = make("g", { class: "br-dev-edges" });
    for (const e of data.edges || []) {
      const a = pos[e.from], b = pos[e.to];
      if (!a || !b) continue;
      const recent = e.last_used && Date.now() / 1000 - e.last_used < 2 * 86400;
      const line = make("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1],
        class: recent ? "pulse" : "", "data-strength": e.strength }, edges);
      line.style.strokeWidth = String(1.2 + (e.strength || 0) / 13);
      const title = make("title", {}, line);
      title.textContent = `${names[e.from]} → ${names[e.to]} · ${L.linkStrength(e.strength)}`;
    }
    const nodes = make("g", { class: "br-dev-nodes" });
    for (const b of items) {
      const p = pos[b.id] || [365, 175];
      const g = make("g", { class: "br-dev-node" + (focus.id === b.id ? " focus" : ""),
                            transform: `translate(${p[0]} ${p[1]})` }, nodes);
      make("circle", { r: 34 + Math.min(12, b.level * 2) }, g);
      const t = make("text", { y: -2, "text-anchor": "middle" }, g); t.textContent = names[b.id];
      const lvl = make("text", { y: 17, "text-anchor": "middle", class: "level" }, g); lvl.textContent = `L${b.level}`;
    }
    return svg;
  }

  function branchesCard() {
    const data = state.data.branches;
    const items = data?.branches || [];
    if (!items.length) return "";
    const names = Object.fromEntries(items.map((b) => [b.id, b.name?.[lang()] || b.name?.ru || b.id]));
    const focus = data.focus || {};
    const tiers = state.data.memory_tiers || {};
    return h("section", { class: "card br-branch-card" },
      h("div", { class: "br-brain-head" }, h("strong", {}, L.branchesTitle)),
      h("p", { class: "row-hint br-section-hint" }, L.branchesHint),
      developmentMap(data, names, focus),
      focus.id ? h("div", { class: "br-focus" },
        h("strong", {}, L.focusTitle),
        h("span", {}, L.focusText(names[focus.id] || focus.id, L.focusActions[focus.action] || focus.action))) : "",
      h("div", { class: "br-branches" }, items.map((b) =>
        h("div", { class: "br-branch" + (focus.id === b.id ? " focus" : ""), "data-branch": b.id },
          h("div", { class: "br-branch-head" },
            h("strong", {}, names[b.id]),
            h("span", { class: "br-status-chip" }, L.branchLevel(b.level))),
          h("span", { class: "br-branch-progress", "aria-label": `${b.progress}%` },
            h("b", { style: `width:${b.progress}%` })),
          h("div", { class: "br-meta" },
            [L.branchXp(b.xp), L.branchItems(b.items), L.branchLinks(b.links)].join(" · "))))),
      h("div", { class: "br-neural-title" }, L.neuralLinks),
      h("div", { class: "br-neural" }, (data.edges || []).map((e) => {
        const id = `edge:${e.from}:${e.to}`, open = state.open === id, history = e.history || [];
        const recent = e.last_used && Date.now() / 1000 - e.last_used < 2 * 86400;
        return h("div", { class: "br-edge" + (recent ? " pulse" : "") },
          h("button", { type: "button", class: "br-edge-toggle", onclick: () => { state.open = open ? null : id; draw(); } },
            h("span", { class: "br-edge-names" }, `${names[e.from] || e.from} → ${names[e.to] || e.to}`),
            h("span", { class: "br-edge-meter" }, h("b", { style: `width:${e.strength}%` })),
            h("span", { class: "br-meta" }, `${L.linkStrength(e.strength)} · ${L.linkUses(e.uses)}`)),
          open ? h("div", { class: "br-edge-history" }, h("strong", {}, L.edgeHistory),
            history.length ? [sparkline(history.map((x) => x.strength), 420, 42),
              h("div", { class: "br-meta" }, history.slice(-6).map((x) =>
                `${date(x.at)}: ${x.strength}% (${x.delta > 0 ? "+" : ""}${x.delta})`).join(" · "))]
              : h("p", { class: "row-hint" }, L.noEdgeHistory)) : "");
      })),
      h("div", { class: "br-memory-tiers" },
        h("div", { class: "br-neural-title" }, L.tiersTitle),
        h("p", { class: "row-hint" }, L.tiersHint),
        h("div", { class: "br-tier-grid" }, Object.entries(L.tiers).map(([id, label]) =>
          h("div", { class: `br-tier t-${id}` }, h("strong", {}, String(tiers[id] || 0)), h("span", {}, label))))));
  }

  function growView() {
    const d = state.data;
    const cloud = d.cloud && d.enabled;
    const btn = (what, label) => h("button", { class: "btn", type: "button", disabled: !cloud || !!state.growing,
                                               onclick: () => growNow(what) }, state.growing === what ? L.working : label);
    const facts = Object.fromEntries(d.facts.map((f) => [f.id, f.text]));
    const del = (type, id) => tool("✕", L.del, () => send("item/delete", { type, ids: [id] }), "danger");
    const styleVersions = [...(d.style.versions || [])].reverse();
    const active = styleVersions.find((v) => v.id === d.style.active);
    const anything = d.suggestions.length + d.user_tools.length + d.lessons.length + styleVersions.length
      + d.wishes.length + d.notes.length + d.links.length;
    return [
      branchesCard(),
      h("div", { class: "br-grow-actions" }, btn("exam", L.examNow), btn("style", L.styleNow), btn("study", L.studyNow),
        btn("curious", L.curiousNow), btn("consolidate", L.consolidateNow), btn("foresee", L.foreseeNow)),
      d.best ? h("p", { class: "row-hint" }, L.best(d.best)) : "",
      !anything ? empty(L.emptyGrow, L.emptyGrowHint) : "",
      d.suggestions.length ? section(L.suggestions, d.suggestions.length, "", h("ul", { class: "br-list" }, d.suggestions.map((s) => {
        const name = h("input", { class: "text-input", value: s.name, maxlength: 60, "aria-label": L.rename });
        return h("li", { class: "br-fact br-suggestion" }, h("div", { class: "br-fact-body" },
          h("div", { class: "br-meta" }, s.signature),
          h("ol", { class: "br-steps" }, s.steps.map((x) => h("li", {}, x))),
          h("div", { class: "br-add" }, name,
            h("button", { class: "btn primary", type: "button", onclick: () => send("suggestion", { id: s.id, accept: true, name: name.value }) }, L.accept),
            h("button", { class: "btn", type: "button", onclick: () => send("suggestion", { id: s.id, accept: false }) }, L.dismiss))));
      }))) : "",
      d.user_tools.length ? section(L.tools, d.user_tools.length, L.toolsHint, h("ul", { class: "br-list" }, d.user_tools.map((t) => {
        const open = state.open === t.id || t.status === "pending";
        return h("li", { class: `br-fact br-utool s-${t.status}` }, h("div", { class: "br-fact-body" },
          h("button", { type: "button", class: "br-link br-skill-name", "aria-expanded": String(open),
                        onclick: () => { state.open = state.open === t.id ? null : t.id; draw(); } }, "my_" + t.name),
          h("div", { class: "br-fact-text" }, t.description),
          h("div", { class: "br-meta" }, h("span", { class: "br-status-chip" },
            t.status === "on" ? L.toolOn : t.status === "off" ? L.toolOff : L.toolPending)),
          open ? [h("pre", { class: "br-code", "aria-label": L.code }, t.code),
                  h("div", { class: "br-meta" }, `${L.test}: ${JSON.stringify(t.example)} → ${JSON.stringify(t.test)}`)] : "",
          h("div", { class: "br-add br-utool-actions" },
            t.status !== "on" ? h("button", { class: "btn primary", type: "button", onclick: () => send("tool", { id: t.id, action: "on" }) }, L.enable)
              : h("button", { class: "btn", type: "button", onclick: () => send("tool", { id: t.id, action: "off" }) }, L.disable),
            h("button", { class: "btn br-danger", type: "button", onclick: () => send("tool", { id: t.id, action: "delete" }) }, L.del))));
      }))) : "",
      d.lessons.length ? section(L.lessons, d.lessons.length, L.lessonsHint, h("ul", { class: "br-list" }, d.lessons.map((x) =>
        h("li", { class: "br-fact" }, h("div", { class: "br-fact-body" }, h("div", { class: "br-fact-text" }, x.text),
          h("div", { class: "br-meta" }, `${L.lessonFrom[x.source] || x.source} · ${date(x.created)}`
            + (x.seen > 1 ? ` · ${L.times(x.seen)}` : ""))),
          h("div", { class: "br-tools" }, del("lessons", x.id)))))) : "",
      styleVersions.length ? section(L.style, null, L.styleHint, [
        h("div", { class: "card br-style" }, active ? h("div", { class: "br-style-text" }, active.text) : h("p", { class: "row-hint" }, L.styleOff),
          active ? h("button", { class: "btn", type: "button", onclick: () => send("style", { id: null }) }, L.turnOff) : ""),
        h("ul", { class: "br-list" }, styleVersions.map((v) => h("li", { class: "br-fact" + (v.id === d.style.active ? " pinned" : "") },
          h("div", { class: "br-fact-body" }, h("div", { class: "br-fact-text" }, v.why || v.text.slice(0, 120)),
            h("div", { class: "br-meta" }, date(v.created) + (v.id === d.style.active ? ` · ${L.active}` : ""))),
          v.id !== d.style.active ? h("button", { class: "btn", type: "button", onclick: () => send("style", { id: v.id }) }, L.use) : ""))),
      ]) : "",
      d.wishes.length ? section(L.wishes, d.wishes.length, "", h("ul", { class: "br-list" }, d.wishes.map((x) =>
        h("li", { class: "br-fact" }, h("div", { class: "br-fact-body" }, h("div", { class: "br-fact-text" }, x.text),
          h("div", { class: "br-meta" }, `${date(x.last || x.created)} · ${L.times(x.count || 1)}`)),
          h("div", { class: "br-tools" }, del("wishes", x.id)))))) : "",
      d.notes.length ? section(L.notes, d.notes.length, "", h("ul", { class: "br-list" }, d.notes.map((n) => {
        const open = state.open === n.id;
        return h("li", { class: "br-fact" }, h("div", { class: "br-fact-body" },
          h("button", { type: "button", class: "br-link br-skill-name", "aria-expanded": String(open),
                        onclick: () => { state.open = open ? null : n.id; draw(); } }, n.topic),
          h("div", { class: "br-meta" }, date(n.created)),
          open ? h("div", { class: "br-quote br-result" }, n.summary) : "",
          h("div", { class: "br-chips" }, (n.sources || []).map((p) => h("a", { class: "br-chip file", target: "_blank",
            href: `/api/disk/file?path=${encodeURIComponent(p)}`, title: L.openFile }, "📄 " + p.split("/").pop())))),
          h("div", { class: "br-tools" }, del("notes", n.id)));
      }))) : "",
      d.links.length ? section(L.links, d.links.length, L.linksHint, h("ul", { class: "br-list" }, d.links.map((x) =>
        h("li", { class: "br-fact" }, h("div", { class: "br-fact-body" },
          h("div", { class: "br-fact-text" }, `${facts[x.a] || "?"} ↔ ${facts[x.b] || "?"}`),
          h("div", { class: "br-meta" }, x.why)),
          h("div", { class: "br-tools" }, del("links", x.id)))))) : "",
    ];
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
    const growing = d.suggestions.length + d.user_tools.length + d.lessons.length + (d.style.versions || []).length
      + d.wishes.length + d.notes.length + d.links.length;
    const groups = [
      [L.groupMe, [["facts", L.facts, d.facts.length], ["map", L.map, d.entities.filter((e) => e.facts > 0).length],
                   ["talks", L.talks, d.talks.length], ["plans", L.plans, openPromises + d.events.length],
                   ["skills", L.skills, d.skills.length]]],
      [L.groupHer, [["mind", L.mind, (d.mind.thoughts || []).length + (d.versions || []).length],
                    ["grow", L.growth, growing],
                    ["improve", L.improve, (d.improvements || []).filter((x) => x.status === "new").length]]]];
    const views = { facts: factsView, map: mapView, talks: talksView, plans: plansView, skills: skillsView,
                    mind: mindView, grow: growView, improve: improveView };
    root.replaceChildren(
      h("div", { class: "br-head" },
        h("div", {}, h("h1", {}, L.title), h("p", { class: "br-lead" }, L.lead(d.facts.length, d.talks.length))),
        h("div", { class: "br-actions" },
          h("button", { class: "btn", type: "button", onclick: exportFile }, L.exp),
          h("button", { class: "btn", type: "button", onclick: importFile }, L.imp),
          h("button", { class: "btn br-danger", type: "button", disabled: !d.facts.length && !d.talks.length,
                        onclick: () => confirm(L.clearAsk) && send("clear", { all: true }) }, L.clear))),
      dashboard(),
      state.msg?.text ? h("p", { class: "row-hint br-msg " + (state.msg.bad ? "bad" : "good") }, state.msg.text) : "",
      settingsCard(),
      h("div", { class: "br-tabs" },
        h("div", { class: "br-tablist", role: "tablist" }, groups.map(([title, tabs], gi) => h("div", { class: "br-tabgroup" },
          h("span", { class: "br-tabgroup-name", "aria-hidden": "true" }, title),
          h("div", { class: "br-tabgroup-tabs" }, tabs.map(([id, label, n]) => h("button", {
            type: "button", role: "tab", "aria-selected": String(state.tab === id), class: state.tab === id ? "on" : "",
            "data-group": String(gi), onclick: () => { state.tab = id; state.open = null; draw(); } },
            label, n ? h("span", {}, String(n)) : "")))))),
        h("div", { class: "br-search" }, search)),
      h("div", { class: "br-view" }, views[state.tab]()));
    const list = root.querySelector(".br-tablist"), on = list?.querySelector("button.on");
    if (on && (on.offsetLeft < list.scrollLeft || on.offsetLeft + on.offsetWidth > list.scrollLeft + list.clientWidth)) {
      list.scrollLeft = on.offsetLeft - 24;  // только по горизонтали: страница не прыгает
    }
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
