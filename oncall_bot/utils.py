from typing import Any


def get_key(item: Any, path: str, default_value: Any=None) -> Any:
    paths = path.split(".")
    v = item
    for p in paths:
        if isinstance(v, list):
            v = v[int(p)] if int(p) < len(v) else None
        elif hasattr(v, "get"):
            v = v.get(p, None)
        else:
            v = None
        if v is None:
            return default_value
    return v
