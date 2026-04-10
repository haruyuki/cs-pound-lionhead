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
        opening_string = dom.xpath("//h2[2]/text()")
        is_open_check = dom.xpath("//h2[last()]/text()")

    if is_open_check[0] in [
        "The Pound",
        "The Lost and Found",
    ]:  # If either Pound or Lost and Found is open
        event = is_open_check[0][4:]
        if event == "Lost and Found":
            remaining_selector = dom.xpath('//div[@id="items-remaining"]/text()')
        else:
            remaining_selector = dom.xpath('//div[@id="pets-remaining"]/text()')
        remaining_text = remaining_selector[0] if remaining_selector else ""
        match = re.search(r"\d+", remaining_text)
        remaining_count = int(match.group()) if match else 0
        return OpeningOpen(
            is_open=True, event_type=event, remaining_count=remaining_count
        )

    opening_string = (
        " ".join(opening_string[0].strip().split()) if opening_string else ""
    )
    match = re.search(
        r"(Pound|Lost and Found).*?(?:in:|within)\s*(?:(\d+)\s*hours?)?\s*(?:,?\s*(\d+)\s*minutes?)?",
        opening_string,
    )
    if match:  # If either Pound or Lost and Found is closed
        event = "Pound" if match.group(1) == "pound" else "Lost and Found"
        hours = int(match.group(2)) if match.group(2) else 0
        minutes = int(match.group(3)) if match.group(3) else 0
        total_minutes = hours * 60 + minutes
        return OpeningClosed(
            is_open=False, event_type=event, remaining_minutes=total_minutes
        )

    return OpeningClosed(
        is_open=False, event_type=None, remaining_minutes=None
    )  # If both are closed
