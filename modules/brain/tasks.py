"""Длинные задачи в фоне: «разбери все договоры и составь таблицу сроков».

Yakumo ставит задачу в очередь мыслей и выполняет её сама, по шагам, теми же
инструментами, что и в чате, но только читающими (ничего не меняет без
спроса). Пока идёт задача, можно спокойно разговаривать. Результат приходит
сообщением в чат; задачу можно отменить на вкладке «Разум».
"""

from __future__ import annotations

import json
import logging
import queue
import threading

log = logging.getLogger("yakumo.modules.brain")

MAX_STEPS = 8           # обращений к инструментам за задачу
MAX_RESULT = 6000       # символов результата одного инструмента
SKIP = ("background_task", "tool_propose")

PROMPT = {
    "ru": ("Ты — Yakumo и выполняешь в фоне задачу пользователя. Работай по шагам. Чтобы вызвать инструмент, напиши "
           'отдельной строкой <tool>{{"name": "имя", "args": {{...}}}}</tool> и закончи сообщение — результат придёт '
           "следующим сообщением. Когда всё готово, напиши итог для пользователя без вызовов инструментов: кратко, по "
           "делу, Markdown можно, ссылки на файлы вида [имя](disk:путь). Ничего не выдумывай.\n\n"
           "Инструменты (только чтение):\n{tools}\n\nЗадача: {task}"),
    "en": ("You are Yakumo running the user's task in the background. Work step by step. To call a tool write on its own "
           'line <tool>{{"name": "name", "args": {{...}}}}</tool> and end the message — the result comes in the next '
           "message. When done, write the result for the user without tool calls: brief, to the point, Markdown allowed, "
           "file links like [name](disk:path). Don't make things up.\n\nTools (read-only):\n{tools}\n\nTask: {task}"),
}


class Tasks:
    def __init__(self, memory, mind, tools: dict, language):
        self.memory = memory
        self.mind = mind
        self.tools = tools              # ctx.chat_tools
        self.language = language
        self.queue: queue.Queue = queue.Queue()
        self.thread: threading.Thread | None = None
        self.stopping = False

    def add(self, task: str, title: str = "") -> dict:
        task = " ".join(task.split())[:2000]
        item = self.mind.thought("task", " ".join(title.split()) or task[:80], "queued", task=task)
        self.queue.put(item["id"])
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._run, name="brain-tasks", daemon=True)
            self.thread.start()
        return item

    def retry(self, item: dict) -> None:
        """Watchdog переочередил задачу; старый запуск не сможет записать поздний результат."""
        self.queue.put(item["id"])
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._run, name="brain-tasks", daemon=True)
            self.thread.start()

    def resume(self) -> None:
        """После перезапуска: незаконченные задачи — снова в очередь."""
        for item in self.memory.data["thoughts"]:
            if item.get("kind") == "task" and item.get("status") in ("queued", "running"):
                item["status"] = "queued"
                item["generation"] = int(item.get("generation", 0)) + 1
                item["heartbeat"] = int(__import__("time").time())
                self.queue.put(item["id"])
        if not self.queue.empty():
            self.thread = threading.Thread(target=self._run, name="brain-tasks", daemon=True)
            self.thread.start()

    def stop(self) -> None:
        self.stopping = True
        self.queue.put(None)

    def _run(self) -> None:
        while not self.stopping:
            try:
                item_id = self.queue.get(timeout=30)
            except queue.Empty:
                return
            item = item_id and self.memory.item("thoughts", item_id)
            if not item or item["status"] != "queued":
                continue
            try:
                self.run(item)
            except Exception as exc:  # noqa: BLE001
                log.warning("Память: фоновая задача не выполнена: %s", exc)
                self.mind.finish(item, "failed", str(exc) or type(exc).__name__)

    def _listing(self) -> str:
        return "\n".join(f"- {t.name}: {t.description}" for t in self.tools.values()
                         if not t.change and t.name not in SKIP)

    def run(self, item: dict) -> str | None:
        from yakumo.core.cloud import _tool_calls, _visible

        lang = "en" if self.language() == "en" else "ru"
        generation = int(item.get("generation", 0))
        with self.memory.lock:
            item["status"] = "running"
            item["steps"] = []
            item["heartbeat"] = int(__import__("time").time())
            self.memory.save()

        def alive() -> bool:
            return item.get("status") == "running" and int(item.get("generation", 0)) == generation

        messages = [{"role": "user", "content": PROMPT[lang].format(tools=self._listing(), task=item["task"])}]
        for _ in range(MAX_STEPS + 1):
            if not alive():
                return None
            self.mind.heartbeat(item)
            text = self.mind.complete(messages, max_tokens=2000)
            if not alive():
                return None
            self.mind.heartbeat(item)
            calls = _tool_calls(text)
            if not calls:
                break
            messages.append({"role": "assistant", "content": text})
            results = []
            for name, args in calls[:3]:
                if not alive():
                    return None
                self.mind.heartbeat(item)
                tool = self.tools.get(name)
                if tool is None or tool.change or name in SKIP:
                    result = {"error": "Нет такого инструмента (или он меняет данные)"}
                else:
                    try:
                        result = tool.run(args)
                    except Exception as exc:  # noqa: BLE001
                        result = {"error": str(exc) or type(exc).__name__}
                dump = json.dumps(result, ensure_ascii=False, default=str)[:MAX_RESULT]
                results.append(f"{name}: {dump}")
                with self.memory.lock:
                    item["steps"] = [*item.get("steps", []), name][-20:]
                    self.memory.save()
            messages.append({"role": "user", "content": "\n\n".join(results)})
        else:
            text = ""
        if not alive():
            return None
        answer = _visible(text).strip() or ("Не получилось довести задачу до конца." if lang == "ru"
                                            else "I couldn't finish the task.")
        if not self.mind.finish(item, "done", answer):
            return None
        head = "Готово: «{}»" if lang == "ru" else "Done: “{}”"
        self.memory.say(head.format(item["title"]) + "\n\n" + answer, "task")
        return answer
