"""Command-file parsing helpers."""
from datetime import date


def parse_date(text) -> date:
    return date.fromisoformat(str(text).strip())


def parse_params(text) -> dict:
    """'a=1;b=2;damage=x:10;damage=y:20' -> {'a': ['1'], 'b': ['2'], 'damage': [...]}"""
    result = {}
    for part in (text or "").split(";"):
        part = part.strip()
        if not part:
            continue
        key, _, value = part.partition("=")
        result.setdefault(key.strip().lower(), []).append(value.strip())
    return result


def first(params, key, default=None):
    values = params.get(key)
    return values[0] if values else default


def truthy(text) -> bool:
    return str(text or "").strip().upper() in ("Y", "YES", "TRUE", "1")
