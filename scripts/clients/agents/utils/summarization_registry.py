from typing import Optional, Callable

_summarizer: Optional[Callable[[str], str]] = None

def set_summarizer(fn: Callable[[str], str]):
    global _summarizer
    _summarizer = fn

def get_summarizer() -> Optional[Callable[[str], str]]:
    return _summarizer