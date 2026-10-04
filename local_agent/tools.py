"""Обычные функции, их описания для модели и проверка входных данных."""
import json
import math
from .file_browser import list_files
from .file_edit import replace_in_file
from .file_manager import create_file, create_directory
from .workspace import read_file

def add(a, b):
    return a + b

def divide(a, b):
    return a / b

def multiply(a, b):
    return a * b

def subtraction(a, b):
    return a - b

TOOL_REGISTRY = {
    "add": add,
    "divide": divide,
    "multiply": multiply,
    "subtraction": subtraction,
    "read_file": read_file,
    "list_files": list_files,
    "replace_in_file": replace_in_file,
    "create_file": create_file,      # <-- НОВОЕ
    "create_directory": create_directory,  # <-- НОВОЕ
}

# Карта ожидаемых ключей для каждого инструмента
TOOL_PARAMS = {
    "add": {"a", "b"},
    "divide": {"a", "b"},
    "multiply": {"a", "b"},
    "subtraction": {"a", "b"},
    "read_file": {"path"},
    "list_files": {"path", "recursive", "limit"},
    "replace_in_file": {"path", "old_text", "new_text"},
    "create_file": {"path", "content"},      # <-- НОВОЕ
    "create_directory": {"path"},            # <-- НОВОЕ
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": req,
                "additionalProperties": False,
            },
        },
    }
    for name, description, props, req in [
        ("add", "Сложить два числа a и b.",
         {"a": {"type": "number", "description": "Первое число"}, "b": {"type": "number", "description": "Второе число"}}, ["a", "b"]),
        ("divide", "Разделить a на b. При b=0 инструмент выдаёт ошибку.",
         {"a": {"type": "number", "description": "Делимое"}, "b": {"type": "number", "description": "Делитель"}}, ["a", "b"]),
        ("multiply", "Умножить число a на число b.",
         {"a": {"type": "number", "description": "Первый множитель"}, "b": {"type": "number", "description": "Второй множитель"}}, ["a", "b"]),
        ("subtraction", "Вычесть число b из числа a.",
         {"a": {"type": "number", "description": "Уменьшаемое"}, "b": {"type": "number", "description": "Вычитаемое"}}, ["a", "b"]),
        ("read_file", "Прочитать содержимое файла по указанному пути.",
         {"path": {"type": "string", "description": "Путь к файлу относительно workspace"}}, ["path"]),
        ("list_files", "Просмотреть файлы и папки в указанной директории.",
         {"path": {"type": "string", "description": "Путь к папке относительно workspace"},
          "recursive": {"type": "boolean", "description": "Рекурсивно обходить подпапки"},
          "limit": {"type": "integer", "description": "Максимальное количество записей (1-2000)"}}, ["path", "recursive", "limit"]),
        ("replace_in_file", "Точечно заменить фрагмент текста в файле. Старый фрагмент должен встречаться ровно один раз.",
         {"path": {"type": "string", "description": "Путь к файлу относительно workspace"},
          "old_text": {"type": "string", "description": "Текст для замены"},
          "new_text": {"type": "string", "description": "Новый текст"}}, ["path", "old_text", "new_text"]),
        ("create_file", "Создать новый файл внутри workspace. Не перезаписывает существующие файлы.",
         {"path": {"type": "string", "description": "Путь к файлу относительно workspace"},
          "content": {"type": "string", "description": "Содержимое файла"}}, ["path", "content"]),
        ("create_directory", "Создать директорию внутри workspace, включая вложенные.",
         {"path": {"type": "string", "description": "Путь к директории относительно workspace"}}, ["path"]),
    ]
]


def parse_arguments(raw, tool_name):
    """JSON-строка -> словарь с проверкой ожидаемых ключей."""
    if not isinstance(raw, str):
        raise ValueError("arguments должен быть JSON-строкой")
    args = json.loads(raw)

    expected = TOOL_PARAMS.get(tool_name, {"a", "b"})
    if not isinstance(args, dict) or set(args) != expected:
        raise ValueError(f"Нужен объект ровно с ключами {expected}")

    for key, value in args.items():
        if key in ("recursive",):
            if type(value) is not bool:
                raise ValueError(f"{key} должен быть boolean")
        elif key in ("limit",):
            if type(value) is not int or not 1 <= value <= 2000:
                raise ValueError(f"{key} должен быть целым числом от 1 до 2000")
        elif key in ("a", "b"):
            if type(value) not in (int, float):
                raise ValueError(f"{key} должен быть числом")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"{key} должно быть конечным числом")
        elif key in ("path", "old_text", "new_text", "content"):
            if not isinstance(value, str):
                raise ValueError(f"{key} должен быть строкой")
    return args