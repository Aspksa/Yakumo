"""Инструменты, которые Yakumo пишет себе сама, и calc для точных расчётов.

Когда Yakumo не хватает умения (например, «посчитай ипотеку»), она может
написать маленькую функцию на Python через tool_propose. Код проверяется
(разрешены только безопасные модули: math, datetime, re, json…, никаких файлов,
сети и запуска программ), пробуется в отдельном процессе-песочнице с таймаутом
и ждёт вашего решения на странице «Память» → «Рост». Включённый инструмент
появляется в чате под именем my_<имя> и всегда выполняется в песочнице.
"""

from __future__ import annotations

import ast
import json
import math
import operator
import re
import subprocess
import sys

SAFE_MODULES = {"math", "cmath", "statistics", "datetime", "calendar", "re", "json", "random", "itertools",
                "functools", "collections", "fractions", "decimal", "string", "textwrap", "unicodedata"}
BANNED = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars", "getattr", "setattr",
          "delattr", "input", "breakpoint", "help", "exit", "quit", "memoryview", "type", "object", "super",
          "classmethod", "staticmethod", "property"}
MAX_CODE = 4000
TIMEOUT = 5
MAX_OUTPUT = 8000
NAME = re.compile(r"[a-z][a-z0-9_]{2,30}")

# Выполняется в отдельном процессе Python (-I: без пользовательских модулей и переменных окружения).
RUNNER = r"""
import json, sys
data = json.loads(sys.stdin.read())
env = {"__name__": "yakumo_tool"}
try:
    exec(compile(data["code"], "tool", "exec"), env)
    out = {"ok": True, "result": env["run"](data["args"])}
    json.dumps(out)
except Exception as exc:
    out = {"ok": False, "error": type(exc).__name__ + ": " + str(exc)}
sys.stdout.write(json.dumps(out, ensure_ascii=False, default=str))
"""


class ToolError(ValueError):
    """Код инструмента не прошёл проверку."""


def check(code: str) -> None:
    """Разрешить только безопасный код с функцией run(args)."""
    if not isinstance(code, str) or not code.strip():
        raise ToolError("Нет кода")
    if len(code) > MAX_CODE:
        raise ToolError("Слишком длинный код")
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ToolError(f"Ошибка в коде: {exc.msg} (строка {exc.lineno})") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".")[0]]
        else:
            names = []
        bad = [n for n in names if n not in SAFE_MODULES]
        if bad:
            raise ToolError(f"Модуль {bad[0]} нельзя: разрешены {', '.join(sorted(SAFE_MODULES))}")
        if isinstance(node, ast.Name) and (node.id in BANNED or node.id.startswith("__")):
            raise ToolError(f"{node.id} нельзя")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ToolError(f"Служебные атрибуты ({node.attr}) нельзя")
        if isinstance(node, (ast.Global, ast.Nonlocal, ast.ClassDef, ast.AsyncFunctionDef, ast.Await)):
            raise ToolError(f"{type(node).__name__} нельзя")
    if not any(isinstance(n, ast.FunctionDef) and n.name == "run" for n in tree.body):
        raise ToolError("Нужна функция run(args)")


def sandbox(code: str, args) -> dict:
    """Выполнить проверенный код в отдельном процессе с таймаутом."""
    check(code)
    try:
        proc = subprocess.run([sys.executable, "-I", "-S", "-c", RUNNER],
                              input=json.dumps({"code": code, "args": args}, ensure_ascii=False),
                              capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return {"error": f"Не уложился в {TIMEOUT} с"}
    try:
        out = json.loads(proc.stdout[:MAX_OUTPUT * 2])
    except ValueError:
        return {"error": (proc.stderr or "Нет ответа").strip()[-500:]}
    if not out.get("ok"):
        return {"error": out.get("error")}
    text = json.dumps(out["result"], ensure_ascii=False, default=str)
    return {"result": out["result"] if len(text) <= MAX_OUTPUT else text[:MAX_OUTPUT] + "…"}


# --- calc: точные вычисления без exec ---

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
       ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
       ast.USub: operator.neg, ast.UAdd: operator.pos}
FUNCS = {name: getattr(math, name) for name in ("sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "log", "log10",
                                                 "log2", "exp", "floor", "ceil", "factorial", "radians", "degrees",
                                                 "hypot", "gcd")}


def _factorial(n):
    if not 0 <= n <= 500:
        raise ValueError("Факториал только до 500")
    return math.factorial(n)


FUNCS.update(abs=abs, round=round, min=min, max=max, factorial=_factorial)
CONSTS = {"pi": math.pi, "e": math.e}


def calc(expr: str) -> float | int:
    """Посчитать выражение: + - * / // % **, скобки, проценты как /100, функции math."""
    if not isinstance(expr, str) or not expr.strip() or len(expr) > 500:
        raise ValueError("Нужно выражение")
    expr = expr.replace("^", "**").replace("×", "*").replace("÷", "/").replace(",", ".")
    expr = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", expr)

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.Name) and node.id in CONSTS:
            return CONSTS[node.id]
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
            return OPS[type(node.op)](ev(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and (abs(right) > 1000 or abs(left) > 1e100):
                raise ValueError("Слишком большое число")
            return OPS[type(node.op)](left, right)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS
                and not node.keywords):
            return FUNCS[node.func.id](*(ev(a) for a in node.args))
        raise ValueError("Непонятное выражение")

    result = ev(ast.parse(expr.strip(), mode="eval"))
    if isinstance(result, float) and result.is_integer() and abs(result) < 1e15:
        return int(result)
    return round(result, 10) if isinstance(result, float) else result
