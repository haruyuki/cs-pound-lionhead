from __future__ import annotations
import os
import logging

import asqlite
import discord
from discord.ext import commands
from dotenv import load_dotenv

import cogs

load_dotenv()
discord.utils.setup_logging()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DEV_GUILD_ID"))


class Bot(commands.Bot):
    def __init__(self, db_pool=asqlite.Pool) -> None:
        self.db_pool = db_pool
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self):
        self.db_pool = await asqlite.create_pool("../chickensmoothie.db")

        for cog in cogs.iter_cogs():
            logging.info(f"Loading extension: {cog}")
            await self.load_extension(cog)

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
        await self.db_pool.close()
        await super().close()


if __name__ == "__main__":
    bot = Bot()
    bot.run(TOKEN)
