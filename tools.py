"""Обычные функции, их описания для модели и проверка входных данных."""

import json
import math


def add(a, b):
    return a + b


def divide(a, b):
    return a / b


TOOL_REGISTRY = {"add": add, "divide": divide}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "Первое число"},
                    "b": {"type": "number", "description": "Второе число"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
        },
    }
    for name, description in [
        ("add", "Сложить два числа a и b."),
        ("divide", "Разделить a на b. При b=0 инструмент выдаёт ошибку."),
    ]
]


def parse_arguments(raw):
    """JSON-строка -> словарь с двумя конечными числами; schema этого не делает."""
    if not isinstance(raw, str):
        raise ValueError("arguments должен быть JSON-строкой")
    args = json.loads(raw)
    if not isinstance(args, dict) or set(args) != {"a", "b"}:
        raise ValueError("Нужен объект ровно с ключами a и b")
    for value in args.values():
        if type(value) not in (int, float):
            raise ValueError("a и b должны быть числами, не строками или bool")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("a и b должны быть конечными числами")
    return args
