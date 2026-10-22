"""Доступ к Yakumo: владелец на этом компьютере и пароль для других устройств."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import tempfile
import threading
import time
from dataclasses import dataclass, field
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit

COOKIE = "yakumo_session"
ITERATIONS = 600_000
SESSION_SECONDS = 12 * 60 * 60
LOGIN_WINDOW = 15 * 60
MAX_ATTEMPTS = 5


@dataclass
class AccessResponse:
    status: int
    data: dict
    headers: dict[str, str] = field(default_factory=dict)


class AccessControl:
    def __init__(self, path: Path | None = None):
        self.path = path
        self.lock = threading.RLock()
        self.password = self._load()
        self.sessions: dict[str, float] = {}
        self.failures: dict[str, tuple[int, float]] = {}

    def _load(self) -> dict | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig")) if self.path else None
            if (isinstance(data, dict) and data.get("version") == 1
                    and isinstance(data.get("salt"), str) and len(data["salt"]) == 32
                    and isinstance(data.get("hash"), str) and len(data["hash"]) == 64):
                bytes.fromhex(data["salt"])
                bytes.fromhex(data["hash"])
                return data
        except (OSError, ValueError):
            pass
        return None  # повреждённый файл закрывает сетевой доступ

    @staticmethod
    def is_local(request) -> bool:
        # Берём адрес TCP-соединения, а не присланные X-Forwarded-For/Host.
        # При --host/--lan браузер владельца может обращаться к своему LAN-IP.
        peer = ipaddress.ip_address(request.client_address[0])
        local = ipaddress.ip_address(request.connection.getsockname()[0])
        return peer.is_loopback or peer == local

    @staticmethod
    def valid_host(request) -> bool:
        """Не принимать произвольные DNS-имена (в том числе DNS rebinding)."""
        host = request.headers.get("Host", "")
        try:
            parsed = urlsplit("//" + host)
            allowed = {"localhost", "127.0.0.1", request.connection.getsockname()[0]}
            return (bool(host) and not any(c.isspace() for c in host)
                    and parsed.hostname in allowed and parsed.username is None and parsed.password is None
                    and not (parsed.path or parsed.query or parsed.fragment)
                    and (parsed.port or 80) == request.server.server_port)
        except ValueError:
            return False

    @staticmethod
    def _token(request) -> str:
        cookie = SimpleCookie()
        try:
            cookie.load(request.headers.get("Cookie", ""))
        except CookieError:
            return ""
        return cookie[COOKIE].value if COOKIE in cookie else ""

    def authorized(self, request) -> bool:
        if self.is_local(request):
            return True
        token = self._token(request)
        with self.lock:
            return bool(self.password and self.sessions.get(token, 0) > time.monotonic())

    def state(self, request) -> dict:
        with self.lock:
            return {"local": self.is_local(request), "password_set": bool(self.password),
                    "authenticated": self.authorized(request)}

    def set_password(self, request) -> dict | AccessResponse:
        if not self.is_local(request):
            return AccessResponse(403, {"error": "Пароль можно менять только на компьютере с Yakumo"})
        body = request.read_json()
        value = body.get("password") if isinstance(body, dict) else None
        if not isinstance(value, str) or (value and not 8 <= len(value) <= 128):
            raise ValueError("Пароль должен содержать от 8 до 128 символов")
        if not self.path:
            raise ValueError("Не задан файл настроек доступа")
        data = None
        if value:
            salt = secrets.token_bytes(16)
            digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, ITERATIONS)
            data = {"version": 1, "salt": salt.hex(), "hash": digest.hex()}
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if data is None:
                self.path.unlink(missing_ok=True)
            else:
                # Запись целиком: сбой сохранения не должен оставлять половину файла.
                tmp = None
                try:
                    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                                     prefix="access-", suffix=".tmp", delete=False) as f:
                        tmp = Path(f.name)
                        json.dump(data, f)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(tmp, self.path)
                finally:
                    if tmp is not None:
                        tmp.unlink(missing_ok=True)
            self.password = data
            self.sessions.clear()
            self.failures.clear()
        return self.state(request)

    def login(self, request) -> AccessResponse:
        body = request.read_json()
        value = body.get("password") if isinstance(body, dict) else None
        if not isinstance(value, str) or len(value) > 128:
            raise ValueError("Неверный пароль")
        peer, now = request.client_address[0], time.monotonic()
        with self.lock:
            self.failures = {p: v for p, v in self.failures.items() if v[1] > now}
            attempts, until = self.failures.get(peer, (0, now + LOGIN_WINDOW))
            if attempts >= MAX_ATTEMPTS:
                return AccessResponse(429, {"error": "Слишком много попыток. Повторите через 15 минут"},
                                      {"Retry-After": str(max(1, int(until - now)))})
            data = self.password
            ok = bool(data and hmac.compare_digest(
                hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), bytes.fromhex(data["salt"]), ITERATIONS),
                bytes.fromhex(data["hash"])))
            if not ok:
                # Ограничиваем и число записей, и число попыток для одного адреса.
                if len(self.failures) >= 1024 and peer not in self.failures:
                    return AccessResponse(429, {"error": "Слишком много попыток входа. Повторите позже"})
                self.failures[peer] = (attempts + 1, until)
                return AccessResponse(401, {"error": "Неверный пароль"})
            self.failures.pop(peer, None)
            self.sessions = {t: expiry for t, expiry in self.sessions.items() if expiry > now}
            self.sessions.pop(self._token(request), None)
            if len(self.sessions) >= 256:
                self.sessions.pop(min(self.sessions, key=self.sessions.get))
            token = secrets.token_urlsafe(32)
            self.sessions[token] = time.monotonic() + SESSION_SECONDS
        return AccessResponse(200, {"ok": True}, {"Set-Cookie":
            f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_SECONDS}"})

    def logout(self, request) -> AccessResponse:
        with self.lock:
            self.sessions.pop(self._token(request), None)
        return AccessResponse(200, {"ok": True}, {"Set-Cookie":
            f"{COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})

    def login_page(self) -> str:
        with self.lock:
            ready = bool(self.password)
        hint = ("Введите пароль, заданный в настройках Yakumo на основном компьютере." if ready else
                "Сетевой доступ закрыт. Задайте пароль в разделе «Настройки → Доступ по сети» "
                "на компьютере, где запущена Yakumo.")
        form = """<form id="login"><label for="password">Пароль</label>
