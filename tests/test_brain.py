import json
import logging
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from yakumo.core.cloud import CloudService
from yakumo.core.config import Config
from yakumo.core.modules import Context, load_all
from yakumo.web.server import create_server

MODULES = Path(__file__).resolve().parents[1] / "modules"
KEY = "good-key-1234567"


class FakeCloud(BaseHTTPRequestHandler):
    """Подставной Cloud.ru: чат отвечает заготовками потоком, разбор беседы — заготовленным JSON."""
    replies: list[str] = []
    learned: dict = {}
    requests: list[dict] = []
    embedded: list[str] = []
    completions: list[str] = []  # готовые ответы для фоновых запросов (задачи, экзамен, стиль) — по очереди

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    embeddings = False
    # Понятия для подставных векторов: слова одного понятия получают один вектор.
    CONCEPTS = (("машин", "автом", "тачк"), ("кошк", "кот", "котё"), ("чай", "чая"), ("отчё", "отчет"))

    def do_GET(self):  # noqa: N802
        models = [{"id": "Qwen/Qwen3-235B-A22B-Instruct-2507"}]
        if FakeCloud.embeddings:
            models.append({"id": "BAAI/bge-m3"})
        self._json({"data": models})

    @classmethod
    def vector(cls, text):
        text = text.lower()
        vec = [1.0 if any(w in text for w in group) else 0.0 for group in cls.CONCEPTS]
        return vec + [0.05]

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.endswith("/embeddings"):
            FakeCloud.embedded.extend(body["input"])
            self._json({"data": [{"index": i, "embedding": self.vector(t)} for i, t in enumerate(body["input"])]})
            return
        FakeCloud.requests.append(body)
        if not body.get("stream") and FakeCloud.completions:
            self._json({"choices": [{"message": {"content": FakeCloud.completions.pop(0)}}]})
            return
        if not body.get("stream"):
            text = "Вот память:\n```json\n" + json.dumps(FakeCloud.learned, ensure_ascii=False) + "\n```"
            self._json({"choices": [{"message": {"content": text}}]})
            return
        text = FakeCloud.replies.pop(0) if FakeCloud.replies else "…"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for i in range(0, len(text), 7):
            chunk = {"choices": [{"delta": {"content": text[i:i + 7]}}]}
            self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *args):
        pass


class BrainBase(unittest.TestCase):
    disabled = ["disk", "update", "hello"]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.fake = ThreadingHTTPServer(("127.0.0.1", 0), FakeCloud)
        threading.Thread(target=self.fake.serve_forever, daemon=True).start()
        FakeCloud.replies, FakeCloud.requests, FakeCloud.learned, FakeCloud.embedded = [], [], {}, []
        FakeCloud.completions = []
        FakeCloud.embeddings = False
        config = Config(cloud_url=f"http://127.0.0.1:{self.fake.server_address[1]}/v1",
                        cloud_model="Qwen/Qwen3-235B-A22B-Instruct-2507")
        (base / "config").mkdir()
        (base / "config" / "secrets.json").write_text(json.dumps({"cloud_api_key": KEY}), encoding="utf-8")
        cloud = CloudService(config, base / "config" / "yakumo.json", base / "config" / "secrets.json")
        self.data = base / "YakumoData"
        self.ctx = Context(paths=SimpleNamespace(app=base, data=self.data, workspace=base), config=config, cloud=cloud)
        infos = load_all(self.ctx, [MODULES], self.disabled)
        self.assertTrue(all(i.error is None for i in infos), [i.error for i in infos])
        self.learn = sys.modules["yakumo_modules.brain.learn"]
        self.learn.DELAY = 0.1
        cloud.tools = self.ctx.chat_tools
        cloud.context_hooks = self.ctx.chat_contexts
        cloud.listeners = self.ctx.chat_listeners
        self.server = create_server("127.0.0.1", 0, base, {**self.ctx.routes, **cloud.routes()})
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        # Фоновые дела разума (сон, смысловой поиск, программы на экране) в тестах запускаем сами.
        self.mind = self.learner().ticks[0].__self__
        self.ticks = [fn for _name, _mode, _every, fn in self.mind.jobs]
        self.learner().ticks.clear()

    def tearDown(self):
        self.ctx.stop()
        self.learn.DELAY = 20
        for s in (self.server, self.fake):
            s.shutdown()
            s.server_close()
        self.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return json.loads(r.read())

    def post(self, path, data, raw=False):
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            body = r.read().decode()
        return body if raw else json.loads(body)

    def chat(self, messages, chat_id="c1"):
        body = self.post("/api/chat", {"messages": messages, "chat_id": chat_id}, raw=True)
        events = [json.loads(line) for line in body.splitlines() if line]
        return "".join(e.get("delta", "") for e in events), events

    def wait_for(self, check, timeout=5.0):
        end = time.time() + timeout
        while time.time() < end:
            if check():
                return
            time.sleep(0.05)
        self.fail("не дождались")

    def system_prompt(self):
        return next(r for r in FakeCloud.requests if r.get("stream"))["messages"][0]["content"]

    def tick(self, name):
        return next(t.__self__ for t in self.ticks if type(getattr(t, "__self__", None)).__name__ == name)

    def memory(self):
        return self.ctx.memory._memory

    def learner(self):
        return next(t.__self__ for t in self.ctx.chat_listeners)


