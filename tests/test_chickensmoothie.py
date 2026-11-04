import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from chickensmoothie import Client, AuthenticationError, Pet
from chickensmoothie.archive import ArchiveEvent, parse_archive, parse_item_ids
from chickensmoothie.pound import parse_opening_status
from src.cogs.updatedb.update_archive import process_event


class ParsingTests(unittest.TestCase):
    def test_opening_states(self):
        open_state = parse_opening_status(
            '<div id="csbody"><h2>Pound</h2></div><span id="pound-pick-countdown"></span><b id="pets-remaining">1,234 pets</b>'
        )
        self.assertTrue(open_state.is_open)
        self.assertEqual(open_state.remaining_count, 1234)
        closed = parse_opening_status(
            '<div id="csbody"><h2>Lost and Found</h2></div><script>{"timeTillOpen_ms": 119999}</script>'
        )
        self.assertFalse(closed.is_open)
        self.assertEqual(closed.remaining_minutes, 1)
        self.assertIsNone(parse_opening_status("<html>Closed</html>").event_type)

    def test_pet_page_links_and_missing_ids(self):
        group = '<div class="archive-pet-tree-container"><img alt="Pet" src="/pet.php?k=ABC"><img alt="Pet" src="/invalid"></div>'
        page = parse_archive(
            group * 8,
            ArchiveEvent(
                "January", "https://www.chickensmoothie.com/archive/2026/January/"
            ),
            "pets",
            2026,
        )
        self.assertEqual(page.group_count, 8)
        self.assertEqual(len(page.entries), 8)
        self.assertTrue(page.entries[-1].archive_url.endswith("?pageStart=7"))
        self.assertEqual(page.entries[0].id, "ABC")

    def test_items(self):
        html = '<div class="archive-item-group"><li class="item"><img src="https://chickencdn.com/item/12&amp;p=34"><div class="item-name"> Hat </div></li><li class="item"></li></div>'
        page = parse_archive(
            html,
            ArchiveEvent(
                "January", "https://www.chickensmoothie.com/archive/2026/January/Items/"
            ),
            "items",
            2026,
        )
        self.assertEqual(len(page.entries), 1)
        self.assertEqual(
            (page.entries[0].left_id, page.entries[0].right_id, page.entries[0].name),
            (12, 34, "Hat"),
        )
        self.assertEqual(
            parse_item_ids("https://example.com/item.php?lid=12&rid=34"), (12, 34)
        )


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_ownership(self):
        session = MagicMock(closed=False)
        session.close = AsyncMock()
        async with Client(session):
            pass
        session.close.assert_not_awaited()
        with patch(
            "chickensmoothie.client.aiohttp.ClientSession", return_value=session
        ):
            async with Client():
                pass
        session.close.assert_awaited_once()

    async def test_http_failure_propagates(self):
        session = MagicMock(closed=False)
        response = MagicMock()
        response.raise_for_status.side_effect = aiohttp.ClientError("failure")
        session.get.return_value.__aenter__ = AsyncMock(return_value=response)
        with self.assertRaises(aiohttp.ClientError):
            await Client(session).get_archive_events(2026)

    async def test_login_failure(self):
        session = MagicMock(closed=False)
        response = MagicMock()
        response.text = AsyncMock(
            return_value='<div id="message"><p>Wrong password</p></div>'
        )
        session.post.return_value.__aenter__ = AsyncMock(return_value=response)
        with self.assertRaises(AuthenticationError):
            await Client(session).login("user", "password")

    async def test_archive_lookup_and_bot_storage(self):
        client = Client()
        event = ArchiveEvent(
            "January", "https://www.chickensmoothie.com/archive/2026/January/"
        )
        page = parse_archive(
            '<div class="archive-pet-tree-container"><img alt="Pet" src="/pet.php?k=ABC"></div>',
            event,
            "pets",
            2026,
        )
        client.get_archive_events = AsyncMock(return_value=[event])
        client.get_archive_event = AsyncMock(return_value=page)
        self.assertIsInstance(await client.get_pet("ABC", years=[2026]), Pet)
        self.assertIsNone(await client.get_pet("missing", years=[2026]))
        conn = MagicMock()
        conn.execute = AsyncMock()
        self.assertEqual(await process_event(client, conn, event, "pets", 2026), (1, 1))
        self.assertEqual(
            conn.execute.call_args.args[1], ("ABC", 2026, "January", event.link)
        )
