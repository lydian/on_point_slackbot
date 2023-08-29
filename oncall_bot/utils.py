from typing import Any, Callable, List, Optional


def get_key(item: Any, path: str, default_value: Any = None) -> Any:
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


def MinMaxValidator(min: Optional[int] = None, max: Optional[int] = None) -> Callable[[List[str]], Optional[str]]:

    def validator(values: List[str]) -> Optional[str]:
        if min is not None and len(values) < min:
            return f"The argument is too short, expected at least {min} got {len(values)}"
        if max is not None and len(values) > max:
            return f"The argument is too long, expected at most {max} got {len(values)}"
        return None

    return validator