class BrainTest(BrainBase):
    def test_learns_from_chat_and_remembers_in_next_one(self):
        FakeCloud.learned = {"new": [{"text": "Пользователя зовут Аня", "kind": "person", "importance": 3},
                                     {"text": "Любит зелёный чай", "kind": "likes", "importance": 2}],
                             "seen": [], "outdated": [], "title": "Знакомство", "summary": "Аня рассказала о себе."}
        FakeCloud.replies = ["Приятно познакомиться, Аня!"]
        self.chat([{"role": "user", "content": "Привет, я Аня и люблю зелёный чай"}])
        self.wait_for(lambda: len(self.get("/api/brain")["talks"]) == 1)
        state = self.get("/api/brain")
        self.assertEqual({f["text"] for f in state["facts"]}, {"Пользователя зовут Аня", "Любит зелёный чай"})
        self.assertEqual(state["talks"][0]["title"], "Знакомство")
        self.assertTrue((self.data / "brain" / "memory.sqlite3").is_file())
        learn_prompt = next(r for r in FakeCloud.requests if not r.get("stream"))["messages"][0]["content"]
        self.assertIn("Привет, я Аня", learn_prompt)

        # Новая беседа: память и конспект прошлой — в подсказке.
        FakeCloud.requests, FakeCloud.replies = [], ["Конечно, Аня."]
        self.chat([{"role": "user", "content": "Как меня зовут?"}], chat_id="c2")
        prompt = self.system_prompt()
        self.assertIn("Пользователя зовут Аня", prompt)
        self.assertIn("«Знакомство»: Аня рассказала о себе.", prompt)

    def test_memory_engine_migrates_legacy_json(self):
        root = self.data / "legacy-test"
        root.mkdir(parents=True)
        legacy = root / "memory.json"
        legacy.write_text(json.dumps({
            "enabled": True,
            "facts": [{"id": "oldfact", "text": "Старое воспоминание", "kind": "other"}],
        }, ensure_ascii=False), encoding="utf-8")
        migrated = type(self.memory())(legacy)
        self.assertEqual(migrated.data["facts"][0]["text"], "Старое воспоминание")
        self.assertTrue((root / "memory.sqlite3").is_file())
        self.assertTrue((root / "memory.legacy.json").is_file())
        self.assertFalse(legacy.exists())
        self.assertEqual(migrated.storage_status()["engine"], "sqlite-wal")

    def test_memory_engine_21_moves_facts_between_layers_without_loss(self):
        recent = self.memory().add("Недавний факт", "other", importance=2)
        self.assertEqual(self.memory().memory_tier(recent), "operational")
        recent["seen"] = 5
        self.assertEqual(self.memory().memory_tier(recent), "longterm")

        old = self.memory().add("Событие прошлого месяца", "other", importance=2)
        old["created"] = old["last_seen"] = int(time.time()) - 30 * 86400
        counts = self.memory().rebalance_tiers()
        self.assertEqual(old["tier"], "episodic")
        self.assertGreaterEqual(counts["episodic"], 1)

        self.memory().supersede([old["id"]], "new_information")
        self.assertEqual(self.memory().fact(old["id"])["tier"], "archive")
        self.assertEqual(self.memory().fact(old["id"])["text"], "Событие прошлого месяца")
        state = self.get("/api/brain")
        self.assertEqual(state["storage"]["memory_engine"], "2.1")
        self.assertGreaterEqual(state["memory_tiers"]["archive"], 1)

    def test_outdated_facts_are_replaced_and_duplicates_merged(self):
        old = self.post("/api/brain/fact", {"text": "Живёт в Казани", "kind": "person"})["facts"][0]
        again = self.post("/api/brain/fact", {"text": "живёт в Казани"})["facts"]
        self.assertEqual(len(again), 1)
        self.assertEqual(again[0]["seen"], 2)
        FakeCloud.learned = {"new": [{"text": "Живёт в Москве", "kind": "person", "importance": 3}],
                             "outdated": [old["id"], "чужой-id"], "title": "Переезд", "summary": "Переехала."}
        self.chat([{"role": "user", "content": "Я переехала в Москву"}])
        self.wait_for(lambda: self.get("/api/brain")["talks"])
        facts = self.get("/api/brain")["facts"]
        self.assertEqual([f["text"] for f in facts if not f.get("archived")], ["Живёт в Москве"])
        archived = next(f for f in facts if f["id"] == old["id"])
        self.assertTrue(archived["archived"])
        self.assertTrue(archived["superseded"])
        self.assertEqual(archived["tier"], "archive")

    def test_chat_tools_remember_recall_and_forget(self):
        FakeCloud.replies = ['<tool>{"name": "memory_remember", "args": {"text": "Пьёт чай без сахара", '
                             '"kind": "likes"}}</tool>', "Запомнила!"]
        text, events = self.chat([{"role": "user", "content": "Запомни: я пью чай без сахара"}])
        self.assertEqual(text, "Запомнила!")
        self.assertIn({"status": "Запоминаю: Пьёт чай без сахара"}, events)
        fact = self.get("/api/brain")["facts"][0]
        self.assertEqual((fact["text"], fact["source"], fact["importance"]), ("Пьёт чай без сахара", "chat", 3))

        FakeCloud.replies = ['<tool>{"name": "memory_recall", "args": {"query": "сахар"}}</tool>', "Помню."]
        self.chat([{"role": "user", "content": "Что я говорила про сахар?"}])
        self.assertIn("Пьёт чай без сахара", FakeCloud.requests[-1]["messages"][-1]["content"])

        # «Забыть» — только по подтверждению, как изменения файлов.
        FakeCloud.replies = [f'<tool>{{"name": "memory_forget", "args": {{"ids": ["{fact["id"]}"]}}}}</tool>Забуду.']
        _text, events = self.chat([{"role": "user", "content": "Забудь про чай"}])
        card = next(e["card"] for e in events if "card" in e)
        self.assertEqual(card["actions"][0]["title"], "Забыть «Пьёт чай без сахара»")
        self.assertEqual(len(self.get("/api/brain")["facts"]), 1)
        self.post("/api/chat/apply", {"actions": card["actions"]})
        self.assertEqual(self.get("/api/brain")["facts"], [])

    def test_turned_off_memory_stays_out_of_chat(self):
        self.post("/api/brain/fact", {"text": "Секретный проект Феникс", "kind": "work"})
        self.post("/api/brain/settings", {"enabled": False})
        FakeCloud.replies = ["Ок"]
        self.chat([{"role": "user", "content": "Привет"}])
        time.sleep(0.4)
        self.assertNotIn("Феникс", self.system_prompt())
        self.assertFalse([r for r in FakeCloud.requests if not r.get("stream")])  # и сама не учится

    def test_page_edit_pin_export_import_and_clear(self):
        f = self.post("/api/brain/fact", {"text": "Учится на дизайнера", "kind": "work"})["facts"][0]
        state = self.post("/api/brain/fact", {"id": f["id"], "text": "Учится на дизайнера интерьеров", "pinned": True})
        self.assertEqual(state["facts"][0]["text"], "Учится на дизайнера интерьеров")
        self.assertEqual(state["facts"][0]["score"], 10.0)
        dump = self.get("/api/brain/export")
        self.post("/api/brain/clear", {"all": True})
        self.assertEqual(self.get("/api/brain")["facts"], [])
        res = self.post("/api/brain/import", dump)
        self.assertEqual(res["facts"], 1)
        self.assertTrue(res["state"]["facts"][0]["pinned"])
        self.assertEqual(self.post("/api/brain/import", dump)["facts"], 0)  # повторный импорт не дублирует
        for path, data in (("/api/brain/import", {"facts": []}), ("/api/brain/fact", {"text": "  "}),
                           ("/api/brain/clear", {}), ("/api/brain/settings", {"enabled": "да"})):
            with self.assertRaises(urllib.error.HTTPError) as err:
                self.post(path, data)
            self.assertEqual(err.exception.code, 400, path)

    def test_old_minor_facts_fade_and_move_to_archive(self):
        store = sys.modules["yakumo_modules.brain.store"]
        memory = store.Memory(self.data / "m.json")
        old = time.time() - 200 * 86400
        minor = memory.add("Смотрел вчера фильм", importance=1, source="auto")
        keep = memory.add("Зовут Аня", importance=3, source="auto")
        mine = memory.add("Любит котов", importance=1, source="manual")
        for f in (minor, keep, mine):
            f["last_seen"] = int(old)
        self.assertLess(memory.score(minor), memory.score(keep))
        memory.add("Новый факт", source="auto")  # Engine 2.1 переносит слабое в архив
        texts = {f["text"] for f in memory.facts()}
        self.assertEqual(texts, {"Смотрел вчера фильм", "Зовут Аня", "Любит котов", "Новый факт"})
        self.assertTrue(memory.fact(minor["id"])["archived"])
        self.assertEqual(memory.fact(minor["id"])["tier"], "archive")


    # --- Граф, источники, обещания, даты, настроение ---

    def test_learns_people_sources_promises_dates_and_mood(self):
        self.post("/api/brain/settings", {"mood": True})
        FakeCloud.learned = {
            "new": [{"text": "Сестру зовут Аня, живёт в Казани", "kind": "person", "importance": 3,
                     "quote": "моя сестра Аня из Казани", "about": [
                         {"name": "Аня", "type": "person", "relation": "сестра"},
                         {"name": "Казань", "type": "place"}]},
                    {"text": "Договор аренды лежит на Диске", "kind": "other", "files": ["Документы/договор.pdf"]},
                    {"text": "Зовёт Yakumo «Яку»", "kind": "self"}],
            "promises": [{"text": "Сдать отчёт", "who": "user", "due": "2030-01-10"},
                         {"text": "Напомнить про врача", "who": "yakumo", "due": None}],
            "dates": [{"text": "День рождения Ани", "date": "1999-05-05", "yearly": True},
                      {"text": "Без даты", "date": "когда-нибудь"}],
            "mood": -2, "mood_note": "устала", "title": "Про семью", "summary": "Рассказала о сестре."}
        FakeCloud.replies = ["Здорово!"]
        self.chat([{"role": "user", "content": "Моя сестра Аня из Казани. Сдам отчёт 10 января"}])
        self.wait_for(lambda: self.get("/api/brain")["talks"])
        state = self.get("/api/brain")
        ents = {e["name"]: e for e in state["entities"]}
        self.assertEqual(ents["Аня"]["relation"], "сестра")
        self.assertEqual((ents["Казань"]["type"], ents["Аня"]["facts"]), ("place", 1))
        anya = next(f for f in state["facts"] if "Аня" in f["text"])
        self.assertEqual(anya["quote"], "моя сестра Аня из Казани")
        self.assertEqual(anya["talk"], "c1")
        self.assertEqual(next(f for f in state["facts"] if "Договор" in f["text"])["files"], ["Документы/договор.pdf"])
        self.assertEqual({(p["who"], p["due"]) for p in state["promises"]}, {("user", "2030-01-10"), ("yakumo", None)})
        self.assertEqual([(e["text"], e["yearly"]) for e in state["events"]], [("День рождения Ани", True)])
        self.assertEqual(state["talks"][0]["mood"], -2)

        # В новой беседе: связи, файлы, обещания, «о себе» и тяжёлые дни — в подсказке.
        today = time.strftime("%Y-%m-%d")
        self.memory().data["days"]["2000-01-01"] = {"mood": [-1]}
        self.memory().data["days"][today]["mood"].append(-1)
        FakeCloud.requests, FakeCloud.replies = [], ["Привет"]
        self.chat([{"role": "user", "content": "Привет"}], chat_id="c2")
        prompt = self.system_prompt()
        self.assertIn("(Аня — сестра; Казань)", prompt)
        self.assertIn("[договор.pdf](disk:Документы/договор.pdf)", prompt)
        self.assertIn("пользователь: Сдать отчёт (2030-01-10)", prompt)
        self.assertIn("Что ты помнишь о себе", prompt)
        self.assertIn("Будь бережнее", prompt)

        # «Откуда ты это знаешь?»
        FakeCloud.replies = [f'<tool>{{"name": "memory_source", "args": {{"id": "{anya["id"]}"}}}}</tool>', "Ты сама сказала."]
        self.chat([{"role": "user", "content": "Откуда ты знаешь про Аню?"}], chat_id="c2")
        report = FakeCloud.requests[-1]["messages"][-1]["content"]
        self.assertIn("моя сестра Аня из Казани", report)
        self.assertIn("Про семью", report)

        # Выполненное обещание закрывается при следующем разборе.
        promise = next(p for p in state["promises"] if p["who"] == "user")
        FakeCloud.learned = {"done": [promise["id"]], "title": "Отчёт", "summary": "Сдала отчёт."}
        FakeCloud.replies = ["Ура!"]
        self.chat([{"role": "user", "content": "Сдала отчёт!"}], chat_id="c3")
        self.wait_for(lambda: any(p["done"] for p in self.get("/api/brain")["promises"]))

    def test_dates_and_on_this_day(self):
        import datetime as dt
        m = self.memory()
        on = dt.date(2027, 3, 4)
        m.event("День рождения мамы", "1970-03-05", yearly=True)
        m.event("Экзамен", "2027-03-04")
        m.event("Високосный", "2024-02-29", yearly=True)
        m.promise("Оплатить интернет", due="2027-03-01")
        m.promise("Без срока")
        soon = {x["text"]: x["in_days"] for x in m.upcoming(1, on)}
        self.assertEqual(soon, {"День рождения мамы": 1, "Экзамен": 0, "Оплатить интернет": -3})
        self.assertEqual(m.upcoming(0, dt.date(2027, 3, 1))[0]["text"], "Високосный")
        talk = m.save_talk("old", "Японский", "Начала учить японский.", 4)
        talk["started"] = int(time.mktime((2026, 3, 4, 12, 0, 0, 0, 0, -1)))
        self.assertEqual(m.on_this_day(on)[0]["ago_months"], 12)
        self.assertEqual(m.on_this_day(dt.date(2027, 3, 5)), [])

    # --- Поиск по смыслу ---

    def test_search_by_meaning(self):
        FakeCloud.embeddings = True
        self.post("/api/brain/fact", {"text": "Ездит на красном автомобиле", "kind": "likes"})
        self.post("/api/brain/fact", {"text": "Любит зелёный чай", "kind": "likes"})
        sync = self.tick("Semantic").sync
        self.assertEqual(sync(), 2)
        self.assertEqual(sync(), 0)  # без изменений ничего не пересчитывается
        found = self.ctx.memory.recall("какая у меня тачка?")
        self.assertEqual([f["text"] for f in found["facts"]], ["Ездит на красном автомобиле"])
        self.assertTrue((self.data / "brain" / "vectors.json").is_file())
        FakeCloud.replies = ["Красная!"]
        self.chat([{"role": "user", "content": "Какая у меня тачка?"}], chat_id="c9")
        self.assertIn("автомобиле", self.system_prompt())

    # --- Сон ---

    def test_sleep_merges_duplicates_and_writes_morning_message(self):
        a = self.post("/api/brain/fact", {"text": "Учится в университете на дизайнера", "kind": "work"})["facts"][0]
        b = self.post("/api/brain/fact", {"text": "Студентка дизайна", "kind": "work"})["facts"]
        b = next(f for f in b if f["id"] != a["id"])
        self.memory().event("День рождения Ани", time.strftime("%Y-%m-%d"), yearly=True)
        FakeCloud.learned = {"merge": [{"ids": [a["id"], b["id"], "чужой"], "text": "Учится на дизайнера в университете"}],
                             "morning": "Мне снилось, что мы рисовали портфолио хвостами! Сегодня день рождения Ани."}
        res = self.post("/api/brain/sleep", {})
        self.assertIn("день рождения Ани", res["morning"])
        facts = res["state"]["facts"]
        self.assertEqual([f["text"] for f in facts], ["Учится на дизайнера в университете"])
        self.assertEqual(facts[0]["seen"], 2)
        prompt = next(r for r in FakeCloud.requests if not r.get("stream"))["messages"][0]["content"]
        self.assertIn("сегодня: День рождения Ани", prompt)
        self.assertEqual(res["state"]["last_sleep"], time.strftime("%Y-%m-%d"))
        self.assertEqual(self.get("/api/brain/inbox")["messages"][0]["kind"], "morning")
        self.assertEqual(self.get("/api/brain/inbox")["messages"], [])  # выдаётся один раз

    def test_sleep_schedule_and_plain_morning_without_cloud(self):
        sleep_ = self.tick("Sleep")
        noon = time.mktime(time.strptime(time.strftime("%Y-%m-%d") + " 12:00", "%Y-%m-%d %H:%M"))
        night = noon - 10 * 3600
        self.learner().last_chat = 0
        self.assertTrue(sleep_.due(noon))
        self.assertFalse(sleep_.due(night))          # до 4 утра не спит
        self.learner().last_chat = noon - 60
        self.assertFalse(sleep_.due(noon))           # в чате только что говорили
        self.learner().last_chat = 0
        (self.data.parent / "config" / "secrets.json").unlink()
        self.memory().promise("Оплатить свет", due="2000-01-01")
        self.assertIn("Оплатить свет", sleep_.run())
        self.assertFalse(sleep_.due(noon))           # сегодня уже спала
        self.post("/api/brain/settings", {"sleep": False})
        self.memory().data["meta"]["last_sleep"] = "2000-01-01"
        self.assertFalse(sleep_.due(noon))

    # --- Навыки ---

    def test_skills_are_saved_and_recalled_in_chat(self):
        FakeCloud.replies = ['<tool>{"name": "memory_skill_save", "args": {"name": "Недельный отчёт", "when": "по '
                             'пятницам", "steps": ["Открыть таблицу продаж", "Сделать график", "Отправить Ивану"]}}'
                             '</tool>', "Запомнила!"]
        self.chat([{"role": "user", "content": "Запомни, как я делаю недельный отчёт: ..."}])
        FakeCloud.requests, FakeCloud.replies = [], ['<tool>{"name": "memory_skill", "args": {"name": "отчёт"}}</tool>',
                                                     "Делаю по шагам."]
        self.chat([{"role": "user", "content": "Сделай недельный отчёт"}], chat_id="c2")
        self.assertIn("Недельный отчёт: по пятницам", self.system_prompt())
        self.assertIn("Сделать график", FakeCloud.requests[-1]["messages"][-1]["content"])
        self.assertEqual(self.get("/api/brain")["skills"][0]["used"], 1)

    def test_remembers_own_versions_and_tells_in_chat(self):
        api = self.ctx.memory
        record = {"key": "job:1", "kind": "install", "revision": "b" * 40, "from_revision": "a" * 40,
                  "title": "main", "at": 1_700_000_000, "changes": ["Диск: избранное и недавние", "Чат: кнопка повтора"]}
        self.assertIsNotNone(api.version(record))
        self.assertIsNone(api.version(record))  # та же установка второй раз не пишется
        self.assertIsNone(api.version({**record, "key": "job:2", "revision": "не коммит"}))
        self.assertEqual(len(self.get("/api/brain")["versions"]), 1)
        FakeCloud.replies = ['<tool>{"name": "my_versions", "args": {}}</tool>', "Меня обновили!"]
        self.chat([{"role": "user", "content": "Что в тебе нового?"}])
        self.assertIn("Диск: избранное и недавние", self.system_prompt())
        self.assertIn("Чат: кнопка повтора", FakeCloud.requests[-1]["messages"][-1]["content"])
        self.post("/api/brain/clear", {"all": True})
        self.assertEqual(len(api.versions()), 1)  # очистка памяти о пользователе не стирает историю версий

    def test_improvements_collect_failures_errors_and_ideas(self):
        improve = self.tick("Improvements")
        self.memory().wish("Читать PDF со сканами")
        improve.scan()
        improve.scan()  # повторный просмотр не плодит пункты
        self.post("/api/brain/feedback", {"question": "Сколько 2+2?", "answer": "5", "good": False, "note": "ошибка в счёте"})
        log = logging.getLogger("yakumo.modules.disk")
        for _ in range(2):
            try:
                {}["нет"]
            except KeyError:
                log.exception("Не удалось разобрать файл")
        # Посторонние сбои фоновых дел тоже могут попасть в список — берём именно этот.
        items = {x["source"]: x for x in self.get("/api/brain")["improvements"]
                 if x["source"] != "error" or x["title"].startswith("Не удалось разобрать файл")}
        self.assertEqual(set(items), {"wish", "thumbs", "error"})
        self.assertEqual(items["thumbs"]["title"], "ошибка в счёте")
        self.assertEqual((items["error"]["module"], items["error"]["count"]), ("Диск", 2))
        self.assertIn("KeyError", items["error"]["detail"])
        self.assertIn("test_brain.py", items["error"]["detail"])
        # Оформление задачей в простое.
        FakeCloud.completions = [json.dumps({"title": "Распознавать сканы PDF", "problem": "Не читает сканы",
                                             "want": "Текст из сканов ищется", "module": "Диск", "priority": "high"},
                                            ensure_ascii=False)] + ["{}"] * 2
        self.assertEqual(improve.refine(), 3)
        state = self.get("/api/brain")
        wish = next(x for x in state["improvements"] if x["source"] == "wish")
        self.assertEqual((wish["title"], wish["priority"]), ("Распознавать сканы PDF", "high"))
        self.assertEqual(state["improvements"][0]["id"], wish["id"])  # важное выше
        # Свои идеи раз в день.
        FakeCloud.completions = [json.dumps({"ideas": [{"title": "Напоминания по времени", "problem": "Нет таймеров",
                                                        "want": "Напомнить через час", "module": "Чат"}]},
                                            ensure_ascii=False)]
        self.assertEqual(improve.ideas(), 1)
        self.assertEqual(improve.ideas(), 0)
        # Копирование для Claude: все новые → текст задачи, статус «отдана».
        res = self.post("/api/brain/improvements/copy", {})
        self.assertIn("## 1. Распознавать сканы PDF", res["text"])
        self.assertIn("**Что хочется:** Текст из сканов ищется", res["text"])
        self.assertIn("Напоминания по времени", res["text"])
        self.assertTrue(all(x["status"] == "given" for x in res["state"]["improvements"]))
        # Удалённое желание не возвращается, сделанная ошибка при повторе снова новая.
        self.post("/api/brain/item/delete", {"type": "improvements", "ids": [wish["id"]]})
        improve.scan()
        error = next(x for x in self.get("/api/brain")["improvements"] if x["title"].startswith("Не удалось разобрать файл"))
        self.post("/api/brain/improvement", {"id": error["id"], "status": "done"})
        try:
            {}["нет"]
        except KeyError:
            log.exception("Не удалось разобрать файл")
        state = self.get("/api/brain")["improvements"]
        self.assertNotIn("wish", {x["source"] for x in state})
        self.assertEqual(next(x for x in state if x["id"] == error["id"])["status"], "new")
        self.post("/api/brain/improvement", {"title": "Тёмная тема для Диска"})
        self.assertIn("manual", {x["source"] for x in self.get("/api/brain")["improvements"]})

    def test_reads_own_code_map_and_uses_it_for_tasks(self):
        app = Path(self.ctx.paths.app)
        (app / "modules" / "tips").mkdir(parents=True)
        (app / "modules" / "tips" / "__init__.py").write_text(
            '"""Чаевые: считает, сколько оставить."""\n\nNAME = "Чаевые"\nVERSION = "0.1"\n\n\n'
            'def tip_amount(total):\n    return total * 0.1  # процент чаевых\n', encoding="utf-8")
        self.tick("Code").sync(vectors=False)
        FakeCloud.replies = ['<tool>{"name": "code_search", "args": {"query": "tip amount"}}</tool>'
                             '<tool>{"name": "code_read", "args": {"path": "config/secrets.json"}}</tool>', "Вот как."]
        self.chat([{"role": "user", "content": "Как ты считаешь чаевые?"}])
        self.assertIn("Чаевые 0.1 — Чаевые: считает, сколько оставить.", self.system_prompt())
        report = FakeCloud.requests[-1]["messages"][-1]["content"]
        self.assertIn("modules/tips/__init__.py:7-8", report)
        self.assertIn("Такого файла в моём коде нет", report)  # настройки и ключи не читаются
        state = self.get("/api/brain")["code"]
        self.assertEqual(state["map"]["modules"][0]["name"], "Чаевые")
        # Задача в «Улучшениях» оформляется с кодом места сбоя.
        self.memory().improvement({"key": "error:x", "source": "error", "title": "Чаевые считаются неверно",
                                   "detail": "ValueError\nmodules/tips/__init__.py:8 (tip_amount)"})
        FakeCloud.completions = [json.dumps({"title": "Неверный процент чаевых",
                                             "fix": "modules/tips/__init__.py, tip_amount: брать процент из настроек"},
                                            ensure_ascii=False)]
        self.assertEqual(self.tick("Improvements").refine(), 1)
        prompt = [r for r in FakeCloud.requests if not r.get("stream")][-1]["messages"][0]["content"]
        self.assertIn("8:     return total * 0.1", prompt)
        item = self.get("/api/brain")["improvements"][0]
        self.assertIn("tip_amount", item["fix"])
        self.assertIn("**Где поправить:**", self.post("/api/brain/improvements/copy", {})["text"])

    def test_universe_galaxies_and_star_docs(self):
        mem = self.memory()
        mem.add("Сестра Аня любит кошек", about=[{"name": "Аня", "type": "person", "relation": "сестра"}])
        mem.add("Коллега Олег ведёт отчёты", about=[{"name": "Олег", "type": "person", "relation": "коллега"}])
        mem.add("Летом ездили в Казань", about=[{"name": "Казань", "type": "place"}])
        mem.add("Лиза дружит с Аней", about=["Лиза", "Аня"])
        universe = self.tick("Universe")
        universe.classify()
        state = self.get("/api/brain")
        areas = {e["name"]: e["area"] for e in state["entities"]}
        self.assertEqual(areas, {"Аня": "family", "Олег": "work", "Казань": "places", "Лиза": "other"})
        self.assertIn("hobby", state["areas"])
        # Когда вы не работаете, Yakumo уточняет галактики — один раз на звезду.
        liza = next(e for e in state["entities"] if e["name"] == "Лиза")
        FakeCloud.completions = [json.dumps({"areas": {liza["id"]: "friends"}})]
        self.assertEqual(universe.refine(), 1)
        self.assertIn("Лиза", [r for r in FakeCloud.requests if not r.get("stream")][-1]["messages"][0]["content"])
        self.assertEqual(universe.refine(), 0)  # всех уже спросили — без новых запросов
        by_name = {e["name"]: e for e in self.get("/api/brain")["entities"]}
        self.assertEqual((by_name["Лиза"]["area"], by_name["Лиза"]["area_by"]), ("friends", "yakumo"))
        # Перенесли звезду руками — Yakumo её больше не трогает.
        oleg = by_name["Олег"]
        state = self.post("/api/brain/item", {"type": "entity", "id": oleg["id"], "area": "hobby"})
        moved = next(e for e in state["entities"] if e["id"] == oleg["id"])
        self.assertEqual((moved["area"], moved["area_by"]), ("hobby", "user"))
        with self.assertRaises(urllib.error.HTTPError):
            self.post("/api/brain/item", {"type": "entity", "id": oleg["id"], "area": "space"})
        # Документы, где встречается имя звезды, прилипают к ней.
        knowledge = self.tick("Knowledge")
        knowledge.items = [{"path": "Семья/письмо.txt", "text": "Привет, Аня! Как дела?", "v": None},
                           {"path": "Отчёты/май.txt", "text": "Олег сдал отчёт. Олег молодец.", "v": None},
                           {"path": "Прочее.txt", "text": "Ананас и банан", "v": None}]
        universe.docs()
        docs = self.get("/api/brain")["entity_docs"]
        self.assertEqual(docs[by_name["Аня"]["id"]], ["Семья/письмо.txt"])
        self.assertEqual(docs[oleg["id"]], ["Отчёты/май.txt"])
        self.assertEqual(len(docs), 2)

    def test_home_galaxy_recall_and_three(self):
        mem = self.memory()
        fact = mem.add("Костя жил в Самаре", about=[{"name": "Костя", "type": "person", "relation": "друг"}])
        fact["archived"] = True
        kostya = fact["about"][0]
        state = self.post("/api/brain/recall", {"id": kostya})
        self.assertFalse(next(f for f in state["facts"] if f["id"] == fact["id"]).get("archived"))
        with urllib.request.urlopen(self.base + "/modules/brain/vendor/three.min.js") as r:
            self.assertIn(b"THREE", r.read(4000))
        web = self.ctx.web_files["brain"]
        self.assertIn("/modules/brain/galaxy.js", web)
        self.assertNotIn("/modules/brain/vendor/three.min.js", web)  # тяжёлое грузится только на главной

    # --- Контекст компьютера ---

    def test_activity_only_with_consent(self):
        activity = self.tick("Activity")
        activity.sampler = lambda: ("Photoshop", "portfolio.psd @ 100%")
        activity.tick()
        self.assertIsNone(activity.now())  # не включено — не смотрит
        self.post("/api/brain/settings", {"activity": True})
        activity.tick()
        activity.tick()
        self.assertEqual(activity.today(), [("Photoshop", 2)])
        FakeCloud.replies = ["Вижу, рисуешь!"]
        self.chat([{"role": "user", "content": "Что я делаю?"}])
        prompt = self.system_prompt()
        self.assertIn("Photoshop — «portfolio.psd @ 100%»", prompt)
        self.assertIn("Photoshop 2 мин", prompt)
        con = sqlite3.connect(self.data / "brain" / "memory.sqlite3")
        try:
            saved = "\n".join(row[0] for row in con.execute("SELECT value FROM state"))
        finally:
            con.close()
        self.assertNotIn("portfolio.psd", saved)  # заголовки окон на диск не попадают


