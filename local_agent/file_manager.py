"""Инструменты создания файлов и директорий внутри workspace."""
import os
from pathlib import Path
from .workspace import FileToolError, MAX_FILE_BYTES, as_workspace


def create_file(path, content, *, workspace):
    """Создаёт файл внутри workspace. Не перезаписывает существующие."""
    if not isinstance(path, str) or not path.strip():
        raise FileToolError("invalid_arguments")
    if not isinstance(content, str):
        raise FileToolError("invalid_arguments")
    
    scope = as_workspace(workspace)
    
    # Проверяем, что путь валиден и внутри workspace
    # resolve(strict=False) позволяет работать с несуществующими путями
    raw = Path(path)
    if raw.drive and not raw.is_absolute():
        raise PermissionError("file_access_denied")
    
    candidate = raw if raw.is_absolute() else scope.root / raw
    try:
        target = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise FileToolError("invalid_path") from error
    
    # Проверяем, что путь внутри workspace
    if not target.is_relative_to(scope.root):
        raise PermissionError("file_access_denied")
    
    # Проверяем, что нет .env в пути
    relative = target.relative_to(scope.root)
    if any(part.casefold() == ".env" for part in relative.parts):
        raise PermissionError("file_access_denied")
    
    # Проверяем, что файл ещё не существует
    if target.exists():
        raise FileToolError("file_already_exists")
    
    # Проверяем размер контента
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise FileToolError("file_too_large")
    
    # Создаём файл
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encoded)
    
    return {
        "path": relative.as_posix(),
        "created": True,
        "size_bytes": len(encoded),
    }


def create_directory(path, *, workspace):
    """Создаёт директорию внутри workspace, включая вложенные."""
    if not isinstance(path, str) or not path.strip():
        raise FileToolError("invalid_arguments")
    
    scope = as_workspace(workspace)
    
    raw = Path(path)
    if raw.drive and not raw.is_absolute():
        raise PermissionError("file_access_denied")
    
    candidate = raw if raw.is_absolute() else scope.root / raw
    try:
        target = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise FileToolError("invalid_path") from error
    
    if not target.is_relative_to(scope.root):
        raise PermissionError("file_access_denied")
    
    relative = target.relative_to(scope.root)
    if any(part.casefold() == ".env" for part in relative.parts):
        raise PermissionError("file_access_denied")
    
    # Если директория уже существует
    if target.exists():
        if target.is_dir():
            return {
                "path": relative.as_posix(),
                "created": False,
                "reason": "directory_already_exists",
            }
        else:
            raise FileToolError("not_a_directory")
    
    # Создаём директорию (включая родительские)
    target.mkdir(parents=True, exist_ok=True)
    
    return {
        "path": relative.as_posix(),
        "created": True,
    }