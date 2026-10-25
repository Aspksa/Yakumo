"""Фоновый «разум» Yakumo: работает круглые сутки, пока программа запущена.

Три режима, как у живого существа: «бодрствует», пока вы пишете; «дремлет» —
лёгкие дела (векторы, база знаний); «спит» — глубокая работа (сон, учёба,
тренировки). Всё, что разум делает, видно в очереди мыслей. Запросы к Cloud.ru
в фоне ограничены суточным бюджетом, чтобы 24/7 не стоило лишних денег.
"""

from __future__ import annotations

import logging
import time

from .store import today

log = logging.getLogger("yakumo.modules.brain")

AWAKE = 5 * 60      # столько секунд после последней реплики Yakumo «бодрствует»
ASLEEP = 60 * 60    # а после стольких тишины — «спит»
NIGHT = (1, 6)      # ночью засыпает быстрее: через 10 минут тишины
BUDGETS = (50, 150, 300, 1000, 0)  # запросов в сутки на фоновую работу; 0 — без ограничения
MAX_THOUGHTS = 100
STALE_THOUGHT = 15 * 60  # без пульса дольше этого мысль считается зависшей
MAX_RETRIES = 1


class BudgetError(RuntimeError):
    """Суточный бюджет фоновых запросов исчерпан."""


class Mind:
    def __init__(self, memory, cloud, learner):
        self.memory = memory
        self.cloud = cloud
        self.learner = learner
        self.jobs: list[tuple[str, str, int, object]] = []  # (имя, режим, раз в сколько секунд, функция)
        self.last_run: dict[str, float] = {}
        self.retry_task = None  # Tasks.retry; задаётся после создания очереди

    # --- Режим ---

    def mode(self, now: float | None = None) -> str:
        now = now or time.time()
        idle = now - self.learner.last_chat
        hour = time.localtime(now).tm_hour
        if idle < AWAKE:
            return "awake"
        if idle >= ASLEEP or (NIGHT[0] <= hour < NIGHT[1] and idle >= 10 * 60):
            return "asleep"
        return "drowsy"

    # --- Бюджет ---

    @property
    def limit(self) -> int:
        value = self.memory.data["meta"].get("budget", 300)
        return value if value in BUDGETS else 300

    def set_limit(self, value) -> None:
        if value not in BUDGETS:
            raise ValueError("Недопустимый бюджет")
        self.memory.data["meta"]["budget"] = value
        self.memory.save()

    def used(self) -> int:
        usage = self.memory.data["meta"].get("usage") or {}
        return usage.get("calls", 0) if usage.get("date") == today() else 0

    def complete(self, messages: list[dict], max_tokens: int = 1000) -> str:
        """Запрос к Cloud.ru от фоновой работы — с учётом бюджета."""
        if self.limit and self.used() >= self.limit:
            raise BudgetError("budget")
        with self.memory.lock:
            self.memory.data["meta"]["usage"] = {"date": today(), "calls": self.used() + 1}
        return self.cloud.complete(messages, max_tokens=max_tokens)

    def can_think(self) -> bool:
        return bool(self.cloud and self.cloud.api_key()) and (not self.limit or self.used() < self.limit)

    # --- Очередь мыслей ---

    def thought(self, kind: str, title: str, status: str = "running", **extra) -> dict:
        now = int(time.time())
        return self.memory.add_item("thoughts", {"kind": kind, "title": title[:200], "status": status,
                                                 "started": now, "heartbeat": now, "generation": 0, **extra},
                                    MAX_THOUGHTS)

    def heartbeat(self, item: dict) -> None:
        """Признак живой работы; watchdog смотрит именно на него, а не на время создания."""
        with self.memory.lock:
            if item.get("status") in ("queued", "running"):
                item["heartbeat"] = int(time.time())
                self.memory.save()

    def finish(self, item: dict, status: str = "done", result: str | None = None,
               generation: int | None = None) -> bool:
        with self.memory.lock:
            # Ответ/ошибка старого запуска не может менять состояние уже начатого повтора.
            if generation is not None and int(item.get("generation", 0)) != generation:
                return False
            # Поздний ответ уже остановленной/отменённой операции не должен воскресить её как «готово».
            if status == "done" and item.get("status") in ("failed", "cancelled"):
                return False
            item.update(status=status, finished=int(time.time()), heartbeat=int(time.time()))
            if result:
                item["result"] = result[:4000]
            self.memory.save()
            return True

    def watchdog(self, now: float | None = None) -> int:
        """Остановить зависшие мысли; фоновую пользовательскую задачу один раз безопасно переочередить."""
        now = int(now or time.time())
        changed = 0
        retry = []
        with self.memory.lock:
            for item in self.memory.data["thoughts"]:
                if item.get("status") != "running":
                    continue
                heartbeat = int(item.get("heartbeat", item.get("started", item.get("created", now))) or now)
                if now - heartbeat < STALE_THOUGHT:
                    continue
                changed += 1
                if item.get("kind") == "task" and int(item.get("retries", 0)) < MAX_RETRIES and self.retry_task:
                    item.update(status="queued", retries=int(item.get("retries", 0)) + 1,
                                generation=int(item.get("generation", 0)) + 1, heartbeat=now, stale=True,
                                result="Задача зависла и поставлена в очередь на один безопасный повтор.")
                    retry.append(item)
                else:
                    item.update(status="failed", finished=now, heartbeat=now, stale=True,
                                result="Остановлено: задача не подавала признаков работы больше 15 минут.")
            if changed:
                self.memory.save()
        for item in retry:
            try:
                self.retry_task(item)
            except Exception:  # noqa: BLE001
                log.exception("Память: не удалось переочередить зависшую задачу")
                self.finish(item, "failed", "Не удалось запустить безопасный повтор.")
        return changed

    def cancel(self, item_id: str) -> bool:
        with self.memory.lock:
            item = self.memory.item("thoughts", item_id)
            if not item or item["status"] not in ("queued", "running"):
                return False
            self.finish(item, "cancelled")
            return True

    # --- Цикл ---

    def every(self, name: str, mode: str, seconds: int, fn) -> None:
        """Фоновое дело: mode — "any", "rest" (дремлет или спит) или "asleep"."""
        self.jobs.append((name, mode, seconds, fn))

    def tick(self) -> None:
        mode = self.mode()
        for name, need, seconds, fn in self.jobs:
            if need == "rest" and mode == "awake" or need == "asleep" and mode != "asleep":
                continue
            if time.time() - self.last_run.get(name, 0) < seconds:
                continue
            self.last_run[name] = time.time()
            try:
                fn()
            except BudgetError:
                log.info("Память: бюджет фоновых запросов на сегодня исчерпан")
            except Exception:  # noqa: BLE001 — одно дело не должно останавливать остальные
                log.exception("Память: ошибка фонового дела %s", name)

    def status(self) -> dict:
        thoughts = sorted(self.memory.data["thoughts"], key=lambda t: -t.get("created", 0))
        return {"mode": self.mode(), "budget": self.limit, "used": self.used(), "budgets": list(BUDGETS),
                "stale": sum(bool(t.get("stale")) for t in thoughts),
                "running": sum(t.get("status") == "running" for t in thoughts),
                "thoughts": thoughts[:40]}
