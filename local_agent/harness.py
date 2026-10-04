"""Базовый синхронный harness: messages -> model -> tools -> messages."""
import json
import math
import time
import concurrent.futures
from dataclasses import dataclass
from typing import Optional

from .clients import DeepSeekModel
from .config import Config
from .file_edit import WriteGuard, replace_in_file
from .file_browser import list_files
from .logging_utils import RunLogger
from .tools import TOOL_REGISTRY, TOOL_SCHEMAS, parse_arguments
from .workspace import Workspace, FileToolError


@dataclass
class RunResult:
    """Результат выполнения harness."""
    answer: str
    reason: str  # "ok", "max_steps", "model_timeout", "error"
    messages: list  

def execute_tool(call, config: Config, logger: Optional[RunLogger] = None, step: Optional[int] = None):
    """Найти функцию, проверить arguments и выполнить вызов."""
    name = call["function"]["name"]
    call_id = call.get("id")

    if name not in TOOL_REGISTRY:
        if logger:
            logger.log("tool_end", "error", step=step, call_id=call_id, tool=name, error="unknown_tool")
        return {"error": f"unknown_tool: {name}"}

    tool = TOOL_REGISTRY[name]
    try:
        args = parse_arguments(call["function"]["arguments"], name)
    except ValueError:
        if logger:
            logger.log("tool_end", "error", step=step, call_id=call_id, tool=name, error="invalid_arguments")
        return {"error": "invalid_arguments"}

    if name in ("read_file", "list_files", "replace_in_file", "create_file", "create_directory"):
        args["workspace"] = config.workspace

    # Для replace_in_file создаём WriteGuard, связанный с tool_timeout
    if name == "replace_in_file":
        args["guard"] = WriteGuard(seconds=config.tool_timeout)

    if logger:
        logger.log("tool_start", "start", step=step, call_id=call_id, tool=name)

    started_at = time.monotonic()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(tool, **args)
            result = future.result(timeout=config.tool_timeout)
        duration_ms = (time.monotonic() - started_at) * 1000
        if logger:
            logger.log("tool_end", "ok", step=step, call_id=call_id, tool=name, duration_ms=duration_ms)
    except concurrent.futures.TimeoutError:
        duration_ms = (time.monotonic() - started_at) * 1000
        if logger:
            logger.log("tool_end", "error", step=step, call_id=call_id, tool=name, duration_ms=duration_ms, error="tool_timeout")
        # Для replace_in_file отменяем guard, чтобы поздняя запись не произошла
        if name == "replace_in_file" and "guard" in args:
            args["guard"].cancel()
        return {"error": "tool_timeout"}
    except FileToolError as e:
        duration_ms = (time.monotonic() - started_at) * 1000
        if logger:
            logger.log("tool_end", "error", step=step, call_id=call_id, tool=name, duration_ms=duration_ms, error=e.code)
        return {"error": e.code}
    except Exception as e:
        duration_ms = (time.monotonic() - started_at) * 1000
        if logger:
            logger.log("tool_end", "error", step=step, call_id=call_id, tool=name, duration_ms=duration_ms, error=str(e))
        return {"error": str(e)}

    if isinstance(result, float) and not math.isfinite(result):
        if logger:
            logger.log("tool_end", "error", step=step, call_id=call_id, tool=name, error="non_finite_result")
        return {"error": "non_finite_result"}
    return result


def tool_message(call_id, result):
    """Связать строковый результат с исходным вызовом модели."""
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": json.dumps(result, ensure_ascii=False, allow_nan=False),
    }


def run(ask_model, question, config: Config, initial_messages: list = None):
    logger = RunLogger()
    logger.log("run_start", "ok", question_preview=question)

    # Формируем начальные сообщения
    messages = [
        {
            "role": "system",
            "content": (
                "Ты учебный помощник. Для вычислений используй инструменты. "
                "Получив результаты, ответь по-русски. Если инструмент вернул "
                "ошибку, объясни её; не выдумывай результат вычисления. "
                "Перед изменением файла сначала прочитай его, возьми точный фрагмент "
                "и меняй только то, что попросил пользователь."
            ),
        }
    ]
    
    # Добавляем историю, если она есть
    if initial_messages:
        messages.extend(initial_messages)
        
    messages.append({"role": "user", "content": question})
    
    step = 0
    try:
        while True:
            step += 1
            if step > config.max_steps:
                logger.log("run_end", "max_steps", step=step)
                return RunResult(answer="", reason="max_steps", messages=messages)

            logger.log("model_request", "start", step=step)
            started_at = time.monotonic()
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(ask_model, messages=messages, tools=TOOL_SCHEMAS)
                    response = future.result(timeout=config.model_timeout)
                duration_ms = (time.monotonic() - started_at) * 1000
                logger.log("model_response", "ok", step=step, duration_ms=duration_ms)
            except concurrent.futures.TimeoutError:
                duration_ms = (time.monotonic() - started_at) * 1000
                logger.log("model_response", "error", step=step, duration_ms=duration_ms, error="model_timeout")
                return RunResult(answer="", reason="model_timeout", messages=messages)
            except Exception as e:
                duration_ms = (time.monotonic() - started_at) * 1000
                logger.log("model_response", "error", step=step, duration_ms=duration_ms, error=str(e))
                raise

            message = response["message"]
            reason = response["finish_reason"]
            if reason not in ("stop", "tool_calls"):
                raise RuntimeError(f"Ответ модели не завершён: {reason}")
            messages.append(message)
            logger.log("history_update", "ok", step=step, role=message.get("role"))

            calls = message.get("tool_calls") or []
            if not calls:
                if reason != "stop" or not isinstance(message.get("content"), str):
                    raise RuntimeError("Модель не вернула ни вызовов, ни финального текста")
                logger.log("run_end", "ok", step=step)
                return RunResult(answer=message["content"], reason="ok", messages=messages)

            for call in calls:
                result = execute_tool(call, config, logger, step)
                messages.append(tool_message(call["id"], result))
    except Exception as e:
        logger.log("run_end", "error", step=step, error=str(e))
        raise