import re
import math
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
    event_type: str | None = ""
    remaining_count: int = 0


OpeningStatus = OpeningClosed | OpeningOpen


async def get_opening_status(
    session: aiohttp.ClientSession,
) -> OpeningStatus:
    async with session.get("/poundandlostandfound.php") as resp:
        resp.raise_for_status()
        text = await resp.text()
        dom = lxml.html.fromstring(text)

    event_type = get_event_type(
        normalise(get_first_text(dom, '//div[@id="csbody"]//h2[1]/text()'))
    )
    has_pick_countdown = bool(dom.xpath('//*[@id="pound-pick-countdown"]'))

    script_match = re.search(r'"timeTillOpen_ms"\s*:\s*(\d+)', text)
    remaining_ms = int(script_match.group(1)) if script_match else None

    if has_pick_countdown:
        remaining_count = extract_remaining_count(dom, event_type)
        return OpeningOpen(
            is_open=True, event_type=event_type, remaining_count=remaining_count
        )

    if remaining_ms is not None:
        return OpeningClosed(
            is_open=False,
            event_type=event_type,
            remaining_minutes=max(0, math.floor(remaining_ms / 60000)),
        )

    return OpeningClosed(
        is_open=False, event_type=None, remaining_minutes=None
    )  # If both are closed


def normalise(value: str) -> str:
    return " ".join(value.split())


def get_first_text(dom: lxml.html.HtmlElement, xpath: str) -> str:
    values = dom.xpath(xpath)
    return str(values[0]) if values else ""


def get_event_type(text: str) -> str | None:
    lowered = text.lower()
    if "lost and found" in lowered:
        return "Lost and Found"
    if "pound" in lowered:
        return "Pound"
    return None


def extract_minutes(text: str) -> int | None:
    match = re.search(
        r"(?:pound|lost and found).*?(?:in:|within)\s*(?:(\d+)\s*hours?)?\s*(?:,?\s*(\d+)\s*minutes?)?",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    return hours * 60 + minutes


def extract_remaining_count(dom: lxml.html.HtmlElement, event: str | None) -> int:
    if event == "Pound":
        remaining_text = normalise(dom.xpath('string(//*[@id="pets-remaining"])'))
    else:  # Lost and Found
        remaining_text = normalise(dom.xpath('string(//*[@id="items-remaining"])'))

    match = re.search(r"\d[\d,]*", remaining_text)
    if match:
        return int(match.group().replace(",", ""))
    return 0