class GrowthTest(BrainBase):
    """Саморазвитие: размышления, calc, разум и бюджет, уроки, стиль, задачи, свои инструменты, база знаний."""

    def test_thinking_is_hidden_and_rules_are_in_prompt(self):
        FakeCloud.replies = ["<think>Сначала посчитаю: 2+2=4, проверю.</think>Будет 4."]
        text, events = self.chat([{"role": "user", "content": "Сколько 2+2?"}])
        self.assertEqual(text, "Будет 4.")
        self.assertIn({"status": "Думаю…"}, events)
        prompt = self.system_prompt()
        self.assertIn("<think>", prompt)
        self.assertIn("calc", prompt)
        self.assertIn("не уверена", prompt)

    def test_calc_tool(self):
        run = self.ctx.chat_tools["calc"].run
        self.assertEqual(run({"expr": "2000 * 15% + sqrt(16)"}), {"result": 304})
        self.assertEqual(run({"expr": "2^10"}), {"result": 1024})
        self.assertIn("error", run({"expr": "__import__('os')"}))
        self.assertIn("error", run({"expr": "1/0"}))
        self.assertIn("error", run({"expr": "9**9**9**9"}))

    def test_repeated_tool_chain_becomes_skill_suggestion(self):
        for i in range(3):
            FakeCloud.replies = ['<tool>{"name": "calc", "args": {"expr": "1+1"}}</tool>'
                                 '<tool>{"name": "memory_recall", "args": {"query": "отчёт"}}</tool>', "Готово."]
            self.chat([{"role": "user", "content": "Сделай сводку по отчёту"}], chat_id=f"c{i}")
        state = self.get("/api/brain")
        self.assertEqual(len(state["suggestions"]), 1)
        sug = state["suggestions"][0]
        self.assertEqual(sug["signature"], "calc → memory_recall")
        inbox = self.get("/api/brain/inbox")["messages"]
        self.assertEqual(inbox[-1]["kind"], "suggestion")
        state = self.post("/api/brain/suggestion", {"id": sug["id"], "accept": True, "name": "Сводка по отчёту"})
        self.assertEqual(state["suggestions"], [])
        self.assertEqual(state["skills"][0]["name"], "Сводка по отчёту")
        self.assertEqual(len(state["skills"][0]["steps"]), 2)

    def test_wishes_and_lessons_from_chat(self):
        FakeCloud.learned = {"wish": "Считать ипотеку", "lesson": "Отвечать короче, без длинных списков",
                             "summary": "Говорили об ипотеке"}
        FakeCloud.replies = ["Пока не умею считать ипотеку.", "Ок."]
        self.chat([{"role": "user", "content": "Посчитай ипотеку. И отвечай короче!"}])
        self.wait_for(lambda: self.memory().data["lessons"])
        state = self.get("/api/brain")
        self.assertEqual(state["wishes"][0]["text"], "Считать ипотеку")
        self.assertEqual(state["lessons"][0]["source"], "chat")
        FakeCloud.requests = []
        self.chat([{"role": "user", "content": "Привет"}], chat_id="c2")
        prompt = self.system_prompt()
        self.assertIn("Отвечать короче, без длинных списков", prompt)
        self.assertIn("Считать ипотеку", prompt)

    def test_mind_modes_budget_and_thoughts(self):
        now = time.mktime(time.strptime(time.strftime("%Y-%m-%d") + " 12:00", "%Y-%m-%d %H:%M"))
        self.learner().last_chat = now - 60
        self.assertEqual(self.mind.mode(now), "awake")
        self.learner().last_chat = now - 20 * 60
        self.assertEqual(self.mind.mode(now), "drowsy")
        self.learner().last_chat = now - 2 * 3600
        self.assertEqual(self.mind.mode(now), "asleep")
        night = now - 9 * 3600  # 3 часа ночи
        self.learner().last_chat = night - 20 * 60
        self.assertEqual(self.mind.mode(night), "asleep")  # ночью засыпает быстрее
        status = self.post("/api/brain/mind", {"budget": 50})
        self.assertEqual(status["budget"], 50)
        with self.assertRaises(urllib.error.HTTPError):
            self.post("/api/brain/mind", {"budget": 7})
        self.memory().data["meta"]["usage"] = {"date": time.strftime("%Y-%m-%d"), "calls": 50}
        self.assertFalse(self.mind.can_think())
        self.assertIn("error", self.ctx.chat_tools["background_task"].run({"task": "что-то"}))
        self.post("/api/brain/mind", {"budget": 0})  # без ограничения
        self.assertTrue(self.mind.can_think())
        item = self.mind.thought("task", "Тест", "queued")
        self.assertTrue(self.post("/api/brain/thought/cancel", {"id": item["id"]})["ok"])
        self.assertEqual(self.get("/api/brain/mind")["thoughts"][0]["status"], "cancelled")

    def test_night_exam_and_style_versions(self):
        for i in range(5):
            FakeCloud.replies = [f"Ответ {i}"]
            self.chat([{"role": "user", "content": f"Вопрос {i}"}], chat_id=f"c{i}")
        self.wait_for(lambda: not self.learner().pending and not self.learner().busy)
        FakeCloud.completions = [json.dumps({"score": 3, "review": "Местами длинно",
                                             "lessons": ["Проверять расчёты через calc"]}, ensure_ascii=False)]
        state = self.post("/api/brain/grow", {"what": "exam"})
        self.assertEqual(state["lessons"][0]["text"], "Проверять расчёты через calc")
        self.assertEqual(state["lessons"][0]["source"], "exam")
        self.assertEqual(state["mind"]["thoughts"][0]["kind"], "exam")
        self.assertIn("3/5", state["mind"]["thoughts"][0]["result"])
        FakeCloud.completions = [json.dumps({"style": "- Отвечать коротко\n- На «ты»", "why": "Просил короче"},
                                            ensure_ascii=False),
                                 json.dumps({"style": "- Совсем коротко", "why": "Ещё короче"}, ensure_ascii=False)]
        first = self.post("/api/brain/grow", {"what": "style"})["style"]["versions"][0]
        state = self.post("/api/brain/grow", {"what": "style"})
        self.assertEqual(len(state["style"]["versions"]), 2)
        FakeCloud.requests = []
        self.chat([{"role": "user", "content": "Привет"}], chat_id="x")
        self.assertIn("- Совсем коротко", self.system_prompt())
        self.post("/api/brain/style", {"id": first["id"]})  # откат
        FakeCloud.requests = []
        self.chat([{"role": "user", "content": "Привет"}], chat_id="y")
        self.assertIn("- Отвечать коротко\n- На «ты»", self.system_prompt())
        self.post("/api/brain/style", {"id": None})
        FakeCloud.requests = []
        self.chat([{"role": "user", "content": "Привет"}], chat_id="z")
        self.assertNotIn("Отвечать коротко", self.system_prompt())

    def test_background_task_runs_tools_and_reports(self):
        FakeCloud.completions = ['<tool>{"name": "calc", "args": {"expr": "6*7"}}</tool>', "Итог: **42**"]
        res = self.ctx.chat_tools["background_task"].run({"task": "Посчитай 6*7 и доложи", "title": "Подсчёт"})
        self.assertTrue(res["ok"])
        self.wait_for(lambda: self.memory().item("thoughts", res["id"])["status"] == "done")
        item = self.memory().item("thoughts", res["id"])
        self.assertEqual(item["steps"], ["calc"])
        self.assertEqual(item["result"], "Итог: **42**")
        tool_result = [r for r in FakeCloud.requests if not r.get("stream")][1]["messages"][-1]["content"]
        self.assertIn("42", tool_result)
        inbox = self.get("/api/brain/inbox")["messages"]
        self.assertEqual(inbox[-1]["kind"], "task")
        self.assertIn("«Подсчёт»", inbox[-1]["text"])

    def test_own_tools_need_approval_and_run_in_sandbox(self):
        propose = self.ctx.chat_tools["tool_propose"].run
        self.assertIn("error", propose({"name": "evil", "description": "x", "code": "import os\ndef run(a): pass"}))
        res = propose({"name": "double", "description": "удвоить число",
                       "code": "def run(args):\n    return args['x'] * 2", "example": {"x": 21}})
        self.assertEqual(res["test"], {"result": 42})
        self.assertNotIn("my_double", self.ctx.chat_tools)  # без одобрения не работает
        tool = self.get("/api/brain")["user_tools"][0]
        self.assertEqual(tool["status"], "pending")
        self.post("/api/brain/tool", {"id": tool["id"], "action": "on"})
        self.assertEqual(self.ctx.chat_tools["my_double"].run({"x": 5}), {"result": 10})
        self.post("/api/brain/tool", {"id": tool["id"], "action": "off"})
        self.assertNotIn("my_double", self.ctx.chat_tools)

    def test_sleep_links_and_archive(self):
        a = self.memory().add("Экзамен по истории 20 мая", "work")
        b = self.memory().add("Поездка в Казань 19-21 мая", "other")
        old = self.memory().add("Когда-то любил квас", "likes", importance=1)
        old["last_seen"] = old["created"] = int(time.time()) - 400 * 86400
        FakeCloud.learned = {"merge": [], "links": [{"a": a["id"], "b": b["id"], "why": "в одни дни"},
                                                    {"a": a["id"], "b": "чужой", "why": "x"}],
                             "morning": "Доброе утро! Экзамен и поездка совпадают."}
        state = self.post("/api/brain/sleep", {})["state"]
        self.assertEqual([(x["a"], x["b"]) for x in state["links"]], [(a["id"], b["id"])])
        archived = next(f for f in state["facts"] if f["id"] == old["id"])
        self.assertTrue(archived["archived"])
        self.assertEqual(state["mind"]["thoughts"][0]["kind"], "sleep")
        FakeCloud.requests = []
        self.chat([{"role": "user", "content": "Привет"}])
        self.assertNotIn("квас", self.system_prompt())  # архив не в подсказке…
        self.assertIn("квас", json.dumps(self.ctx.memory.recall("квас"), ensure_ascii=False))  # …но ищется
        self.post("/api/brain/fact/restore", {"id": old["id"]})
        self.assertNotIn("archived", self.memory().fact(old["id"]))

    def test_knowledge_base_and_study(self):
        FakeCloud.embeddings = True
        docs = [("Учёба/конспект.txt", 1, "Машинное обучение: градиентный спуск.\n\nОтчёт по курсу сдать до мая."),
                ("Дом/кошка.txt", 1, "Кошку Мурку кормить дважды в день.")]
        self.ctx.services["disk"] = SimpleNamespace(documents=lambda: docs)
        self.tick("Semantic").sync()
        knowledge = self.tick("Knowledge")
        self.assertEqual(knowledge.sync(), 2)
        found = self.ctx.chat_tools["knowledge_search"].run({"query": "чем кормить кота"})["found"]
        self.assertEqual(found[0]["link"], "[кошка.txt](disk:Дом/кошка.txt)")
        FakeCloud.requests = []
        self.chat([{"role": "user", "content": "Когда кормить котика?"}])
        self.assertIn("Мурку кормить", self.system_prompt())
        docs.pop()  # документ удалили с Диска — из базы тоже
        knowledge.sync()
        self.assertEqual(knowledge.status()["documents"], 1)
        self.memory().entity("Курс по ML", "project")
        self.memory().add("Делает отчёт по курсу", "work", about=[{"name": "Курс по ML", "type": "project"}])
        FakeCloud.completions = ["- Отчёт сдать до мая"]
        state = self.post("/api/brain/grow", {"what": "study"})
        self.assertEqual(state["notes"][0]["sources"], ["Учёба/конспект.txt"])

    # --- Эволюция из чата и сильное мышление ---

    def test_deep_think_several_voices_and_critic(self):
        self.ctx.cloud.models = ["Qwen/Qwen3-235B-A22B-Instruct-2507", "openai/gpt-oss-120b",
                                 "ai-sage/GigaChat3-10B-A1.8B"]
        FakeCloud.completions = ["Черновик: 120", "Черновик: 125, учёл комиссию", "Черновик: 120",
                                 json.dumps({"answer": "Итого **125** ₽ с комиссией", "confidence": 4,
                                             "disagreements": "Скептик учёл комиссию",
                                             "lesson": "Не забывать про комиссии в расчётах"}, ensure_ascii=False)]
        res = self.ctx.chat_tools["deep_think"].run({"task": "Сколько заплачу за 100 ₽ с комиссией?",
                                                     "context": "Комиссия 5 ₽, НДС 20 ₽"})
        self.assertEqual(res["answer"], "Итого **125** ₽ с комиссией")
        self.assertEqual(res["voices"], 3)
        self.assertEqual(len(set(res["models"][:3])), 3)
        self.assertEqual(self.memory().data["lessons"][0]["source"], "think")
        critic = [r for r in FakeCloud.requests if not r.get("stream")][-1]["messages"][0]["content"]
        self.assertIn("Черновик: 125, учёл комиссию", critic)
        FakeCloud.replies = ["Привет!"]
        self.chat([{"role": "user", "content": "Привет"}])
        self.assertIn("deep_think", self.system_prompt())

    def test_thumbs_up_and_down_from_chat(self):
        growth = self.tick("Growth")
        self.post("/api/brain/feedback", {"question": "Как сварить кофе?", "answer": "Вот так.", "good": True})
        self.post("/api/brain/feedback", {"question": "Сколько 2+2?", "answer": "5", "good": False,
                                          "note": "ошибка в счёте"})
        self.assertEqual(self.get("/api/brain")["best"], 1)
        FakeCloud.completions = [json.dumps({"why": "Неверно посчитала", "lesson": "Считать через calc"},
                                            ensure_ascii=False)]
        self.assertEqual(growth.digest(), 1)
        state = self.get("/api/brain")
        self.assertEqual(state["lessons"][0]["text"], "Считать через calc")
        self.assertEqual(state["lessons"][0]["source"], "feedback")
        self.assertEqual(self.memory().data["feedback"], [])
        prompt = [r for r in FakeCloud.requests if not r.get("stream")][-1]["messages"][0]["content"]
        self.assertIn("ошибка в счёте", prompt)
        # Образцы с 👍 идут в экзамен и улучшение стиля первыми.
        self.assertIn("Как сварить кофе?", growth._samples(4))

    def test_curiosity_asks_one_question_a_day(self):
        for text in ("Зовут Аня", "Учится на дизайнера", "Есть кот Персик"):
            self.memory().add(text, "person")
        FakeCloud.completions = [json.dumps({"question": "Как зовут твоего научного руководителя?",
                                             "why": "Не знаю руководителя"}, ensure_ascii=False)]
        res = self.post("/api/brain/grow", {"what": "curious"})
        self.assertEqual(res["question"], "Как зовут твоего научного руководителя?")
        inbox = self.get("/api/brain/inbox")["messages"]
        self.assertEqual(inbox[-1]["kind"], "question")
        self.assertIsNone(self.tick("Growth").curious())  # сегодня уже спрашивала

    def test_lessons_consolidate_in_sleep(self):
        a = self.memory().lesson("Отвечать короче", "chat")
        b = self.memory().lesson("Не писать длинные списки", "exam")
        self.memory().lesson("Проверять расчёты через calc", "exam")
        a["seen"] = 3
        FakeCloud.completions = [json.dumps({"lessons": [
            {"text": "Отвечать коротко, без длинных списков", "from": [a["id"], b["id"]]},
            {"text": "Проверять расчёты через calc", "from": ["чужой"]}]}, ensure_ascii=False)]
        state = self.post("/api/brain/grow", {"what": "consolidate"})
        self.assertEqual([(x["text"], x["seen"]) for x in state["lessons"]],
                         [("Отвечать коротко, без длинных списков", 4), ("Проверять расчёты через calc", 1)])

    def test_brain_growth_census(self):
        self.memory().add("Зовут Аня", "person", about=["Аня"])
        snap = self.tick("Growth").census(5)
        self.assertEqual(snap["parts"]["documents"], 5)
        self.assertEqual(snap["links"], 1)
        brain = self.get("/api/brain")["brain"]
        self.assertEqual(brain[-1]["neurons"], snap["neurons"])

    def test_development_links_strengthen_on_joint_growth_and_choose_focus(self):
        branches = self.tick("DevelopmentBranches")
        base = branches.tick()
        before = next(e for e in base["edges"] if e["from"] == "memory" and e["to"] == "logic")

        self.memory().add("Новый факт для роста памяти", "other")
        self.memory().lesson("Новый урок для роста логики", "chat")
        snap = branches.tick()
        edge = next(e for e in snap["edges"] if e["from"] == "memory" and e["to"] == "logic")
        self.assertGreater(edge["strength"], before["strength"])
        self.assertEqual(edge["uses"], before["uses"] + 1)
        self.assertTrue(edge["history"])
        self.assertEqual(edge["history"][-1]["strength"], edge["strength"])
        self.assertIn(snap["focus"]["id"], {b["id"] for b in snap["branches"] if b["available"]})
        self.assertIn(snap["focus"]["action"],
                      {"consolidate", "exam", "study", "code_refine", "foresee", "ideas"})

    def test_observability_memory_versions_conflicts_and_entity_cards(self):
        memory = self.memory()
        rev = "a" * 40
        memory.version({"key": "seen:a", "kind": "seen", "revision": rev, "title": "main", "at": 10})
        memory.version({"key": "install:a", "kind": "install", "revision": rev, "title": "main",
                        "at": 20, "changes": ["Добавлена карта"], "total": 1})
        versions = memory.versions()
        same = [v for v in versions if v["revision"] == rev]
        self.assertEqual(len(same), 1)
        self.assertEqual(same[0]["kind"], "install")
        self.assertIn("Добавлена карта", same[0]["changes"])

        a = memory.add("Аня работает инженером", "person", about=[{"name": "Аня", "type": "person"}])
        b = memory.add("Аня работает водителем", "person", about=[{"name": "Аня", "type": "person"}])
        conflicts = memory.conflicts()
        self.assertTrue(any({x["a"], x["b"]} == {a["id"], b["id"]} for x in conflicts))
        self.assertTrue(all(not x["verified"] and x["status"] == "needs_clarification" for x in conflicts))

        e1 = memory.observe_entity("Toyota-Hilux", "thing", ["Гараж/путевой лист.docx"], relation="автомобиль")
        e2 = memory.observe_entity("Toyota Hilux", "thing", ["Гараж/чек.pdf"], relation="автомобиль")
        self.assertEqual(e1["id"], e2["id"])
        card = next(e for e in memory.entities() if e["id"] == e1["id"])
        self.assertIn("Toyota Hilux", card.get("aliases", []))
        self.assertEqual(set(card["files"]), {"Гараж/путевой лист.docx", "Гараж/чек.pdf"})

        trace = memory.trace("decision", "Выбрали локальный индекс", reason="не отправлять документы в облако",
                             result="использовать SQLite", status="done", files=["Документы/решение.docx"])
        self.assertIsNotNone(trace)
        self.assertEqual(memory.timeline()[0]["kind"], "decision")
        self.assertTrue(memory.activity_feed())

    def test_learner_saves_causes_decisions_errors_and_unfinished_work(self):
        FakeCloud.learned = {
            "new": [], "seen": [], "outdated": [],
            "traces": [
                {"kind": "cause", "text": "Поиск был медленным", "reason": "индекс не был построен", "status": "done"},
                {"kind": "decision", "text": "Решили перестроить индекс", "reason": "поиск был медленным",
                 "result": "запустить переиндексацию", "status": "done"},
                {"kind": "project_error", "text": "Индекс не обновлялся", "reason": "ошибка фоновой задачи",
                 "result": "исправлен запуск", "status": "done"},
                {"kind": "progress", "text": "Переделать поиск", "result": "осталось проверить PDF", "status": "open"},
            ],
            "title": "Работа над поиском", "summary": "Разобрали проблему индекса."
        }
        FakeCloud.replies = ["Поняла."]
        self.chat([{"role": "user", "content": "Поиск тормозил из-за индекса. Решили его перестроить; PDF ещё проверить."}])
        self.wait_for(lambda: len(self.get("/api/brain")["traces"]) == 4)
        state = self.get("/api/brain")
        self.assertEqual({x["kind"] for x in state["traces"]},
                         {"cause", "decision", "project_error", "progress"})
        self.assertEqual(state["diagnostics"]["memory"]["open_progress"], 1)
        self.assertTrue(any(x["status"] == "open" for x in state["timeline"] if x["kind"] == "progress"))

    def test_watchdog_stops_stale_thought_and_does_not_let_late_finish_revive_it(self):
        mind = self.mind
        thought = mind.thought("doc", "Зависшее чтение")
        thought["heartbeat"] = int(time.time()) - 16 * 60
        self.assertEqual(mind.watchdog(), 1)
        self.assertEqual(thought["status"], "failed")
        self.assertTrue(thought["stale"])
        self.assertFalse(mind.finish(thought, "done", "поздний ответ"))
        self.assertEqual(thought["status"], "failed")

    def test_foresee_prepares_in_advance(self):
        self.memory().promise("Сдать отчёт по практике", due=time.strftime("%Y-%m-%d"))
        FakeCloud.completions = [
            json.dumps({"needs": [{"what": "Черновик отчёта по практике", "why": "срок сегодня",
                                   "task": "Собери черновик отчёта по практике из документов"},
                                  {"what": "Взять зонт", "why": "", "task": None}]}, ensure_ascii=False),
            "Черновик готов: три раздела."]
        state = self.post("/api/brain/grow", {"what": "foresee"})
        prompt = [r for r in FakeCloud.requests if not r.get("stream")][0]["messages"][0]["content"]
        self.assertIn("Сдать отчёт по практике", prompt)
        task = next(t for t in state["mind"]["thoughts"] if t["kind"] == "task")
        self.assertEqual(task["title"], "Заранее: Черновик отчёта по практике")
        self.wait_for(lambda: self.memory().item("thoughts", task["id"])["status"] == "done")
        kinds = [m["kind"] for m in self.get("/api/brain/inbox")["messages"]]
        self.assertIn("foresee", kinds)
        self.assertIn("task", kinds)
        self.assertEqual(self.tick("Growth").foresee(), [])  # раз в день

    # --- Мозг и Диск ---

    def test_new_documents_are_read_remembered_and_sorted(self):
        docs = [("Учёба/конспект.txt", 1, "Старый конспект " * 20)]
        self.ctx.services["disk"] = SimpleNamespace(documents=lambda: docs)
        reader = self.tick("Docs")
        self.assertEqual(reader.scan(), 0)  # первый заход: что уже лежало, не читаем
        contract = "Договор аренды № 15. Арендодатель Иван Петров. Плата 35 000 ₽ до 15 ноября. " * 3
        docs.append(("договор.pdf", 2, contract))
        FakeCloud.completions = [json.dumps({
            "summary": "Договор аренды квартиры",
            "facts": [{"text": "По договору аренды № 15 платит 35 000 ₽ в месяц", "kind": "work",
                       "about": [{"name": "Иван Петров", "type": "person", "relation": "арендодатель"}]}],
            "dates": [{"text": "Оплата аренды", "date": "2099-11-15", "yearly": False}],
            "message": "Срок оплаты аренды — 15 ноября, 35 000 ₽.", "folder": "Документы/Аренда"},
            ensure_ascii=False)]
        self.assertEqual(reader.scan(), 1)
        prompt = [r for r in FakeCloud.requests if not r.get("stream")][-1]["messages"][0]["content"]
        self.assertIn("Учёба", prompt)  # знает существующие папки
        fact = next(f for f in self.memory().facts() if f["source"] == "doc")
        self.assertEqual(fact["files"], ["договор.pdf"])
        self.assertEqual(self.memory().data["events"][0]["text"], "Оплата аренды (договор.pdf)")
        inbox = self.get("/api/brain/inbox")["messages"]
        self.assertEqual([m["kind"] for m in inbox], ["doc", "sort"])
        self.assertIn("(disk:договор.pdf)", inbox[0]["text"])
        plan = self.ctx.chat_tools["disk_sort_plan"].run({})
        self.assertEqual(plan["files"][0]["to"], "Документы/Аренда")
        # Перенесли файл — второй раз не читает, а из плана раскладки он уходит.
        docs[1] = ("Документы/Аренда/договор.pdf", 3, contract)
        self.assertEqual(reader.scan(), 0)
        self.assertEqual(self.ctx.chat_tools["disk_sort_plan"].run({})["files"], [])
        self.post("/api/brain/settings", {"docs": False})
        docs.append(("новый.txt", 4, "Совсем новый документ " * 10))
        self.assertEqual(reader.scan(), 0)

    def test_folder_brief(self):
        docs = [("Учёба/билеты.txt", 1, "Билет 1. Баухаус."), ("Учёба/сроки.txt", 1, "Экзамен 20 мая."),
                ("Дом/кот.txt", 1, "Кормить кота.")]
        self.ctx.services["disk"] = SimpleNamespace(documents=lambda: docs)
        FakeCloud.completions = ["В папке билеты и сроки: экзамен 20 мая."]
        res = self.ctx.chat_tools["folder_brief"].run({"path": "Учёба", "question": "когда экзамен?"})
        self.assertEqual(res["documents"], 2)
        self.assertIn("экзамен 20 мая", res["brief"])
        prompt = [r for r in FakeCloud.requests if not r.get("stream")][-1]["messages"][0]["content"]
        self.assertIn("[Учёба/сроки.txt]", prompt)
        self.assertNotIn("кота", prompt)
        self.assertIn("когда экзамен?", prompt)


