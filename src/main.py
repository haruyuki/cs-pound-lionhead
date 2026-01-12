from __future__ import annotations

import asyncio
import os
import logging
import logging.handlers
from typing import List

import aiohttp
import asqlite
import discord
import lxml.html
from discord.ext import commands
from dotenv import load_dotenv

import cogs

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DEV_GUILD_ID"))


class Bot(commands.Bot):
    def __init__(
        self,
        *args,
        initial_extensions: List[str],
        archive_db_pool: asqlite.Pool,
        autoremind_db_pool: asqlite.Pool,
        web_client: aiohttp.ClientSession,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.initial_extensions = initial_extensions
        self.archive_db_pool = archive_db_pool
        self.autoremind_db_pool = autoremind_db_pool
        self.web_client = web_client

    async def setup_hook(self):
        payload = {
            "username": os.getenv("CS_USERNAME"),
            "password": os.getenv("CS_PASSWORD"),
            "redirect": "index.php",
            "autologin": "on",
            "login": "Login",
        }

        logging.debug("Performing login...")
        async with self.web_client.post(
            "/Forum/ucp.php?mode=login", data=payload
        ) as resp:
            resp.raise_for_status()
            text = await resp.text()
            dom = lxml.html.fromstring(text)
            login_message = dom.xpath('//div[@id="message"]//p/text()')
            if (
                login_message
                and login_message[0] == "You have been successfully logged in."
            ):
                logging.info("Login successful.")
            else:
                logging.error("Login failed. Some features may not work properly.")

        for extension in self.initial_extensions:
            logging.info(f"Loading extension: {extension}")
            await self.load_extension(extension)

        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        logging.info("Successfully synced commands to guild")
        # await self.tree.sync()
        # logging.info("Successfully synced global commands")

        logging.info("Bot setup complete")

    async def on_ready(self):
        logging.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logging.info("------")

    async def close(self) -> None:
        await self.archive_db_pool.close()
        await self.autoremind_db_pool.close()
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

    console_handler = logging.StreamHandler()
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
        autoremind_db_pool = await asqlite.create_pool("../autoremind.db")
        async with Bot(
            commands.when_mentioned,
            archive_db_pool=archive_db_pool,
            autoremind_db_pool=autoremind_db_pool,
            web_client=our_client,
            initial_extensions=extensions,
            intents=intents,
        ) as bot:
            await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
