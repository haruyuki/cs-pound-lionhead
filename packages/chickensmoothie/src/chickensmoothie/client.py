"""HTTP access, with explicit session ownership and no application configuration."""

from datetime import datetime, timezone
from collections.abc import Iterable
from urllib.parse import urljoin, urlparse

import aiohttp
import lxml.html

from .archive import ArchiveEvent, Pet, TableType, get_event_title, parse_archive
from .pound import parse_opening_status

BASE_URL = "https://www.chickensmoothie.com"
NEWS_FEED_URL = "https://chickensmoothie.com/rss.php?feed=news"


class AuthenticationError(Exception):
    """Chicken Smoothie did not accept the supplied credentials."""


class Client:
    """Use as an async context manager; an injected session remains caller-owned."""

    def __init__(self, session: aiohttp.ClientSession | None = None):
        self._session = session
        self._owns_session = session is None
        self.username = None

    async def __aenter__(self):
        if self._session is None:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": "chickensmoothie-python/0.1.0"},
                timeout=aiohttp.ClientTimeout(total=60),
            )
        if self._session.closed:
            raise RuntimeError("Client session is closed")
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def close(self):
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    def _require_session(self):
        if self._session is None or self._session.closed:
            raise RuntimeError("Use Client inside 'async with Client()'")
        return self._session

    async def _text(self, path):
        url = urljoin(BASE_URL, path)
        if urlparse(url).netloc != urlparse(BASE_URL).netloc:
            raise ValueError("Expected a Chicken Smoothie URL")
        async with self._require_session().get(url) as response:
            response.raise_for_status()
            return await response.text()

    async def login(self, username: str, password: str) -> None:
        if not username or not password:
            raise ValueError("username and password are required")
        payload = {
            "username": username,
            "password": password,
            "redirect": "index.php",
            "autologin": "on",
            "login": "Login",
        }
        async with self._require_session().post(
            BASE_URL + "/Forum/ucp.php?mode=login", data=payload
        ) as response:
            response.raise_for_status()
            dom = lxml.html.fromstring(await response.text())
        messages = dom.xpath('//div[@id="message"]//p/text()')
        if not messages or messages[0] != "You have been successfully logged in.":
            raise AuthenticationError("ChickenSmoothie login failed.")
        self.username = username

    async def is_logged_in(self, username: str | None = None) -> bool:
        dom = lxml.html.fromstring(await self._text("/"))
        labels = dom.xpath('//li[@class="icon-logout"]/a/text()')
        expected = username or self.username
        return bool(labels and (expected is None or expected in labels[0]))

    async def get_opening_status(self):
        return parse_opening_status(await self._text("/poundandlostandfound.php"))

    async def get_archive_events(self, year: int, table: TableType = "pets"):
        if table not in ("pets", "items"):
            raise ValueError("table must be 'pets' or 'items'")
        if not isinstance(year, int) or year < 2008:
            raise ValueError("year must be an integer from 2008 onward")
        path = f"/archive/{year}/" + ("Items/" if table == "items" else "")
        dom = lxml.html.fromstring(await self._text(path))
        return [
            ArchiveEvent(
                get_event_title(urlparse(a.get("href")).path),
                urljoin(BASE_URL, a.get("href")),
            )
            for a in dom.cssselect("li.event > a[href]")
        ]

    async def get_archive_event(self, event: ArchiveEvent, table: TableType, year: int):
        text = await self._text(event.link.split("?")[0] + "?pageSize=3000")
        return parse_archive(text, event, table, year)

    async def get_archive(
        self, pet_id: str, *, years: Iterable[int] | None = None
    ) -> list[Pet]:
        """Find all archive records for an image's k ID."""
        return [entry async for entry in self._iter_pet_matches(pet_id, years)]

    async def _iter_pet_matches(self, pet_id: str, years: Iterable[int] | None):
        if not isinstance(pet_id, str) or not pet_id.strip():
            raise ValueError("pet_id must be a nonempty image k ID")
        if years is None:
            years = range(2008, datetime.now(timezone.utc).year + 1)
        for year in dict.fromkeys(years):
            for event in await self.get_archive_events(year):
                page = await self.get_archive_event(event, "pets", year)
                for entry in page.entries:
                    if isinstance(entry, Pet) and entry.id == pet_id:
                        yield entry

    async def get_pet(
        self, pet_id: str, *, years: Iterable[int] | None = None
    ) -> Pet | None:
        """Return the first archive record for an image k ID, or None."""
        async for entry in self._iter_pet_matches(pet_id, years):
            return entry
        return None