class BrainWithDiskTest(BrainBase):
    """Память и Диск вместе: ctx.memory для модулей и ссылки на файлы."""
    disabled = ["update", "hello"]

    def test_files_follow_moves_and_disk_search_uses_memory(self):
        root = self.data / "disk" / "Документы"
        root.mkdir(parents=True)
        (root / "договор.pdf").write_bytes(b"%PDF-1.4")
        fact = self.ctx.memory.remember("Договор аренды квартиры в Москве", about=["Москва"],
                                        files=["Документы/договор.pdf"])
        self.assertEqual(fact["source"], "module")
        self.post("/api/disk/rename", {"path": "Документы", "name": "Бумаги"})
        self.assertEqual(self.memory().fact(fact["id"])["files"], ["Бумаги/договор.pdf"])
        result = self.ctx.chat_tools["disk_search"].run({"query": "аренда квартиры"})
        self.assertEqual(result["from_memory"][0]["files"], ["Бумаги/договор.pdf"])

    def test_learns_from_user_edits_of_her_files(self):
        grow = sys.modules["yakumo_modules.brain.grow"]
        grow.EDIT_SETTLE = 0
        try:
            res = self.ctx.chat_tools["disk_write"].run({"path": "Письма/письмо.md",
                                                         "text": "Уважаемый Иван Петрович!\n\nНастоящим сообщаю, что отчёт готов."})
            draft = self.memory().data["drafts"][0]
            self.assertEqual(draft["path"], res["path"])
            growth = self.tick("Growth")
            self.assertEqual(growth.edits(), 0)  # пока не правили
            draft["at"] -= 100
            (self.data / "disk" / "Письма" / "письмо.md").write_text("Иван, привет!\n\nОтчёт готов.", encoding="utf-8")
            FakeCloud.completions = [json.dumps({"changes": "Убрал официоз",
                                                 "lessons": ["Писать письма просто, без канцелярита"]},
                                                ensure_ascii=False)]
            self.assertEqual(growth.edits(), 1)
            self.assertEqual(self.memory().data["lessons"][0]["source"], "edit")
            self.assertEqual(self.memory().data["drafts"], [])
            prompt = [r for r in FakeCloud.requests if not r.get("stream")][-1]["messages"][0]["content"]
            self.assertIn("+Иван, привет!", prompt)
        finally:
            grow.EDIT_SETTLE = 600

    def test_tables_and_comparing_versions(self):
        import zipfile
        root = self.data / "disk"
        (root / "Счета").mkdir(parents=True, exist_ok=True)
        (root / "Счета" / "расходы.csv").write_text(
            "Месяц;Услуга;Сумма\nЯнварь;Свет;1 200,50\nЯнварь;Вода;800\nФевраль;Свет;1 100\n", encoding="utf-8")
        cells = lambda r, vals: "".join(  # noqa: E731
            f'<c r="{c}{r}" t="inlineStr"><is><t>{v}</t></is></c>' if isinstance(v, str) else f'<c r="{c}{r}"><v>{v}</v></c>'
            for c, v in zip("ABC", vals))
        sheet = ('<worksheet><sheetData>' + "".join(f'<row r="{i}">{cells(i, row)}</row>' for i, row in enumerate(
            [("Товар", "Цена"), ("Молоко", 89), ("Хлеб", 45.5)], 1)) + '</sheetData></worksheet>')
        with zipfile.ZipFile(root / "Счета" / "цены.xlsx", "w") as zf:
            zf.writestr("xl/workbook.xml", '<workbook><sheets><sheet name="Май" sheetId="1"/></sheets></workbook>')
            zf.writestr("xl/worksheets/sheet1.xml", sheet)
        table = self.ctx.chat_tools["disk_table"].run
        res = table({"path": "Счета/расходы.csv", "where": {"услуга": "свет"}, "sum": ["Сумма"]})
        self.assertEqual((res["rows"], res["sum"]), (2, {"Сумма": 2300.5}))
        res = table({"path": "Счета/расходы.csv", "sum": "Сумма", "group_by": "Месяц"})
        self.assertEqual(res["groups"]["Январь"], {"rows": 2, "Сумма": 2000.5})
        res = table({"path": "Счета/цены.xlsx", "sum": ["цена"]})
        self.assertEqual((res["sheet"], res["columns"], res["sum"]), ("Май", ["Товар", "Цена"], {"Цена": 134.5}))
        with self.assertRaises(Exception):
            table({"path": "Счета/расходы.csv", "sum": ["Нет такой"]})
        (root / "старый.txt").write_text("Плата 30 000\nСрок 1 год\n", encoding="utf-8")
        (root / "новый.txt").write_text("Плата 35 000\nСрок 1 год\n", encoding="utf-8")
        diff = self.ctx.chat_tools["disk_compare"].run({"a": "старый.txt", "b": "новый.txt"})
        self.assertIn("-Плата 30 000", diff["diff"])
        self.assertIn("+Плата 35 000", diff["diff"])
        self.assertEqual((diff["added_lines"], diff["removed_lines"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
