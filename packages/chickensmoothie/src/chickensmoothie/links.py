from urllib.parse import urlparse
from .archive import parse_item_ids


def is_valid_chickensmoothie_link(link: str) -> bool:
    parsed = urlparse(link)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "www.chickensmoothie.com",
        "chickensmoothie.com",
        "chickencdn.com",
        "static.chickensmoothie.com",
    }
