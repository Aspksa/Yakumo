import json
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
        # Фоновые дела (сон, смысловой поиск, программы на экране) в тестах запускаем сами.
        self.ticks = list(self.learner().ticks)
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
        return next(t.__self__ for t in self.ticks if type(t.__self__).__name__ == name)

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
        self.assertTrue((self.data / "brain" / "memory.json").is_file())
        learn_prompt = next(r for r in FakeCloud.requests if not r.get("stream"))["messages"][0]["content"]
        self.assertIn("Привет, я Аня", learn_prompt)

        # Новая беседа: память и конспект прошлой — в подсказке.
        FakeCloud.requests, FakeCloud.replies = [], ["Конечно, Аня."]
        self.chat([{"role": "user", "content": "Как меня зовут?"}], chat_id="c2")
        prompt = self.system_prompt()
        self.assertIn("Пользователя зовут Аня", prompt)
        self.assertIn("«Знакомство»: Аня рассказала о себе.", prompt)

    def test_outdated_facts_are_replaced_and_duplicates_merged(self):
        old = self.post("/api/brain/fact", {"text": "Живёт в Казани", "kind": "person"})["facts"][0]
        again = self.post("/api/brain/fact", {"text": "живёт в Казани"})["facts"]
        self.assertEqual(len(again), 1)
        self.assertEqual(again[0]["seen"], 2)
        FakeCloud.learned = {"new": [{"text": "Живёт в Москве", "kind": "person", "importance": 3}],
                             "outdated": [old["id"], "чужой-id"], "title": "Переезд", "summary": "Переехала."}
        self.chat([{"role": "user", "content": "Я переехала в Москву"}])
        self.wait_for(lambda: self.get("/api/brain")["talks"])
        self.assertEqual([f["text"] for f in self.get("/api/brain")["facts"]], ["Живёт в Москве"])

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

    def test_old_minor_facts_fade_and_are_forgotten(self):
        store = sys.modules["yakumo_modules.brain.store"]
        memory = store.Memory(self.data / "m.json")
        old = time.time() - 200 * 86400
        minor = memory.add("Смотрел вчера фильм", importance=1, source="auto")
        keep = memory.add("Зовут Аня", importance=3, source="auto")
        mine = memory.add("Любит котов", importance=1, source="manual")
        for f in (minor, keep, mine):
            f["last_seen"] = int(old)
        self.assertLess(memory.score(minor), memory.score(keep))
        memory.add("Новый факт", source="auto")  # при добавлении память чистится
        self.assertEqual({f["text"] for f in memory.facts()}, {"Зовут Аня", "Любит котов", "Новый факт"})


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
        saved = (self.data / "brain" / "memory.json").read_text(encoding="utf-8")
        self.assertNotIn("portfolio.psd", saved)  # заголовки окон на диск не попадают


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


if __name__ == "__main__":
    unittest.main()
