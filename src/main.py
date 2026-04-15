from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import sys
from typing import List

import aiohttp
import asqlite
import discord
from discord.ext import commands
from dotenv import load_dotenv
from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection

import cogs
from tasks import autoremind_task, initialize_reminder_times
from utils import chickensmoothie_login, mongodb_login

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DEV_GUILD_ID") or 0)


class Bot(commands.Bot):
    def __init__(
        self,
        *args,
        initial_extensions: List[str],
        archive_db_pool: asqlite.Pool,
        autoremind_client: AsyncMongoClient,
        autoremind_collection: AsyncCollection,
        web_client: aiohttp.ClientSession,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.initial_extensions = initial_extensions
        self.archive_db_pool = archive_db_pool
        self.autoremind_client = autoremind_client
        self.autoremind_collection = autoremind_collection
        self.web_client = web_client

    async def setup_hook(self):
        await chickensmoothie_login(self.web_client)

        for extension in self.initial_extensions:
            logging.info("Loading extension: %s", extension)
            await self.load_extension(extension)

        await initialize_reminder_times(self.autoremind_collection)
        self.loop.create_task(autoremind_task(self))

        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        logging.info("Successfully synced commands to guild")
        # await self.tree.sync()
        # logging.info("Successfully synced global commands")

        logging.info("Bot setup complete")

    async def on_ready(self):
        logging.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        logging.info("------")

    async def close(self) -> None:
        await self.archive_db_pool.close()
        close_result = self.autoremind_client.close()
        if asyncio.iscoroutine(close_result):
            await close_result
        if self.web_client:
            await self.web_client.close()
        await super().close()


async def main():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    dt_fmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
    )

    file_handler = logging.handlers.RotatingFileHandler(
        filename="../discord.log",
        encoding="utf-8",
        maxBytes=32 * 1024 * 1024,  # 32 MiB
        backupCount=5,
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)  # show INFO+ on console
    logger.addHandler(console_handler)

    headers = {
        "User-Agent": "CS-Pound Discord Bot Agent",
        "From": "haru@haruyuki.moe",
    }
    base_url = "https://www.chickensmoothie.com"

    async with aiohttp.ClientSession(base_url=base_url, headers=headers) as our_client:

        extensions = list(cogs.iter_cogs())
        extensions.append("jishaku")
        intents = discord.Intents.default()
        intents.message_content = True
        archive_db_pool = await asqlite.create_pool("../chickensmoothie.db")

        autoremind_client, autoremind_collection = await mongodb_login()

        bot = Bot(
            commands.when_mentioned,
            archive_db_pool=archive_db_pool,
            autoremind_client=autoremind_client,
            autoremind_collection=autoremind_collection,
            web_client=our_client,
            initial_extensions=extensions,
            intents=intents,
        )

        assert TOKEN is not None
        try:
            await bot.start(TOKEN)
        finally:
            await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
