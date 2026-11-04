"""Reusable asynchronous Chicken Smoothie access."""

from .archive import ArchiveEvent, ArchivePage, Item, Pet
from .client import AuthenticationError, Client, NEWS_FEED_URL
from .pound import OpeningClosed, OpeningOpen, OpeningStatus
from .links import is_valid_chickensmoothie_link, parse_item_ids


async def get_pet(pet_id: str, *, years=None) -> Pet | None:
    async with Client() as client:
        return await client.get_pet(pet_id, years=years)


async def get_archive(pet_id: str, *, years=None) -> list[Pet]:
    async with Client() as client:
        return await client.get_archive(pet_id, years=years)


async def get_opening_status() -> OpeningStatus:
    async with Client() as client:
        return await client.get_opening_status()


__all__ = [
    "Client",
    "AuthenticationError",
    "ArchiveEvent",
    "ArchivePage",
    "Pet",
    "Item",
    "OpeningClosed",
    "OpeningOpen",
    "OpeningStatus",
    "NEWS_FEED_URL",
    "get_pet",
    "get_archive",
    "get_opening_status",
    "is_valid_chickensmoothie_link",
    "parse_item_ids",
]
