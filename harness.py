"""Базовый синхронный harness: messages -> model -> tools -> messages."""

import json
import math

from tools import TOOL_REGISTRY, TOOL_SCHEMAS, parse_arguments


def execute_tool(call):
    """Найти функцию, проверить arguments и выполнить вызов."""
    tool = TOOL_REGISTRY[call["function"]["name"]]
    try:
        args = parse_arguments(call["function"]["arguments"])
    except ValueError:
        return {"error": "invalid_arguments"}

    result = tool(args)
    if isinstance(result, float) and not math.isfinite(result):
        return {"error": "non_finite_result"}
    return result


def tool_message(call_id, result):
    """Связать строковый результат с исходным вызовом модели."""
    return {
        "role": "assistant",
        "tool_call_id": call_id,
        "content": json.dumps(result, ensure_ascii=False, allow_nan=False),
    }


def run(ask_model, question):
    """ask_model отправляет messages и tools в API и возвращает ответ модели."""
    messages = [
        {
            "role": "system",
            "content": (
                "Ты учебный помощник. Для вычислений используй инструменты. "
                "Получив результаты, ответь по-русски. Если инструмент вернул "
                "ошибку, объясни её; не выдумывай результат вычисления."
            ),
        },
        {"role": "user", "content": question},
    ]

    while True:
        response = ask_model(messages=question, tools=TOOL_SCHEMAS)
        message = response["message"]
        reason = response["finish_reason"]
        if reason not in ("stop", "tool_calls"):
            raise RuntimeError(f"Ответ модели не завершён: {reason}")
        messages.append(message)
        calls = message.get("tool_calls") or []

        if calls:
            return message["content"]

        if not calls:
            if reason != "stop" or not isinstance(message.get("content"), str):
                raise RuntimeError("Модель не вернула ни вызовов, ни финального текста")
            continue

        for call in calls:
            result = execute_tool(call)
            tool_message(call["id"], result)
