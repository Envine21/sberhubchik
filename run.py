"""Один запрос пользователя к harness с настоящим DeepSeek Flash."""

import argparse
import sys

from local_agent.clients import DeepSeekModel
from local_agent.diagnostics import describe_error
import local_agent.harness as harness


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, usage='%(prog)s "запрос пользователя"', add_help=False,
    )
    parser.add_argument("question", nargs="?", help="Запрос пользователя в кавычках")
    parser.add_argument("-h", "--help", action="help", help="Показать справку")
    args = parser.parse_args(argv)
    if not args.question or not args.question.strip():
        print('Ошибка: передайте непустой запрос, например: python run.py "Сложи 18 и 24"', file=sys.stderr)
        return 2

    model = None
    try:
        model = DeepSeekModel()
        result = harness.run(model, args.question) # <-- теперь возвращает RunResult
        
        if result.reason == "max_steps":
            raise RuntimeError(f"max_steps: достигнут лимит запросов к модели")
            
        if model.last_response and model.last_response["message"].get("tool_calls"):
            raise RuntimeError("Работа завершилась до получения окончательного ответа модели.")
        if not isinstance(result.answer, str) or not result.answer.strip(): # <-- используем result.answer
            raise RuntimeError("Программа завершилась без текстового ответа.")
        print(f"Ответ: {result.answer}") # <-- используем result.answer
        return 0
    except Exception as error:
        print(f"Ошибка: {describe_error(error)}", file=sys.stderr)
        return 1
    finally:
        if model is not None:
            model.close()


if __name__ == "__main__":
    sys.exit(main())
