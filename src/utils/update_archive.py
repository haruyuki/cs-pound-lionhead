from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp
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


async def fetch_event_links(
    session: aiohttp.ClientSession, year: int, table: TableType
) -> list[str]:
    path = f"/archive/{year}/" if table == "pets" else f"/archive/{year}/Items/"
    async with session.get(path) as resp:
        if resp.status != 200:
            return []
        text = await resp.text()

    dom = lxml.html.fromstring(text)
    links = [a.get("href") for a in dom.cssselect("li.event > a")]
    return links


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


async def process_event(
    session: aiohttp.ClientSession,
    conn: Any,
    event: ArchiveEvent,
    table: TableType,
    year: int,
) -> tuple[int, int] | None:
    all_data_link = f"{event.link}?pageSize=3000"
    async with session.get(all_data_link) as resp:
        if resp.status != 200:
            logging.warning(
                "Skipping event %s (%s): HTTP %s",
                event.title,
                all_data_link,
                resp.status,
            )
            return None
        text = await resp.text()

    dom = lxml.html.fromstring(text)
    group_type = CSS_PET_GROUP if table == "pets" else CSS_ITEM_GROUP
    group_nodes = dom.cssselect(group_type)
    group_count = len(group_nodes)

    added_stats = 0
    for group_index, group_node in enumerate(group_nodes):
        added_stats += await process_page(
            conn,
            group_node,
            event.link,
            table,
            year,
            event.title,
            group_index,
        )

    return group_count, added_stats


async def process_page(
    conn: Any,
    group_node: Any,
    base_link: str,
    table: TableType,
    year: int,
    event_title: str,
    group_index: int,
) -> int:
    groups_per_page = 7 if table == "pets" else 10
    page_number = group_index // groups_per_page
    clean_base = base_link.split("?")[0]
    stored_page_link = (
        clean_base
        if page_number == 0
        else f"{clean_base}?pageStart={page_number * groups_per_page}"
    )
    added_count = 0

    match table:
        case "pets":
            image_links = [
                img.get("src") for img in group_node.cssselect('img[alt="Pet"]')
            ]

            for link in image_links:
                pet_id = parse_qs(urlparse(link).query).get("k", [None])[0]
                if pet_id in EXCEPTIONS:
                    continue

                await conn.execute(
                    "INSERT OR REPLACE INTO Pets (petID, petYear, petEvent, petLink) VALUES (?, ?, ?, ?)",
                    (pet_id, year, event_title, stored_page_link),
                )
                added_count += 1
        case "items":
            item_nodes = group_node.cssselect("li.item")
            for item in item_nodes:
                image_link = item.cssselect("img")[0].get("src")

                left_id, right_id = parse_item_ids(image_link)
                if left_id is None or right_id is None:
                    continue

                name = item.cssselect("div.item-name")[0].text_content().strip()
                await conn.execute(
                    "INSERT OR REPLACE INTO Items (itemLID, itemRID, itemName, itemYear, itemEvent, itemLink) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        left_id,
                        right_id,
                        name,
                        year,
                        event_title,
                        stored_page_link,
                    ),
                )
                added_count += 1

    return added_count