<input id="password" name="password" type="password" autocomplete="current-password"
required maxlength="128" autofocus><button>Войти</button><p id="error" role="alert"></p></form>""" if ready else ""
        return """<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Вход · Yakumo</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#100d09;color:#f4ead7;
font:16px system-ui,sans-serif}main{box-sizing:border-box;width:min(440px,100%);padding:32px}
h1{color:#d9a441}p{line-height:1.6}label,input,button{display:block;box-sizing:border-box;width:100%}
input,button{font:inherit;border-radius:10px;padding:12px;margin-top:12px}
input{background:#211b12;color:inherit;border:1px solid #8d7548}button{border:0;background:#d9a441;
color:#191208;cursor:pointer}button:disabled{opacity:.6}#error{color:#ffad9c}</style>
<main><h1>Yakumo</h1><p>""" + hint + "</p>" + form + """</main>
<script>const form=document.getElementById('login');if(form)form.addEventListener('submit',async e=>{
e.preventDefault();const button=form.querySelector('button');button.disabled=true;
const error=document.getElementById('error');error.textContent='';try{
const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({password:form.elements.password.value})});const data=await r.json();
if(!r.ok)throw new Error(data.error);location.replace('/');
}catch(e){error.textContent=e.message||'Не удалось войти';button.disabled=false;}});</script></html>"""
