"""Один запрос к агенту; workspace — папка, из которой вызвали команду."""
import argparse
import json
import logging
from pathlib import Path
import sys
from .clients import DeepSeekModel
from .config import Config
from .diagnostics import describe_error
from . import harness

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name.removesuffix(".exe"), description=__doc__,
        epilog='Пример: %(prog)s "Что в файле README.md?"',
    )
    parser.add_argument("question", nargs="+", help="Запрос, с кавычками или без")
    args = parser.parse_args(argv)
    question = " ".join(args.question).strip()
    if not question:
        parser.error("передайте непустой запрос")
        
    model = None
    try:
        root = Path.cwd().resolve(strict=True)
        config = Config.from_env(workspace_root=root)
        config.bind_workspace(root)
        
        if config.log_events:
            logging.basicConfig(level=logging.INFO, format="%(message)s")
            
        # --- ЗАГРУЗКА ИСТОРИИ ---
        history_file = root / ".agent_history.json"
        initial_messages = []
        if config.history_turns > 0 and history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    initial_messages = json.load(f)
            except Exception:
                initial_messages = []  # Игнорируем битые файлы истории

        model = DeepSeekModel(config=config)
        result = harness.run(model, question, config, initial_messages=initial_messages)
        
        if result.reason == "max_steps":
            raise RuntimeError(f"max_steps: достигнут лимит {config.max_steps} запросов к модели")
            
        print(f"Ответ: {result.answer}")
        
        # --- СОХРАНЕНИЕ ИСТОРИИ ---
        if config.history_turns > 0 and result.reason == "ok":
            try:
                # Находим все индексы пользовательских сообщений (начало каждого диалога)
                user_indices = [i for i, msg in enumerate(result.messages) if msg["role"] == "user"]
                
                # Если вопросов больше, чем разрешено памятью, обрезаем самые старые
                if len(user_indices) > config.history_turns:
                    start_idx = user_indices[-config.history_turns]
                    messages_to_save = result.messages[start_idx:]
                else:
                    messages_to_save = result.messages
                    
                with open(history_file, "w", encoding="utf-8") as f:
                    json.dump(messages_to_save, f, ensure_ascii=False, indent=2)
            except Exception:
                pass  # Не ломаем программу, если не удалось сохранить
                
        return 0
    except Exception as error:
        print(f"Ошибка: {describe_error(error)}", file=sys.stderr)
        return 1
    finally:
        if model is not None:
            model.close()