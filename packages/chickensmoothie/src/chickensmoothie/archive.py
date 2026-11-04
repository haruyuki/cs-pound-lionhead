from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, unquote, urlparse

import lxml.html

MONTHS = {
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
}

CSS_PET_GROUP = ".archive-pet-tree-container"
CSS_ITEM_GROUP = ".archive-item-group"

EXCEPTIONS = {
    "3B46301A6C8B850D87A730DA365B0960",
    "E5FEFE44A3070BC9FC176503EC1A603F",
    "0C1AFF9AEAA0953F1B1F9B818C2771C9",
    "7C912BA5616D2E24E9F700D90E4BA2B6",
    "905BB7DE4BC4E29D7FD2D1969667B568",
    "773B14EEB416FA762C443D909FFED344",
    "1C0DB4785FC78DF4395263D40261C614",
    "5066110701B0AE95948A158F0B262EBB",
    "5651A6C10C4D375A1901142C49C5C70C",
    "8BED72498D055E55ABCA7AD29B180BF4",
}

Category = Literal["monthly", "special"]
TableType = Literal["pets", "items"]


@dataclass(slots=True)
class ArchiveEvent:
    title: str
    link: str


def get_event_title(link: str) -> str:
    pattern = re.compile(r"^/archive/\d{4}/(?P<event>[^/]+)(?:/Items)?/?$")
    match = pattern.match(link)
    if not match:
        return "Unknown Event"
    return unquote(match.group("event"))


def get_category(event_title: str) -> Category:
    return "monthly" if event_title in MONTHS else "special"


def parse_item_ids(image_link: str) -> tuple[int | None, int | None]:
    parsed = urlparse(image_link)
    pattern = re.compile(r"/item/(\d+)&p=(\d+)")
    match = pattern.search(parsed.path)
    if match:
        return int(match.group(1)), int(match.group(2))

    query = parse_qs(parsed.query)
    left = query.get("lid", [None])[0] or query.get("l", [None])[0]
    right = query.get("rid", [None])[0] or query.get("p", [None])[0]
    if left and right:
        return int(left), int(right)

    return None, None


@dataclass(frozen=True, slots=True)
class Pet:
    id: str
    year: int
    event: str
    archive_url: str
    image_url: str


@dataclass(frozen=True, slots=True)
class Item:
    left_id: int
    right_id: int
    name: str
    year: int
    event: str
    archive_url: str
    image_url: str


@dataclass(slots=True)
class ArchivePage:
    group_count: int
    entries: list[Pet | Item]


def parse_archive(
    text: str, event: ArchiveEvent, table: TableType, year: int
) -> ArchivePage:
    from urllib.parse import urljoin

    if table not in ("pets", "items"):
        raise ValueError("table must be 'pets' or 'items'")
    dom = lxml.html.fromstring(text)
    groups = dom.cssselect(CSS_PET_GROUP if table == "pets" else CSS_ITEM_GROUP)
    entries = []
    groups_per_page = 7 if table == "pets" else 10
    base = event.link.split("?")[0]
    for index, group in enumerate(groups):
        offset = (index // groups_per_page) * groups_per_page
        page = f"{base}?pageStart={offset}" if offset else base
        if table == "pets":
            for image in group.cssselect('img[alt="Pet"][src]'):
                image_url = urljoin(event.link, image.get("src"))
                pet_id = parse_qs(urlparse(image_url).query).get("k", [None])[0]
                if pet_id and pet_id not in EXCEPTIONS:
                    entries.append(Pet(pet_id, year, event.title, page, image_url))
        else:
            for item in group.cssselect("li.item"):
                images = item.cssselect("img[src]")
                names = item.cssselect("div.item-name")
                if not images or not names:
                    continue
                image_url = urljoin(event.link, images[0].get("src"))
                try:
                    left, right = parse_item_ids(image_url)
                except ValueError:
                    continue
                if left is not None and right is not None:
                    entries.append(
                        Item(
                            left,
                            right,
                            names[0].text_content().strip(),
                            year,
                            event.title,
                            page,
                            image_url,
                        )
                    )
    return ArchivePage(len(groups), entries)
