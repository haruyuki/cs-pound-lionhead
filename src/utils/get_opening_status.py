import re
from dataclasses import dataclass

import aiohttp
import lxml.html


@dataclass
class OpeningClosed:
    is_open: bool = False
    event_type: str | None = None
    remaining_minutes: int | None = None


@dataclass
class OpeningOpen:
    is_open: bool = True
    event_type: str = ""
    remaining_count: int = 0


OpeningStatus = OpeningClosed | OpeningOpen


async def get_opening_status(
    session: aiohttp.ClientSession,
) -> OpeningStatus:
    async with session.get("/poundandlostandfound.php") as resp:
        resp.raise_for_status()
        text = await resp.text()
        dom = lxml.html.fromstring(text)

    event_header = normalise(get_first_text(dom, '//div[@id="csbody"]//h2[1]/text()'))

    countdown_text = normalise(
        get_first_text(dom, '//*[@id="pound-open-countdown"]/text()')
    )
    event_type = get_event_type(event_header)

    closed_minutes = extract_minutes(countdown_text)
    if closed_minutes != 0:
        return OpeningClosed(
            is_open=False,
            event_type=event_type,
            remaining_minutes=closed_minutes,
        )

    if event_header == "The Pound" or event_header == "The Lost and Found":
        remaining_count = extract_remaining_count(dom, event_type)
        return OpeningOpen(
            is_open=True, event_type=event_type, remaining_count=remaining_count
        )

    return OpeningClosed(
        is_open=False, event_type=None, remaining_minutes=None
    )  # If both are closed


def normalise(value: str) -> str:
    return " ".join(value.split())


def get_first_text(dom: lxml.html.HtmlElement, xpath: str) -> str:
    values = dom.xpath(xpath)
    return str(values[0]) if values else ""


def get_event_type(text: str) -> str:
    return "Pound" if "pound" in text.lower() else "Lost and Found"


def extract_minutes(text: str) -> int:
    match = re.search(
        r"(?:pound|lost and found).*?(?:in:|within)\s*(?:(\d+)\s*hours?)?\s*(?:,?\s*(\d+)\s*minutes?)?",
        text,
        re.IGNORECASE,
    )
    if not match:
        return 0
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    return hours * 60 + minutes


def extract_remaining_count(dom: lxml.html.HtmlElement, event: str) -> int:
    selector = (
        '//div[@id="pets-remaining"]/text()'
        if event == "Pound"
        else '//div[@id="items-remaining"]/text()'
    )
    remaining_text = get_first_text(dom, selector)

    match = re.search(r"\d+", remaining_text)
    return int(match.group()) if match else 0
