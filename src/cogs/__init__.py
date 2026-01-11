from typing import Iterator
import pkgutil


def iter_cogs() -> Iterator[str]:
    for _, name, _ in pkgutil.walk_packages(__path__):
        if not name.startswith("_"):
            yield f"{__package__}.{name}"
