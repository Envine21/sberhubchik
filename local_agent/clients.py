"""Адаптер настоящего DeepSeek Chat Completions API."""

from copy import deepcopy
import os
from pathlib import Path
from typing import Optional

DEFAULT_MODEL = "deepseek-flash"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

class RequestLimitExceeded(RuntimeError):
    """Внешняя страховка от бесконечных платных запросов при отладке."""


class DeepSeekModel:
    def __init__(
        self, 
        model: str = DEFAULT_MODEL, 
        *, 
        client=None, 
        watchdog: int = 8,
        config=None  # <-- НОВОЕ: принимаем config из cli.py
    ):
        # Если передан config, берем значения из него для синхронизации
        if config is not None:
            watchdog = config.max_steps
            
        if type(watchdog) is not int or watchdog < 1:
            raise ValueError("watchdog должен быть положительным целым")
            
        if client is None:
            from dotenv import load_dotenv

            load_dotenv(ENV_PATH, override=False, encoding="utf-8-sig")
            api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                raise RuntimeError("Заполните DEEPSEEK_API_KEY в .env рядом с clients.py (образец: .env.example)")
            from openai import OpenAI

            # Используем timeout из config, если он есть, иначе оставляем 20.0
            timeout_val = config.model_timeout if config is not None else 20.0

            client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com",
                timeout=timeout_val,
                max_retries=0,
            )
        self.client = client
        self.model = model
        self.watchdog = watchdog
        self.calls = 0
        self.last_response = None

    def __call__(self, *, messages, tools):
        # Учебный предохранитель клиента; это не нормальная остановка harness.
        if self.calls >= self.watchdog:
            raise RequestLimitExceeded(
                f"Достигнут клиентский лимит: {self.watchdog} запросов. Работа не завершена."
            )
        self.calls += 1
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            stream=False,
            max_tokens=4096,
            extra_body={"thinking": {"type": "disabled"}},
        )
        choice = response.choices[0]
        message = {"role": "assistant", "content": choice.message.content}
        if choice.message.tool_calls:
            message["tool_calls"] = [
                call.model_dump(exclude_none=True) for call in choice.message.tool_calls
            ]
        reply = {"message": message, "finish_reason": choice.finish_reason}
        self.last_response = deepcopy(reply)
        return reply

    def close(self):
        self.client.close()