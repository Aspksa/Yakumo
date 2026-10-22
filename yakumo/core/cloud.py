"""Чат через Cloud.ru Foundation Models (API в формате OpenAI)."""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

log = logging.getLogger(__name__)

# Если модель ещё не выбрана, берём первую доступную из этого списка, иначе первую из каталога.
PREFERRED_MODELS = (
    "Qwen/Qwen3-235B-A22B-Instruct-2507",
    "ai-sage/GigaChat3-10B-A1.8B",
    "openai/gpt-oss-120b",
)

SYSTEM_PROMPT = {
    "ru": ("Ты Yakumo, кицунэ с девятью золотыми хвостами и помощница в программе Yakumo на Windows. "
           "Отвечай по-русски, дружелюбно и по делу. Для кода и списков используй Markdown."),
    "en": ("You are Yakumo, a nine-tailed golden kitsune and the assistant inside the Yakumo app for Windows. "
           "Be friendly and to the point. Use Markdown for code and lists."),
}

# Инструменты модулей (например, «Диск»). Модель вызывает их строкой <tool>{"name": ..., "args": {...}}</tool>:
# такой текстовый формат понимает любая модель каталога, в отличие от встроенного вызова функций.
TOOLS_PROMPT = {
    "ru": ("\n\nУ тебя есть инструменты. Чтобы вызвать инструмент, напиши отдельной строкой\n"
           '<tool>{{"name": "имя", "args": {{...}}}}</tool>\n'
           "и закончи ответ: результат придёт следующим сообщением, его видишь только ты. Можно вызвать "
           "несколько инструментов подряд. Не выдумывай результаты и пути файлов — сначала узнай их инструментом. "
           "Инструменты, которые меняют файлы, выполняются только после того, как пользователь подтвердит план "
           "кнопкой, поэтому после них коротко перечисли, что предлагаешь сделать. На файлы ссылайся так: "
           "[имя](disk:путь/к/файлу).\n\nИнструменты:\n{tools}"),
    "en": ("\n\nYou have tools. To call one, write on its own line\n"
           '<tool>{{"name": "name", "args": {{...}}}}</tool>\n'
           "and end your message: the result comes in the next message and only you see it. You may call several "
           "tools in a row. Never invent results or file paths — look them up with a tool first. Tools that change "
           "files only run after the user confirms the plan with a button, so after calling them briefly list "
           "what you propose. Link files like [name](disk:path/to/file).\n\nTools:\n{tools}"),
}
MAX_TOOL_ROUNDS = 6         # сколько раз подряд модель может обратиться к инструментам
MAX_TOOL_RESULT = 15000     # символов результата одного инструмента
TOOL_TAG = "<tool>"
THINK_TAG = "<think>"     # размышления модели перед ответом: пользователю не показываются
THINKING = {"ru": "Думаю…", "en": "Thinking…"}
# Модели, которые понимают картинки (для описания фото на Диске).
# Модели для смыслового поиска (эмбеддинги).
EMBEDDING = re.compile(r"embed|(^|[/_-])(bge|gte|e5)([/_-]|$)", re.I)
VISION = re.compile(r"(^|[/_-])(vl|vision|visual|omni|llava|pixtral|internvl|minicpm-v)|gemma-?3", re.I)


@dataclass
class ChatTool:
    """Инструмент для чата. change=True — меняет данные и выполняется только по подтверждению."""

    name: str
    description: str                 # для модели: что делает и какие аргументы принимает
    run: Callable[[dict], Any]
    change: bool = False
    title: Callable[[dict], str] | None = None  # для пользователя: «Ищу…» или пункт плана


MAX_MESSAGES = 30          # сколько последних реплик отправлять модели
MAX_MESSAGE_CHARS = 8000   # одна реплика
TIMEOUT = 120              # секунд на ответ модели


class CloudError(Exception):
    """Понятная пользователю ошибка связи с Cloud.ru."""


class CloudService:
    def __init__(self, config, config_path: Path, secrets_path: Path):
        self.config = config
        self.config_path = config_path
        self.secrets_path = secrets_path
        self.models: list[str] = []  # последний полученный каталог
        self.tools: dict[str, ChatTool] = {}  # инструменты модулей (ctx.chat_tool)
        self.context_hooks: list[Callable] = []  # дополнения к подсказке (ctx.chat_context)
        self.listeners: list[Callable] = []      # кому сообщать о завершённом ответе (ctx.on_chat)

    # --- Ключ ---
    # Ключ лежит отдельно от настроек и никогда не отдаётся в браузер целиком.

    def api_key(self) -> str:
        try:
            data = json.loads(self.secrets_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return ""
        key = data.get("cloud_api_key") if isinstance(data, dict) else None
        return key if isinstance(key, str) else ""

    def save_key(self, key: str) -> None:
        self.secrets_path.parent.mkdir(parents=True, exist_ok=True)
        if not key:
            self.secrets_path.unlink(missing_ok=True)
            return
        tmp = self.secrets_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"cloud_api_key": key}), encoding="utf-8")
        os.replace(tmp, self.secrets_path)

    # --- Запросы к Cloud.ru ---

    def _request(self, path: str, key: str, body: dict | None = None, timeout: float = 20):
        if not key:
            raise CloudError("no_key")
        req = urllib.request.Request(
            self.config.cloud_url.rstrip("/") + path, data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "Accept": "text/event-stream" if body and body.get("stream") else "application/json"},
            method="POST" if body is not None else "GET")
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            detail = _error_text(exc)
            log.warning("Cloud.ru ответил %s: %s", exc.code, detail)
            if exc.code in (401, 403):
                raise CloudError("bad_key") from exc
            if exc.code == 429:
                raise CloudError("rate_limit") from exc
            if exc.code == 404 and body is not None:
                raise CloudError("bad_model") from exc
            raise CloudError(f"HTTP {exc.code}: {detail}" if detail else f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, socket.timeout, OSError) as exc:
            log.warning("Нет связи с Cloud.ru: %s", exc)
            raise CloudError("network") from exc

    def fetch_models(self, key: str) -> list[str]:
        with self._request("/models", key) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("data", []) if isinstance(data, dict) else []
        models = sorted({m["id"] for m in items if isinstance(m, dict) and isinstance(m.get("id"), str)})
        if not models:
            raise CloudError("no_models")
        self.models = models
        return models

    def default_model(self, models: list[str]) -> str:
        return next((m for m in PREFERRED_MODELS if m in models), models[0])

    def vision_model(self) -> str | None:
        """Модель из каталога, которая видит картинки, или None."""
        models = self.models or self.fetch_models(self.api_key())
        found = [m for m in models if VISION.search(m)]
        return next((m for m in found if "qwen" in m.lower()), found[0] if found else None)

    def embedding_model(self) -> str | None:
        """Модель эмбеддингов из каталога или None."""
        models = self.models or self.fetch_models(self.api_key())
        found = [m for m in models if EMBEDDING.search(m) and "rerank" not in m.lower()]
        return next((m for m in found if "bge-m3" in m.lower()), found[0] if found else None)

    def embed(self, texts: list[str], model: str, timeout: float = 30) -> list[list[float]]:
        """Векторы смысла для текстов (порядок как у texts). Ошибки — CloudError."""
        with self._request("/embeddings", self.api_key(), {"model": model, "input": texts}, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("data") if isinstance(data, dict) else None
        if not isinstance(items, list) or len(items) != len(texts):
            raise CloudError(_message(data.get("error", "empty") if isinstance(data, dict) else data))
        items = sorted(items, key=lambda i: i.get("index", 0))
        return [i["embedding"] for i in items]

    def complete(self, messages: list[dict], model: str | None = None, max_tokens: int = 600,
                 timeout: float = TIMEOUT) -> str:
        """Ответ модели целиком (для фоновых задач модулей). Ошибки — CloudError."""
        key = self.api_key()
        payload = {"model": model or self.config.cloud_model, "messages": messages, "stream": False,
                   "temperature": 0.2, "max_tokens": max_tokens}
        with self._request("/chat/completions", key, payload, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise CloudError(_message(data.get("error", "empty") if isinstance(data, dict) else data)) from exc
        return re.sub(r"<think>.*?(</think>|$)", "", text, flags=re.S).strip()

    # --- Маршруты ---

    def state(self, _request=None) -> dict:
        key = self.api_key()
        return {
            "has_key": bool(key),
            "key_hint": "…" + key[-4:] if len(key) >= 8 else ("•" * len(key)),
            "model": self.config.cloud_model,
            "models": self.models,
        }

    def save(self, request) -> dict:
        """Сохранить ключ и/или модель. Пустой ключ удаляет сохранённый."""
        changes = request.read_json()
        if not isinstance(changes, dict) or not set(changes) <= {"api_key", "model"}:
            raise ValueError("Ожидается api_key и/или model")
        key, model = changes.get("api_key"), changes.get("model")
        if key is not None and (not isinstance(key, str) or len(key) > 4000 or any(c.isspace() for c in key.strip())):
            raise ValueError("Недопустимый ключ")
        if model is not None and (not isinstance(model, str) or not model or len(model) > 200):
            raise ValueError("Недопустимая модель")
        if key is not None:
            self.save_key(key.strip())
            log.info("Ключ Cloud.ru %s", "сохранён" if key.strip() else "удалён")
        if model is not None:
            self.config.cloud_model = model
            self.config.save(self.config_path)
            log.info("Модель Cloud.ru: %s", model)
        return self.state()

    def test(self, request) -> dict:
        """Проверка связи: запросить каталог моделей с новым или сохранённым ключом."""
        body = request.read_json() or {}
        key = body.get("api_key") if isinstance(body, dict) else None
        key = key.strip() if isinstance(key, str) and key.strip() else self.api_key()
        try:
            models = self.fetch_models(key)
        except CloudError as exc:
            return {**self.state(), "ok": False, "error": str(exc)}
        if not self.config.cloud_model or self.config.cloud_model not in models:
            self.config.cloud_model = self.default_model(models)
            self.config.save(self.config_path)
        return {**self.state(), "ok": True}

    def chat(self, request) -> Iterator[bytes]:
        """Ответ модели потоком: строки JSON {"delta": ...}, в конце {"done": true} или {"error": ...}."""
        body = request.read_json()
        messages = body.get("messages") if isinstance(body, dict) else None
        if not isinstance(messages, list) or not messages:
            raise ValueError("Нет сообщений")
        clean = []
        for m in messages[-MAX_MESSAGES:]:
            if (not isinstance(m, dict) or m.get("role") not in ("user", "assistant")
                    or not isinstance(m.get("content"), str)):
                raise ValueError("Неверное сообщение")
            clean.append({"role": m["role"], "content": m["content"][:MAX_MESSAGE_CHARS]})
        # Многие модели требуют, чтобы после системной подсказки шёл пользователь и роли чередовались.
        merged: list[dict] = []
        for m in clean:
            if merged and merged[-1]["role"] == m["role"]:
                merged[-1]["content"] += "\n\n" + m["content"]
            elif merged or m["role"] == "user":
                merged.append(dict(m))
        if not merged:
            raise ValueError("Нет сообщений пользователя")
        clean = merged
        chat_id = body.get("chat_id")
        if not isinstance(chat_id, str) or not re.fullmatch(r"[\w-]{1,64}", chat_id):
            chat_id = ""
        lang = self.config.language if self.config.language in SYSTEM_PROMPT else "ru"
        prompt = SYSTEM_PROMPT[lang]
        for hook in self.context_hooks:
            try:
                extra = hook(clean, chat_id)
            except Exception:  # noqa: BLE001 — ошибка модуля не должна ломать чат
                log.exception("Ошибка дополнения к подсказке чата")
                continue
            if extra:
                prompt += "\n\n" + extra
        if self.tools:
            listing = "\n".join(f"- {t.name}: {t.description}" + (" [меняет файлы]" if t.change and lang == "ru"
                                 else " [changes files]" if t.change else "") for t in self.tools.values())
            prompt += TOOLS_PROMPT[lang].format(tools=listing)
        return self._stream([{"role": "system", "content": prompt}, *clean], history=clean, chat_id=chat_id)

    def _stream(self, messages: list[dict], history: list[dict] | None = None, chat_id: str = "") -> Iterator[bytes]:
        """Ответ потоком; если модель зовёт инструменты — выполнить и продолжить с их результатами.

        События: {"delta": текст}, {"status": "Ищу…"}, {"card": {"type": "plan", ...}}, {"done": true}, {"error": ...}.
        """
        def line(obj) -> bytes:
            return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")

        plan: list[dict] = []
        answer = ""  # что увидел пользователь — для ctx.on_chat
        try:
            key = self.api_key()
            model = self.config.cloud_model
            if key and not model:
                model = self.config.cloud_model = self.default_model(self.fetch_models(key))
            said = False
            used: list[tuple[str, dict]] = []  # какие инструменты звались — для ctx.on_chat
            for _ in range(MAX_TOOL_ROUNDS + 1):
                payload = {"model": model, "messages": messages, "stream": True,
                           "temperature": 0.7, "max_tokens": 2500}
                text, shown = "", 0
                with self._request("/chat/completions", key, payload, timeout=TIMEOUT) as resp:
                    thinking = False
                    for delta in _deltas(resp):
                        text += delta
                        if not thinking and _thinking(text):
                            thinking = True
                            yield line({"status": THINKING.get(self.config.language, THINKING["ru"])})
                        shown_text = _visible(text, partial=True)
                        if len(shown_text) > shown:
                            out = shown_text[shown:]
                            if not shown and said:
                                out = "\n\n" + out.lstrip()  # ответ после работы инструментов — с новой строки
                            yield line({"delta": out})
                            shown = len(shown_text)
                tail = _visible(text)[shown:]
                if tail:
                    yield line({"delta": tail})
                said = said or bool(_visible(text).strip())
                answer += ("\n\n" if answer else "") + _visible(text).strip()
                calls = _tool_calls(text) if self.tools else []
                used += calls
                if not calls:
                    break
                results, asked = [], False
                for name, args in calls:
                    tool = self.tools.get(name)
                    if tool is None:  # модель ошиблась в имени или JSON: пусть исправится
                        asked = True
                        results.append((name, {"error": "нет такого инструмента или неверный JSON"}))
                        continue
                    title = _title(tool, args)
                    if tool.change:
                        plan.append({"tool": name, "args": args, "title": title})
                        results.append((name, {"ok": "добавлено в план, выполнится после подтверждения"}))
                        continue
                    asked = True
                    yield line({"status": title})
                    try:
                        results.append((name, tool.run(args)))
                    except Exception as exc:  # noqa: BLE001 — ошибку видит модель и может исправиться
                        results.append((name, {"error": str(exc) or type(exc).__name__}))
                if not asked:
                    break  # только план: дальше решает пользователь
                report = "\n".join(f"{name}: {_dump(result)}" for name, result in results)
                messages = [*messages, {"role": "assistant", "content": text},
                            {"role": "user", "content": "Результаты инструментов:\n" + report}]
        except CloudError as exc:
            yield line({"error": str(exc)})
            return
        except (OSError, socket.timeout) as exc:
            log.warning("Ответ Cloud.ru прервался: %s", exc)
            yield line({"error": "network"})
            return
        if plan:
            yield line({"card": {"type": "plan", "actions": plan}})
        yield line({"done": True})
        if history is not None and answer.strip():
            for listener in self.listeners:
                try:
                    listener(history, answer.strip(), chat_id, used)
                except Exception:  # noqa: BLE001
                    log.exception("Ошибка обработчика ответа чата")

    def apply(self, request) -> dict:
        """Выполнить подтверждённый пользователем план (инструменты, которые меняют данные)."""
        body = request.read_json()
        actions = body.get("actions") if isinstance(body, dict) else None
        if not isinstance(actions, list) or not actions or len(actions) > 200:
            raise ValueError("Нет действий")
        results = []
        for action in actions:
            tool = self.tools.get(action.get("tool")) if isinstance(action, dict) else None
            args = action.get("args") if isinstance(action, dict) else None
            if tool is None or not tool.change or not isinstance(args, dict):
                results.append({"ok": False, "error": "неизвестное действие"})
                continue
            try:
                tool.run(args)
                results.append({"ok": True, "title": _title(tool, args)})
            except Exception as exc:  # noqa: BLE001 — остальные шаги плана всё равно выполняем
                results.append({"ok": False, "title": _title(tool, args), "error": str(exc) or type(exc).__name__})
        log.info("План из чата: выполнено %s из %s", sum(r["ok"] for r in results), len(results))
        return {"results": results}

    def routes(self) -> dict:
        return {"/api/cloud": self.state, "POST /api/cloud": self.save,
                "POST /api/cloud/test": self.test, "POST /api/chat": self.chat,
                "POST /api/chat/apply": self.apply}


def _deltas(resp) -> Iterator[str]:
    """Куски текста из потока Cloud.ru (Server-Sent Events в формате OpenAI)."""
    for raw in resp:
        text = raw.decode("utf-8", errors="replace").strip()
        if not text.startswith("data:"):
            continue
        data = text[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except ValueError:
            continue
        if chunk.get("error"):
            raise CloudError(_message(chunk["error"]))
        for choice in chunk.get("choices") or []:
            delta = (choice.get("delta") or {}).get("content")
            if delta:
                yield delta


def _thinking(text: str) -> bool:
    """Модель начала размышлять (<think> открыт и ещё не закрыт)."""
    start = text.rfind(THINK_TAG)
    return start >= 0 and text.find("</think>", start) < 0


def _visible(text: str, partial: bool = False) -> str:
    """Текст для пользователя без вызовов инструментов и размышлений.

    partial: ответ ещё идёт — придержать незакрытый вызов или размышление и хвост, похожий на их начало («<to»).
    """
    out = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.S)
    out = re.sub(r"<tool>.*?</tool>[ \t]*\n?", "", out, flags=re.S)
    for tag in (THINK_TAG, TOOL_TAG):
        cut = out.find(tag)
        if cut >= 0:
            out = out[:cut]
    if partial:
        for k in range(min(len(THINK_TAG) - 1, len(out)), 0, -1):
            if any(tag.startswith(out[-k:]) for tag in (TOOL_TAG, THINK_TAG)):
                return out[:-k]
    return out


def _tool_calls(text: str) -> list[tuple[str, dict]]:
    calls = []
    text = re.sub(r"<think>.*?(</think>|$)", "", text, flags=re.S)
    for body in re.findall(r"<tool>(.*?)(?:</tool>|$)", text, flags=re.S):
        body = body.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            data = json.loads(body)
        except ValueError:
            calls.append(("?", {"raw": body[:200]}))
            continue
        if isinstance(data, dict) and isinstance(data.get("name"), str):
            args = data.get("args") if isinstance(data.get("args"), dict) else {}
            calls.append((data["name"], args))
    return calls


def _title(tool: ChatTool, args: dict) -> str:
    try:
        return tool.title(args) if tool.title else tool.name
    except Exception:  # noqa: BLE001
        return tool.name


def _dump(result) -> str:
    text = json.dumps(result, ensure_ascii=False, default=str)
    return text if len(text) <= MAX_TOOL_RESULT else text[:MAX_TOOL_RESULT] + "… (обрезано)"


def _message(error) -> str:
    if isinstance(error, dict):
        return str(error.get("message") or error)
    return str(error)


def _error_text(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read(2000).decode("utf-8", errors="replace")
    except OSError:
        return ""
    try:
        data = json.loads(raw)
    except ValueError:
        return raw.strip()[:300]
    return _message(data.get("error", data) if isinstance(data, dict) else data)[:300]
